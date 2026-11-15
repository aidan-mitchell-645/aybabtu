# -*- coding: utf-8 -*-
"""
hw.py -- Beepy hardware helpers: battery gauge + a 'doctor' self-check.

The Beepy battery lives on the RP2040 keyboard controller. The beepy-kbd driver
publishes it at /sys/firmware/beepy/battery_percent. If that file isn't there,
the driver isn't installed/loaded and we fall back gracefully (and doctor() will
say so). We try several known paths so it "just works" once the driver lands.
"""

import glob
import os
import shutil
import subprocess
from pathlib import Path

# ordered best-effort battery sources
_BATTERY_FILES = [
    "/sys/firmware/beepy/battery_percent",   # beepy-kbd driver (preferred)
    "/sys/firmware/sharp/battery_percent",   # older naming
]


def battery_percent():
    """Return int 0..100, or None if no gauge is exposed."""
    for p in _BATTERY_FILES:
        try:
            v = Path(p).read_text().strip()
            if v != "":
                return max(0, min(100, int(float(v))))
        except Exception:
            pass
    # generic kernel power_supply class
    for cap in glob.glob("/sys/class/power_supply/*/capacity"):
        try:
            return max(0, min(100, int(Path(cap).read_text().strip())))
        except Exception:
            pass
    return None


def battery_str():
    v = battery_percent()
    return f"{v}%" if v is not None else "--"


def battery_bar(width=5):
    """A tiny [####-] gauge, or dashes when unknown."""
    v = battery_percent()
    if v is None:
        return "[" + "?" * width + "]"
    filled = round(v / 100 * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _have(cmd):
    return shutil.which(cmd) is not None


def doctor():
    """Return a list of (label, status, detail) rows describing the rig."""
    rows = []

    # battery / driver
    drv = os.path.isdir("/sys/firmware/beepy")
    bp = battery_percent()
    if bp is not None:
        rows.append(("battery", "OK", battery_str()))
    elif drv:
        rows.append(("battery", "??", "driver dir present, no reading"))
    else:
        rows.append(("battery", "NO", "beepy-kbd driver not installed"))

    # framebuffer / sharp display
    fbs = []
    for fb in sorted(glob.glob("/sys/class/graphics/fb*")):
        name = ""
        try:
            name = Path(fb, "name").read_text().strip()
        except Exception:
            pass
        fbs.append(f"{os.path.basename(fb)}:{name or '?'}")
    rows.append(("display", "OK" if fbs else "NO", ", ".join(fbs) or "no fb"))

    # i2c (keyboard controller lives here)
    i2c = sorted(glob.glob("/dev/i2c-*"))
    rows.append(("i2c", "OK" if i2c else "NO",
                 ", ".join(os.path.basename(x) for x in i2c) or "none"))

    # wifi iface
    try:
        out = subprocess.run("iw dev 2>/dev/null | awk '/Interface/{print $2}'",
                             shell=True, capture_output=True, text=True, timeout=4)
        ifaces = out.stdout.split()
    except Exception:
        ifaces = []
    rows.append(("wifi", "OK" if ifaces else "??", ", ".join(ifaces) or "none"))

    # tooling
    for tool in ("nmap", "searchsploit", "msfconsole", "arp-scan", "iw"):
        rows.append((tool, "OK" if _have(tool) else "no",
                     shutil.which(tool) or "not installed"))

    return rows


if __name__ == "__main__":
    print("battery:", battery_str(), battery_bar())
    print("---- doctor ----")
    for label, status, detail in doctor():
        print(f"  [{status:>2}] {label:<12} {detail}")
