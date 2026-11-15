# -*- coding: utf-8 -*-
"""
gfx.py -- portrait pixel-art frame compositor for AYBABTU.

Renders the whole UI as a vertical image sized to the panel (default 240x320),
styled after the Zero Wing / "CATS" intro: deep background, a cyber-villain
mascot with a glowing scan-eye, and an orange/purple/green palette. The mascot
expression + eye change with what the launcher is doing.

compose(state, size) -> PIL.Image (RGB). display.py maps/rotates it onto the
real framebuffer. Everything is drawn blocky and upscaled NEAREST -> crisp
pixel-art, no anti-aliasing.
"""

from PIL import Image, ImageDraw, ImageFont

# ---- Zero Wing palette ----
BG    = (6, 8, 20)        # deep blue-black
PANEL = (16, 18, 40)
FG    = (0, 255, 110)     # terminal green
DIM   = (0, 120, 55)
ACC   = (255, 120, 0)     # CATS orange (selection, eye)
PUR   = (150, 70, 220)    # cape purple
STEEL = (120, 140, 175)   # cyber skin
WARN  = (255, 60, 60)
WHITE = (220, 235, 255)

_FONT = ImageFont.load_default()


# ----------------------------------------------------------- text helpers ----
def _text_img(s, color, scale):
    bbox = _FONT.getbbox(s)
    tw, th = max(1, bbox[2] - bbox[0]), max(1, bbox[3] - bbox[1])
    tmp = Image.new("RGBA", (tw + 2, th + 2), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((1 - bbox[0], 1 - bbox[1]), s, font=_FONT, fill=color + (255,))
    if scale != 1:
        tmp = tmp.resize((tmp.width * scale, tmp.height * scale), Image.NEAREST)
    return tmp


def _blit_text(base, xy, s, color=FG, scale=2, center_x=None):
    img = _text_img(s, color, scale)
    x, y = xy
    if center_x is not None:
        x = center_x - img.width // 2
    base.alpha_composite(img, (int(x), int(y)))
    return img.width


# ------------------------------------------------------------- multicolor ----
def _msprite(rows, pal, scale=1):
    h = len(rows)
    w = max(len(r) for r in rows)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            c = pal.get(ch)
            if c is not None:
                px[x, y] = c + (255,)
    if scale != 1:
        img = img.resize((w * scale, h * scale), Image.NEAREST)
    return img


# cyber-villain head. P=helmet/cape purple, S=steel skin, #=outline,
# L=human (left) eye, R=cybernetic (right) eye [mood colour], W=eye wire,
# M=mouth. Reads as a face with one glowing cyber eye.
_VILLAIN = [
    "......#######.......",
    "....##PPPPPPP##......",
    "...#PPPPPPPPPPP#.....",
    "..#PPP#######PPP#....",
    "..#PP#SSSSSSSSS#P#...",
    "..#P#SSSSSSSSSSS#P...",
    "..##SSSSSSSSSSSSS#...",
    "..#SSSSSSSSSSSSSS#...",
    "..#SLLLSSSSSRRRRS#...",   # eyes
    "..#SLLLSSSSSRRRRS#...",
    "..#SSSSSSSSSSWWRS#...",   # cyber-eye wire
    "..#SSSSSSSSSSSWSS#...",
    "..#SSSSS###SSSSSS#...",
    "..#SSSSMMMMMSSSSS#...",   # mouth
    "..#SSSSSSSSSSSSSS#...",
    "...#SSSSSSSSSSSSS#...",
    "....#SSSSSSSSSSS#....",
    "...P##SSSSSSSSS##P...",
    "..PPPP#SSSSSSS#PPPP..",
    ".PPPPPP#######PPPPPP.",
    "PPPPPPPPPPPPPPPPPPPPP",
    "PPPPPPPPPPPPPPPPPPPPP",
]

_BASE_PAL = {"#": (20, 24, 44), "P": PUR, "S": STEEL, "M": (25, 16, 16),
             "L": (205, 222, 245), "W": ACC, ".": None, " ": None}


def villain(mood, frame=0, scale=5):
    """Cyber-villain mascot; the right (cyber) eye reflects mood."""
    eye = {
        "idle": ACC, "boot": ACC, "scanning": (255, 210, 70),
        "hit": FG, "pwn": WARN, "empty": DIM, "fail": (45, 45, 60),
        "sleep": (45, 45, 60),
    }.get(mood, ACC)
    pal = dict(_BASE_PAL)
    pal["R"] = eye
    if mood in ("fail", "sleep"):          # dead cyber eye: wire goes dark too
        pal["W"] = (60, 45, 20)
        pal["L"] = (70, 80, 95)
    img = _msprite(_VILLAIN, pal, scale=1)
    # bright core in the cyber eye
    img.putpixel((12, 8), (255, 255, 255, 255))
    # scan sweep across the eyes while scanning
    if mood == "scanning":
        sx = 4 + (frame % 12)
        for ey in (8, 9):
            if 0 <= sx < img.width:
                img.putpixel((sx, ey), (255, 255, 255, 255))
    # blink: close eyes briefly
    if mood in ("idle", "hit") and frame % 8 == 7:
        for ey in (8, 9):
            for x in range(4, 16):
                img.putpixel((x, ey), STEEL + (255,))
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)


# ------------------------------------------------------------------- icons ----
_ICONS = {
    "RECON":    ["..#..", ".#.#.", "#.#.#", ".#.#.", "..#.."],
    "EXPLOIT":  [".###.", "#o.o#", "#####", ".#.#.", ".#.#."],
    "WIFI":     ["....#", "..#.#", "..#.#", "#.#.#", "#.#.#"],
    "LOOT":     ["##...", "#####", "#...#", "#...#", "#####"],
    "TERMINAL": ["#....", "##...", "###..", "##...", "#...#"],
    "DOCTOR":   ["..#..", "..#..", "#####", "..#..", "..#.."],
    "QUIT":     ["#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
    "TOOL":     ["#####", "#...#", "#.#.#", "#...#", "#####"],
}


def icon(name, color, scale=3):
    rows = _ICONS.get(name, _ICONS["TOOL"])
    return _msprite(rows, {"#": color, "o": None, ".": None}, scale)


def battery_icon(pct, color=FG, scale=2):
    cells = 4 if pct is None else round((pct or 0) / 100 * 4)
    inside = ("?##?" if pct is None else
              "".join("#" if i < cells else "." for i in range(4)))
    rows = [".######.", "#" + inside + "##", ".######."]
    return _msprite(rows, {"#": color, ".": None}, scale)


# ------------------------------------------------------------- short labels ---
STATUS = {"boot": "BOOTING", "idle": "READY", "scanning": "SCANNING",
          "hit": "HOSTS UP", "pwn": "EXPLOITS", "empty": "NOTHING",
          "fail": "ABORTED", "sleep": "SLEEP"}


# ----------------------------------------------------------------- compose ----
def compose(state, size=(240, 320)):
    w, h = size
    base = Image.new("RGBA", (w, h), BG + (255,))
    d = ImageDraw.Draw(base)
    cx = w // 2

    # ---- top status bar ----
    d.rectangle([0, 0, w - 1, 20], fill=PANEL)
    pct = state.get("batt_pct")
    base.alpha_composite(battery_icon(pct, FG), (5, 5))
    _blit_text(base, (28, 3), (f"{pct}%" if pct is not None else "--"), FG, 2)
    _blit_text(base, (0, 5), "ZeroBase", DIM, 1, center_x=cx)
    clk = _text_img(state.get("clock", "--:--"), ACC, 2)
    base.alpha_composite(clk, (w - clk.width - 6, 3))

    # ---- mascot ----
    mh_top = 26
    v = villain(state.get("mood", "idle"), state.get("frame", 0), scale=5)
    vx = cx - v.width // 2
    # subtle orange backdrop glow behind the head (Zero Wing vibe)
    d.rectangle([vx + 8, mh_top + 6, vx + v.width - 8, mh_top + v.height - 18],
                fill=(40, 22, 6))
    base.alpha_composite(v, (vx, mh_top))

    # ---- status word ----
    sy = mh_top + v.height + 4
    word = state.get("say") or STATUS.get(state.get("mood", "idle"), "")
    _blit_text(base, (0, sy), word, ACC, 2, center_x=cx)

    # ---- identity line ----
    iy = sy + 20
    _blit_text(base, (0, iy), f"{state.get('iface','net')} {state.get('ip','0.0.0.0')}",
               FG, 1, center_x=cx)

    # ---- divider ----
    dy = iy + 16
    d.line([(8, dy), (w - 8, dy)], fill=DIM)

    # ---- vertical menu ----
    items = state.get("menu", [])
    sel = state.get("sel", 0)
    y0 = dy + 6
    rowh = 19
    avail = max(1, (h - 2 - y0) // rowh)
    top = 0
    if len(items) > avail:
        top = min(max(0, sel - avail // 2), len(items) - avail)
    for r, i in enumerate(range(top, min(len(items), top + avail))):
        it = items[i]
        y = y0 + r * rowh
        selected = (i == sel)
        if selected:
            d.rectangle([4, y - 1, w - 5, y + rowh - 3], fill=ACC)
        txtcol = BG if selected else FG
        ic = icon(it["label"], BG if selected else FG, scale=3)
        base.alpha_composite(ic, (10, y + 1))
        _blit_text(base, (32, y + 2), it["label"], txtcol, 2)

    # ---- scanlines ----
    if state.get("scanlines", True):
        ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        for yy in range(22, h, 4):
            od.line([(0, yy), (w, yy)], fill=(0, 0, 0, 90))
        base.alpha_composite(ov)
    return base.convert("RGB")


if __name__ == "__main__":
    import sys
    menu = [{"label": n, "desc": ""} for n in
            ("RECON", "EXPLOIT", "WIFI", "LOOT", "TERMINAL", "DOCTOR", "QUIT")]
    st = {"mood": "idle", "ip": "192.168.1.106", "iface": "wlan0",
          "batt_pct": 84, "clock": "21:14", "menu": menu, "sel": 0, "frame": 0}
    compose(st).save(sys.argv[1] if len(sys.argv) > 1 else "preview.png")
    print("ok")
