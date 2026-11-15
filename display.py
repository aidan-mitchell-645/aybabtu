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
        self.sim_dir = os.environ.get("AYBABTU_SIM")
        self.invert = os.environ.get("AYBABTU_INVERT") == "1"
        self.fb = None if self.sim_dir else detect_fb()
        self.frame_no = 0
        if self.fb:
            self._f = open(self.fb["dev"], "r+b")
        else:
            self._f = None
            if self.sim_dir:
                Path(self.sim_dir).mkdir(parents=True, exist_ok=True)

    @property
    def size(self):
        return (self.fb["w"], self.fb["h"]) if self.fb else (400, 240)

    @property
    def info(self):
        if self.fb:
            return f"{self.fb['dev']} {self.fb['w']}x{self.fb['h']} {self.fb['bpp']}bpp ({self.fb['name']})"
        return "SIM (no framebuffer)"

    def show(self, img):
        if self.fb:
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


# --------------------------------------------------------------- Keyboard ----
class Keyboard:
    """Non-blocking raw-tty key reader. Returns tokens; None if nothing ready."""
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.saved = None
        try:
            self.saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        except Exception:
            self.saved = None  # not a tty (piped) -- get() will no-op

    def cbreak(self):
        """Re-enter raw mode (after a console action restored cooked mode)."""
        try:
            tty.setcbreak(self.fd)
        except Exception:
            pass

    def get(self, timeout=0.1):
        try:
            r, _, _ = select.select([self.fd], [], [], timeout)
        except Exception:
            return None
        if not r:
            return None
        ch = os.read(self.fd, 1)
        if not ch:
            return None
        if ch == b"\x1b":  # escape or arrow sequence
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

    def restore(self):
        if self.saved:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)
            except Exception:
                pass


if __name__ == "__main__":
    d = Display()
    print("display:", d.info)
    fb = detect_fb()
    print("detect_fb:", fb)
