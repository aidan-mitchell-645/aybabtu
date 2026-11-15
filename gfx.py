# -*- coding: utf-8 -*-
"""
gfx.py -- pixel-art frame compositor for AYBABTU.

Renders the whole UI as a 400x240 image (the Beepy Sharp LCD's native size)
with Pillow: a chunky CATS-cat mascot sprite, an icon menu, a battery glyph,
and CRT scanlines. Everything is drawn at 1x on small canvases and upscaled
with NEAREST so it stays crisp, blocky pixel-art -- not anti-aliased.

compose(state) -> PIL.Image (RGB). display.py pushes it to the framebuffer
(or a PNG for previews). Colours threshold cleanly to 1-bit for the mono LCD.
"""

from PIL import Image, ImageDraw, ImageFont

W, H = 400, 240

# green-phosphor hacker palette (also clean when thresholded to 1-bit mono)
BG    = (0, 0, 0)
FG    = (0, 255, 90)
DIM   = (0, 110, 45)
ACC   = (0, 255, 200)
WARN  = (255, 60, 60)
WHITE = (210, 255, 220)

_FONT = ImageFont.load_default()


# --------------------------------------------------------------- pixel tools --
def _sprite(rows, on=FG, off=None, scale=1):
    """Build an image from a list of strings. '#'/'1' = on, anything else off."""
    h = len(rows)
    w = max(len(r) for r in rows) if rows else 1
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in "#1*@":
                px[x, y] = on + (255,)
            elif off is not None and ch in ".o":
                px[x, y] = off + (255,)
    if scale != 1:
        img = img.resize((w * scale, h * scale), Image.NEAREST)
    return img


def _text(draw, xy, s, color=FG, scale=1):
    """Draw crisp bitmap text, optionally pixel-doubled."""
    if scale == 1:
        draw.text(xy, s, font=_FONT, fill=color)
        return
    bbox = _FONT.getbbox(s)
    tw, th = max(1, bbox[2] - bbox[0]), max(1, bbox[3] - bbox[1])
    tmp = Image.new("RGBA", (tw + 2, th + 2), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((1 - bbox[0], 1 - bbox[1]), s, font=_FONT, fill=color + (255,))
    tmp = tmp.resize((tmp.width * scale, tmp.height * scale), Image.NEAREST)
    return tmp


def _paste_text(base, xy, s, color=FG, scale=2):
    img = _text(ImageDraw.Draw(base), (0, 0), s, color, scale)
    if img:
        base.alpha_composite(img, xy)


# ------------------------------------------------------------------ mascot ----
# a chunky CATS-cat head; eyes+mouth swap per mood. 1x grid, upscaled later.
_HEAD = [
    "..##..........##..",
    ".#..#........#..#.",
    ".#...#......#...#.",
    ".#....######....#.",
    ".#..............#.",
    "#................#",
    "#................#",
    "#................#",
    "#................#",
    "#................#",
    "#................#",
    ".#..............#.",
    ".#..............#.",
    "..#............#..",
    "...############...",
]
# (eyes_row_offset, mouth_row_offset) overlays keyed by mood
_EYES = {
    "idle":     ["#..#", "....", ".##."],   # chill
    "scanning": ["o..o", "....", "####"],    # wide, focused
    "hit":      ["^..^", "....", ".##."],    # happy
    "pwn":      ["@..@", "....", "WVVW"],     # wired
    "empty":    ["-..-", "....", ".--."],    # meh
    "fail":     ["x..x", "....", "####"],    # dead
    "sleep":    ["-..-", "....", "...."],    # zzz
    "boot":     ["o..o", "....", ".oo."],
}


def mascot(mood, frame=0, scale=5):
    """Return an RGBA pixel-art mascot image for a mood."""
    head = _sprite(_HEAD, on=FG)
    px = head.load()
    # eye sockets at rows 6-8, cols 4-7 (left) and 10-13 (right)
    eyes = _EYES.get(mood, _EYES["idle"])
    # blink
    if frame % 6 == 5 and mood in ("idle", "scanning", "hit"):
        eyes = ["....", "....", eyes[2]]
    ov = _sprite(["    " + eyes[0] + "    ",
                  "                 ",
                  "    " + eyes[1] + "    "], on=ACC)
    # place eyes roughly in the middle band
    # draw directly for control:
    d = ImageDraw.Draw(head)
    cols = {"L": (4, 7), "R": (10, 13)}
    midy = 6
    # left eye
    _draweye(head, eyes, 4, midy)
    _draweye(head, eyes, 10, midy, right=True)
    # mouth row ~ y=11
    mouth = eyes[2]
    for i, ch in enumerate(mouth):
        if ch not in ". ":
            head.putpixel((6 + i, 11), ACC + (255,))
    big = head.resize((head.width * scale, head.height * scale), Image.NEAREST)
    # sleepy Z's
    if mood == "sleep":
        dd = ImageDraw.Draw(big)
        _paste = _text(dd, (big.width - 22, 2), "z", DIM, 2)
    return big


def _draweye(img, eyes, col, row, right=False):
    pat = eyes[0]
    glyph = pat[0] if not right else pat[3]
    cx, cy = col, row
    if glyph in "o@":
        for dx in range(2):
            for dy in range(2):
                _safe(img, cx + dx, cy + dy, ACC)
    elif glyph == "#":
        _safe(img, cx, cy, ACC); _safe(img, cx + 1, cy, ACC)
    elif glyph == "^":
        _safe(img, cx + 1, cy, ACC); _safe(img, cx, cy + 1, ACC); _safe(img, cx + 2, cy + 1, ACC)
    elif glyph == "x":
        _safe(img, cx, cy, ACC); _safe(img, cx + 1, cy + 1, ACC); _safe(img, cx + 1, cy - 1, ACC)
    elif glyph == "-":
        _safe(img, cx, cy + 1, ACC); _safe(img, cx + 1, cy + 1, ACC)
    else:
        _safe(img, cx, cy, ACC)


def _safe(img, x, y, color):
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), color + (255,))


# ------------------------------------------------------------------- icons ----
_ICONS = {
    "RECON": ["..#..", ".#.#.", "#.#.#", ".#.#.", "..#.."],       # crosshair/target
    "EXPLOIT": [".###.", "#o.o#", "#####", ".#.#.", ".#.#."],     # skull
    "WIFI": ["....#", "..#.#", "..#.#", "#.#.#", "#.#.#"],         # signal bars
    "LOOT": ["##...", "#####", "#...#", "#...#", "#####"],         # folder
    "TERMINAL": ["#....", "##...", "###..", "##...", "#...#"],     # >_ prompt
    "DOCTOR": ["..#..", "..#..", "#####", "..#..", "..#.."],      # medical +
    "QUIT": ["#...#", ".#.#.", "..#..", ".#.#.", "#...#"],         # X
    "TOOL": ["#####", "#...#", "#.#.#", "#...#", "#####"],         # generic box
}


def icon(name, scale=4):
    rows = _ICONS.get(name, _ICONS["TOOL"])
    return _sprite(rows, on=FG, scale=scale)


def battery_icon(pct, scale=3):
    fill = "#" if pct is None else ""
    cells = 4 if pct is None else round((pct or 0) / 100 * 4)
    body = []
    body.append(".######.")
    inside = "".join("#" if i < cells else "." for i in range(4))
    if pct is None:
        inside = "?##?"
    body.append("#" + inside + "##")   # includes the little nub
    body.append(".######.")
    return _sprite(body, on=FG, scale=scale)


# ----------------------------------------------------------------- compose ----
def compose(state):
    """state: mood, ip, iface, batt_pct, clock, menu(list of dict), sel, say."""
    base = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(base)

    # ---- top bar ----
    d.rectangle([0, 0, W, 20], fill=BG, outline=DIM)
    _paste_text(base, (6, 3), "ALL YOUR BASE", FG, 2)
    # battery + clock on the right (spaced so nothing collides)
    pct = state.get("batt_pct")
    base.alpha_composite(battery_icon(pct), (W - 148, 5))
    _paste_text(base, (W - 122, 3), (f"{pct}%" if pct is not None else "--"), FG, 2)
    _paste_text(base, (W - 64, 3), state.get("clock", "--:--"), ACC, 2)

    # ---- left: mascot panel ----
    d.rectangle([4, 24, 150, 214], outline=DIM)
    m = mascot(state.get("mood", "idle"), state.get("frame", 0), scale=6)
    base.alpha_composite(m, (12, 30))
    # identity under mascot
    _paste_text(base, (10, 150), state.get("iface", "net"), ACC, 2)
    _paste_text(base, (10, 168), state.get("ip", "0.0.0.0"), WHITE, 2)
    # speech bubble
    d.rectangle([10, 188, 146, 210], outline=FG)
    say = (state.get("say", "") or "")[:17]
    _paste_text(base, (14, 192), say, FG, 2)

    # ---- right: icon menu ----
    items = state.get("menu", [])
    sel = state.get("sel", 0)
    x0, y0, rowh = 158, 26, 30
    avail = (214 - y0) // rowh
    top = 0
    if len(items) > avail:
        top = min(max(0, sel - avail // 2), len(items) - avail)
    for r, i in enumerate(range(top, min(len(items), top + avail))):
        it = items[i]
        y = y0 + r * rowh
        selected = (i == sel)
        if selected:
            d.rectangle([x0 - 2, y - 1, W - 4, y + rowh - 4], fill=FG)
        txtcol = BG if selected else FG
        ic = icon(it["label"], scale=4)
        # tint icon black when selected
        if selected:
            ic = _tint(ic, BG)
        base.alpha_composite(ic, (x0 + 2, y + 1))
        _paste_text(base, (x0 + 26, y + 2), it["label"], txtcol, 2)
        sub = it.get("desc", "")[:20]
        if sub:
            _paste_text(base, (x0 + 26, y + 16), sub, (BG if selected else DIM), 1)

    # ---- subtle scanlines for CRT vibe (skip the top bar; every 4px) ----
    if state.get("scanlines", True):
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for y in range(24, H, 4):
            od.line([(0, y), (W, y)], fill=(0, 0, 0, 110))
        base.alpha_composite(overlay)
    return base.convert("RGB")


def _tint(img, color):
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a > 0:
                px[x, y] = color + (a,)
    return out


# ------------------------------------------------------------------ preview ---
if __name__ == "__main__":
    import sys
    menu = [
        {"label": "RECON", "desc": "nmap > exploit"},
        {"label": "EXPLOIT", "desc": "msf / sploit"},
        {"label": "WIFI", "desc": "scan aps"},
        {"label": "LOOT", "desc": "saved scans"},
        {"label": "TERMINAL", "desc": "shell"},
        {"label": "DOCTOR", "desc": "self-check"},
    ]
    state = {"mood": "idle", "ip": "192.168.1.37", "iface": "wlan0",
             "batt_pct": 84, "clock": "21:14", "menu": menu, "sel": 0,
             "say": "ALL YOUR BASE", "frame": 0}
    out = sys.argv[1] if len(sys.argv) > 1 else "preview.png"
    compose(state).save(out)
    print("wrote", out)
