# -*- coding: utf-8 -*-
"""
display.py -- push pixel-art frames to the Beepy framebuffer + read the keyboard.

Output: detects the framebuffer geometry/bit-depth from sysfs and packs a PIL
image into the right pixel format (32/16/8/1 bpp). Falls back to writing PNGs
("sim" mode) when there's no framebuffer or AYBABTU_SIM is set, so the exact
same renderer can be previewed over SSH or off-device.

Input: puts the tty in cbreak/raw mode and returns key tokens (UP/DOWN/ENTER/
ESC/digits/letters) without blocking, so the mascot can animate while idle.

Env knobs:
    AYBABTU_SIM=dir   force sim mode, write frames to dir/frame.png
    AYBABTU_FB=/dev/fb1   use a specific framebuffer
    AYBABTU_INVERT=1  flip black/white (some mono panels are 0=white)
"""

import os
import select
import sys
import termios
import tty
from pathlib import Path

from PIL import Image


# ----------------------------------------------------------- fb autodetect ---
def _read(path, default=""):
    try:
        return Path(path).read_text().strip()
    except Exception:
        return default


def _settings():
    """Persistent display prefs (rotate/invert). Env vars override these."""
    import json
    try:
        return json.loads((Path(__file__).resolve().parent / "settings.json").read_text())
    except Exception:
        return {}


def detect_fb():
    """Return dict(dev,w,h,bpp,stride,name) for the first usable fb, or None."""
    forced = os.environ.get("AYBABTU_FB")
    devs = [forced] if forced else [f"/dev/fb{i}" for i in range(4)]
    for dev in devs:
        if not dev or not os.path.exists(dev):
            continue
        n = dev.rsplit("fb", 1)[-1]
        sysbase = f"/sys/class/graphics/fb{n}"
        vsize = _read(f"{sysbase}/virtual_size")       # "400,240"
        bpp = _read(f"{sysbase}/bits_per_pixel")
        stride = _read(f"{sysbase}/stride")
        name = _read(f"{sysbase}/name", "fb")
        try:
            w, h = (int(x) for x in vsize.split(","))
            bpp = int(bpp)
        except Exception:
            continue
        try:
            stride = int(stride)
        except Exception:
            stride = w * (bpp // 8 if bpp >= 8 else 1)
        return {"dev": dev, "w": w, "h": h, "bpp": bpp, "stride": stride, "name": name}
    return None


def _pack565(rgb, w, h):
    """RGB image -> little-endian RGB565 bytes. numpy-fast, pure-python fallback."""
    try:
        import numpy as np
        a = np.asarray(rgb, dtype=np.uint16)
        v = ((a[:, :, 0] & 0xF8) << 8) | ((a[:, :, 1] & 0xFC) << 3) | (a[:, :, 2] >> 3)
        return v.astype("<u2").tobytes()
    except Exception:
        px = rgb.load()
        out = bytearray(w * h * 2)
        i = 0
        for y in range(h):
            for x in range(w):
                r, g, b = px[x, y]
                val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                out[i] = val & 0xFF
                out[i + 1] = (val >> 8) & 0xFF
                i += 2
        return bytes(out)


def _restride(src, srcrow, stride, h):
    """Copy tightly-packed rows into a (possibly) padded stride buffer."""
    if stride == srcrow:
        return src
    out = bytearray(stride * h)
    for y in range(h):
        out[y * stride:y * stride + srcrow] = src[y * srcrow:(y + 1) * srcrow]
    return bytes(out)


def pack_frame(img, w, h, bpp, stride, invert=False):
    """PIL image -> raw framebuffer bytes. Uses PIL's C codecs (fast)."""
    if img.size != (w, h):
        img = img.resize((w, h), Image.NEAREST)

    if bpp >= 24:  # 32bpp XRGB8888 == BGRA byte order little-endian
        src = img.convert("RGBA").tobytes("raw", "BGRA")
        return _restride(src, w * 4, stride, h)

    if bpp == 16:  # RGB565 little-endian
        src = _pack565(img.convert("RGB"), w, h)
        return _restride(src, w * 2, stride, h)

    if bpp == 8:  # grayscale
        g = img.convert("L")
        if invert:
            g = g.point(lambda v: 255 - v)
        return _restride(g.tobytes(), w, stride, h)

    # 1 bpp mono (Sharp LCD): threshold (no dither) -> PIL "1" packs MSB-first
    g = img.convert("L").point(lambda v: 255 if v > 90 else 0)
    if invert:
        g = g.point(lambda v: 255 - v)
    bits = g.convert("1", dither=Image.NONE)
    return _restride(bits.tobytes(), (w + 7) // 8, stride, h)


# --------------------------------------------------------------- Display -----
class Display:
    def __init__(self):
        s = _settings()
        self.sim_dir = os.environ.get("AYBABTU_SIM")
        inv = os.environ.get("AYBABTU_INVERT")
        self.invert = (inv == "1") if inv is not None else bool(s.get("invert", False))
        rot = os.environ.get("AYBABTU_ROTATE")
        self.user_rot = int(rot if rot is not None else s.get("rotate", 0) or 0) % 360
        self.fb = None if self.sim_dir else detect_fb()
        self.frame_no = 0
        if self.fb:
            self._f = open(self.fb["dev"], "r+b")
        else:
            self._f = None
            if self.sim_dir:
                Path(self.sim_dir).mkdir(parents=True, exist_ok=True)

    @property
    def logical_size(self):
        """Portrait canvas to compose in (w<=h), regardless of fb orientation."""
        if self.fb:
            a, b = self.fb["w"], self.fb["h"]
            return (min(a, b), max(a, b))
        return (240, 320)

    # kept for compatibility
    size = logical_size

    @property
    def info(self):
        if self.fb:
            return (f"{self.fb['dev']} {self.fb['w']}x{self.fb['h']} "
                    f"{self.fb['bpp']}bpp ({self.fb['name']}) rot={self.user_rot}")
        return "SIM (no framebuffer) 240x320"

    def _orient(self, img):
        """Rotate the portrait logical frame to match the physical fb buffer."""
        fbw, fbh = self.fb["w"], self.fb["h"]
        total = self.user_rot
        if fbw > fbh:                       # physical fb is landscape
            total = (total + 90) % 360
        if total:
            img = img.rotate(total, expand=True)
        if img.size != (fbw, fbh):
            img = img.resize((fbw, fbh), Image.NEAREST)
        return img

    def show(self, img):
        if self.fb:
            img = self._orient(img)
            raw = pack_frame(img, self.fb["w"], self.fb["h"], self.fb["bpp"],
                             self.fb["stride"], self.invert)
            self._f.seek(0)
            self._f.write(raw)
            self._f.flush()
        elif self.sim_dir:
            img.save(os.path.join(self.sim_dir, "frame.png"))
            self.frame_no += 1

    def close(self):
        if self._f:
            try:
                self._f.close()
            except Exception:
                pass


def _input_mode():
    """'evdev' (read input devices directly -- works over SSH) or 'tty'."""
    if os.environ.get("AYBABTU_SIM"):
        return "tty"
    m = os.environ.get("AYBABTU_INPUT") or _settings().get("input") or "auto"
    if m in ("evdev", "tty"):
        return m
    # auto: use evdev when we're root and python3-evdev is available
    try:
        import evdev  # noqa: F401
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            return "evdev"
    except Exception:
        pass
    return "tty"


# --------------------------------------------------------------- Keyboard ----
class Keyboard:
    """Non-blocking key reader -> tokens (UP/DOWN/ENTER/ESC/digits/letters).

    Two backends: a raw-tty reader (keys typed into this terminal), and an
    evdev reader that reads the input devices directly, so the Beepy keyboard
    and the trackpad->arrows mapping drive the UI even when launched over SSH.
    """
    def __init__(self):
        import collections
        self.fd = sys.stdin.fileno()
        self.saved = None
        self.evdevs = None
        self._q = collections.deque()
        # always put the tty in cbreak (stops stray echo); harmless if not a tty
        try:
            self.saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        except Exception:
            self.saved = None
        if _input_mode() == "evdev":
            self._init_evdev()

    # ---- evdev backend ----
    def _init_evdev(self):
        try:
            import evdev
            self._ev = evdev
            ec = evdev.ecodes
            self._map = {
                ec.KEY_UP: "UP", ec.KEY_DOWN: "DOWN", ec.KEY_LEFT: "LEFT",
                ec.KEY_RIGHT: "RIGHT", ec.KEY_ENTER: "ENTER",
                ec.KEY_KPENTER: "ENTER", ec.KEY_TAB: "ENTER",  # click = select
                ec.KEY_ESC: "ESC", ec.KEY_BACKSPACE: "BACKSPACE",
                ec.KEY_Q: "q", ec.KEY_J: "j", ec.KEY_K: "k",
                ec.KEY_L: "l", ec.KEY_R: "r",
            }
            for n in range(10):
                self._map[getattr(ec, f"KEY_{n}")] = str(n)
            devs = []
            for path in evdev.list_devices():
                try:
                    d = evdev.InputDevice(path)
                except Exception:
                    continue
                keys = d.capabilities().get(ec.EV_KEY, [])
                if ec.KEY_ENTER in keys or ec.KEY_UP in keys or ec.KEY_A in keys:
                    devs.append(d)
            self.evdevs = devs or None
        except Exception:
            self.evdevs = None   # fall back to tty reader

    def _pump(self, timeout):
        r, _, _ = select.select(self.evdevs, [], [], timeout)
        for d in r:
            try:
                for ev in d.read():
                    if ev.type == self._ev.ecodes.EV_KEY and ev.value == 1:
                        tok = self._map.get(ev.code)
                        if tok:
                            self._q.append(tok)
            except OSError:
                pass

    # ---- shared API ----
    def get(self, timeout=0.1):
        if self.evdevs:
            if not self._q:
                self._pump(timeout)
            return self._q.popleft() if self._q else None
        return self._get_tty(timeout)

    def _get_tty(self, timeout):
        try:
            r, _, _ = select.select([self.fd], [], [], timeout)
        except Exception:
            return None
        if not r:
            return None
        ch = os.read(self.fd, 1)
        if not ch:
            return None
        if ch == b"\x1b":
            r, _, _ = select.select([self.fd], [], [], 0.02)
            if not r:
                return "ESC"
            seq = os.read(self.fd, 2)
            return {b"[A": "UP", b"[B": "DOWN", b"[C": "RIGHT",
                    b"[D": "LEFT"}.get(seq, "ESC")
        if ch in (b"\r", b"\n"):
            return "ENTER"
        if ch == b"\x7f":
            return "BACKSPACE"
        try:
            return ch.decode("ascii")
        except Exception:
            return None

    def suspend(self):
        """Hand the tty back to cooked mode so a console action can input()."""
        self.restore()

    def resume(self):
        """Return to UI input mode; drop any keys buffered during the action."""
        try:
            termios.tcflush(self.fd, termios.TCIFLUSH)
        except Exception:
            pass
        self.cbreak()
        self._q.clear()
        if self.evdevs:                      # drain stale device events
            try:
                r, _, _ = select.select(self.evdevs, [], [], 0)
                for d in r:
                    for _ in d.read():
                        pass
            except Exception:
                pass

    def cbreak(self):
        try:
            tty.setcbreak(self.fd)
        except Exception:
            pass

    def restore(self):
        if self.saved:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)
            except Exception:
                pass

    def close(self):
        self.restore()
        for d in (self.evdevs or []):
            try:
                d.close()
            except Exception:
                pass


if __name__ == "__main__":
    d = Display()
    print("display:", d.info)
    print("input mode:", _input_mode())
    fb = detect_fb()
    print("detect_fb:", fb)
