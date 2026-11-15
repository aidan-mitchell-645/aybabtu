#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AYBABTU -- a pwnagotchi-style pixel-art launcher for the Beepy (Pi Zero 2W +
BlackBerry keyboard) running Kali. Renders a real 400x240 graphical UI straight
to the framebuffer with a CATS-cat mascot that reacts to what you're doing, and
wraps the Kali tools behind big icon buttons.

  RECON (nmap, scope-gated) -> auto-chains into exploit leads (searchsploit/msf)
  EXPLOIT / WIFI / LOOT / TERMINAL / DOCTOR  + your own buttons via menu.json

Controls:  up/down or j/k move * number keys jump * Enter/right select
           q quit  (ESC also backs out)

Runs the graphical UI when a framebuffer is present; set AYBABTU_SIM=<dir> to
preview frames as PNGs instead. For a pure-text fallback, run aybabtu_tui.py.
"""

import json
import os
import random
import sys
import time
from pathlib import Path

import actions
import display
import faces
import gfx

VERSION = "0.3"
HERE = Path(__file__).resolve().parent
MENU_FILE = HERE / "menu.json"


def load_menu():
    items = [
        {"key": "1", "label": "RECON",    "desc": "nmap > exploit",  "action": "recon"},
        {"key": "2", "label": "EXPLOIT",  "desc": "msf / sploit",    "action": "exploit"},
        {"key": "3", "label": "WIFI",     "desc": "scan aps",        "action": "wifi"},
        {"key": "4", "label": "LOOT",     "desc": "saved scans",     "action": "loot"},
        {"key": "5", "label": "TERMINAL", "desc": "drop to shell",   "action": "shell"},
        {"key": "9", "label": "DOCTOR",   "desc": "self-check",      "action": "doctor"},
    ]
    if MENU_FILE.exists():
        try:
            for e in json.loads(MENU_FILE.read_text()).get("tools", []):
                items.append({"key": e.get("key", "?"), "label": e.get("label", "TOOL"),
                              "desc": e.get("desc", ""), "action": "cmd",
                              "cmd": e.get("cmd", ""), "needs_scope": e.get("needs_scope", False)})
        except Exception:
            pass
    items.append({"key": "0", "label": "QUIT", "desc": "", "action": "quit"})
    return items


def refresh_state(state):
    state["ip"] = actions._primary_ip()
    import hw
    out = actions.subprocess.run("ip route show default", shell=True,
                                 capture_output=True, text=True)
    parts = out.stdout.split()
    state["iface"] = parts[parts.index("dev") + 1] if "dev" in parts else "none"
    state["batt_pct"] = hw.battery_percent()


def new_taunt(mood):
    return faces.get(mood)[1][:17]


def run_action(disp, kb, state, item):
    """Drop to the text console, run the action, return to the pixel UI."""
    act = item["action"]
    if act == "quit":
        raise SystemExit
    kb.restore()
    os.system("clear")
    print("\033[1;32m== AYBABTU ==\033[0m\n")
    try:
        if act == "cmd":
            actions.run_cmd(state, item)
        elif act in actions.DISPATCH:
            actions.DISPATCH[act](state)
    except KeyboardInterrupt:
        pass
    finally:
        os.system("clear")
        kb.cbreak()
        if state["mood"] == "scanning":   # don't get stuck mid-scan face
            state["mood"] = "idle"
        state["say"] = new_taunt(state["mood"])


def main():
    disp = display.Display()
    kb = display.Keyboard()
    items = load_menu()
    state = {"mood": "boot", "ip": "...", "iface": "...", "batt_pct": None,
             "clock": "--:--", "menu": items, "sel": 0, "say": "BOOTING",
             "frame": 0, "scanlines": os.environ.get("AYBABTU_NOSCAN") != "1"}
    refresh_state(state)

    boot_until = time.time() + 1.6
    last_status = last_say = time.time()
    tick = 0
    try:
        while True:
            now = time.time()
            if state["mood"] == "boot" and now > boot_until:
                state["mood"] = "idle"; state["say"] = new_taunt("idle")
            state["clock"] = time.strftime("%H:%M")
            state["frame"] = tick
            if now - last_status > 10:
                refresh_state(state); last_status = now
            if now - last_say > 3.5:
                state["say"] = new_taunt(state["mood"]); last_say = now

            disp.show(gfx.compose(state))

            key = kb.get(timeout=0.4)
            tick += 1
            if key is None:
                continue
            if key in ("q", "0"):
                break
            elif key in ("UP", "k"):
                state["sel"] = (state["sel"] - 1) % len(items)
            elif key in ("DOWN", "j"):
                state["sel"] = (state["sel"] + 1) % len(items)
            elif key in ("ENTER", "RIGHT", "l"):
                run_action(disp, kb, state, items[state["sel"]])
                last_say = 0
            elif key == "r":
                refresh_state(state)
            else:
                for i, it in enumerate(items):
                    if it["key"] == key:
                        state["sel"] = i
                        run_action(disp, kb, state, it)
                        last_say = 0
                        break
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        kb.restore()
        disp.close()
        os.system("clear")
        print("CATS: YOU HAVE NO CHANCE TO SURVIVE MAKE YOUR TIME. (bye)")


if __name__ == "__main__":
    main()
