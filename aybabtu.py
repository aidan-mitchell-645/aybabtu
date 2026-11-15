#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AYBABTU  --  A pwnagotchi-style launcher skinned in "All Your Base" glory.
Built for the Beepy (Pi Zero 2W + BlackBerry keyboard) running Kali in the
framebuffer console. Pure-stdlib curses: no pip installs, no X, no fuss.

Controls:
    j / k  or  up/down     move
    number keys            jump straight to an item
    Enter / l / right      select
    r                      refresh status (ip, battery)
    q / 0                  quit

Scope rule: recon actions make you confirm the target is yours / authorized
before anything fires. Keep it a learning rig.
"""

import curses
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MENU_FILE = HERE / "menu.json"
LOOT_DIR = Path(os.environ.get("AYBABTU_LOOT", HERE / "loot"))
LOOT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- aesthetics --
QUOTES = [
    "ALL YOUR BASE ARE BELONG TO US",
    "SOMEBODY SET UP US THE BOMB",
    "YOU HAVE NO CHANCE TO SURVIVE MAKE YOUR TIME",
    "WHAT YOU SAY !!",
    "FOR GREAT JUSTICE",
    "MOVE 'ZIG' FOR GREAT JUSTICE",
    "YOU KNOW WHAT YOU DOING",
    "TAKE OFF EVERY 'ZIG'",
]

# mascot faces keyed by mood; the launcher swaps them as it works
FACES = {
    "idle":   "(⌐■_■)",   # (⌐■_■)  cool/cats
    "busy":   "(>_<)",
    "happy":  "(^_^)",
    "angry":  "(x_x)",
    "think":  "(._.)",
}


def sh(cmd):
    """Run a shell command, return stripped stdout or '' on failure."""
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip()
    except Exception:
        return ""


def primary_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"


def default_iface():
    out = sh("ip route show default")
    # e.g. "default via 192.168.1.1 dev wlan0 ..."
    parts = out.split()
    if "dev" in parts:
        return parts[parts.index("dev") + 1]
    return "none"


def battery():
    """Best-effort battery read across common Beepy / power_supply paths."""
    candidates = [
        "/sys/firmware/beepy/battery_percent",
        "/sys/firmware/sharp/battery_percent",
    ]
    for p in candidates:
        try:
            v = Path(p).read_text().strip()
            if v:
                return f"{v}%"
        except Exception:
            pass
    # generic power_supply
    base = Path("/sys/class/power_supply")
    if base.exists():
        for d in base.iterdir():
            cap = d / "capacity"
            if cap.exists():
                try:
                    return f"{cap.read_text().strip()}%"
                except Exception:
                    pass
    return "--"


# ---------------------------------------------------------------- menu model --
def builtin_menu():
    return [
        {"key": "1", "label": "RECON",    "desc": "nmap a target",         "action": "recon"},
        {"key": "2", "label": "EXPLOIT",  "desc": "msf / searchsploit",    "action": "exploit"},
        {"key": "3", "label": "WIFI",     "desc": "interfaces & monitor",  "action": "wifi"},
        {"key": "4", "label": "LOOT",     "desc": "saved scan output",     "action": "loot"},
        {"key": "5", "label": "TERMINAL", "desc": "drop to a real shell",  "action": "shell"},
    ]


def load_menu():
    """Built-ins + anything the user adds in menu.json (easy to extend)."""
    items = builtin_menu()
    if MENU_FILE.exists():
        try:
            extra = json.loads(MENU_FILE.read_text())
            for e in extra.get("tools", []):
                items.append({
                    "key": e.get("key", "?"),
                    "label": e.get("label", "TOOL"),
                    "desc": e.get("desc", ""),
                    "action": "cmd",
                    "cmd": e.get("cmd", ""),
                    "needs_scope": e.get("needs_scope", False),
                })
        except Exception:
            pass
    items.append({"key": "0", "label": "QUIT", "desc": "", "action": "quit"})
    # renumber keys 1..9 for the non-quit items if user config added more
    return items


# -------------------------------------------------------------- shell escape --
def run_in_terminal(stdscr, fn):
    """Leave curses, run a normal terminal program, come back cleanly."""
    curses.def_prog_mode()
    curses.endwin()
    os.system("clear")
    try:
        fn()
    finally:
        print("\n\033[1;32m[ press Enter to return to AYBABTU ]\033[0m", end="")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
    curses.reset_prog_mode()
    stdscr.clear()
    curses.curs_set(0)


# --------------------------------------------------------------- text prompt --
def prompt(stdscr, question, default=""):
    """Simple single-line input inside curses."""
    curses.curs_set(1)
    curses.echo()
    h, w = stdscr.getmaxyx()
    stdscr.move(h - 2, 0)
    stdscr.clrtoeol()
    stdscr.addstr(h - 2, 0, (question + " ")[: w - 1], curses.A_BOLD)
    stdscr.refresh()
    try:
        val = stdscr.getstr(h - 2, min(len(question) + 1, w - 2), 80)
        val = val.decode("utf-8", "ignore").strip()
    except Exception:
        val = ""
    curses.noecho()
    curses.curs_set(0)
    return val or default


def confirm_scope(stdscr, target):
    ans = prompt(stdscr,
                 f"Authorized to scan {target}?  type YES:")
    return ans.strip().upper() == "YES"


# -------------------------------------------------------------- the actions --
NMAP_PROFILES = {
    "1": ("Quick  (top 100 ports)",          "nmap -T4 -F {t}"),
    "2": ("Standard (top 1000 + versions)",  "nmap -T4 -sV {t}"),
    "3": ("Deep   (all ports + scripts)",    "nmap -T4 -p- -sV -sC {t}"),
    "4": ("Ping sweep (who's alive)",        "nmap -sn {t}"),
}


def act_recon(stdscr):
    suggested = primary_ip().rsplit(".", 1)[0] + ".0/24"
    target = prompt(stdscr, "Target (ip / host / cidr):", suggested)
    if not target:
        return
    if not confirm_scope(stdscr, target):
        flash(stdscr, "ABORTED - scope not confirmed", FACES["angry"])
        return
    # pick profile
    lines = ["CHOOSE SCAN:"] + [f"  {k}  {v[0]}" for k, v in NMAP_PROFILES.items()]
    choice = pick(stdscr, lines, list(NMAP_PROFILES.keys()))
    if not choice:
        return
    cmd = NMAP_PROFILES[choice][1].format(t=target)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe = target.replace("/", "_").replace(":", "_")
    outfile = LOOT_DIR / f"nmap_{safe}_{stamp}.txt"

    def go():
        print(f"\033[1;32m>>> {cmd}\033[0m\n")
        subprocess.run(f"{cmd} | tee {outfile}", shell=True)
        print(f"\n\033[1;36msaved -> {outfile}\033[0m")

    run_in_terminal(stdscr, go)


def act_exploit(stdscr):
    opts = [
        "EXPLOIT MENU:",
        "  1  searchsploit (offline exploit-db)",
        "  2  msfconsole (Metasploit)",
        "  3  back",
    ]
    c = pick(stdscr, opts, ["1", "2", "3"])
    if c == "1":
        term = prompt(stdscr, "searchsploit terms:")
        if term:
            run_in_terminal(stdscr, lambda: subprocess.run(
                f"searchsploit {term}", shell=True))
    elif c == "2":
        run_in_terminal(stdscr, lambda: subprocess.run("msfconsole", shell=True))


def act_wifi(stdscr):
    def go():
        print("\033[1;32m== interfaces ==\033[0m")
        subprocess.run("ip -brief addr", shell=True)
        print("\n\033[1;32m== nearby (iwlist scan, needs root) ==\033[0m")
        subprocess.run(
            "iwlist scan 2>/dev/null | grep -E 'ESSID|Signal|Channel' | head -40",
            shell=True)
    run_in_terminal(stdscr, go)


def act_loot(stdscr):
    files = sorted(LOOT_DIR.glob("*.txt"), reverse=True)[:20]
    if not files:
        flash(stdscr, "no loot yet - run a scan", FACES["think"])
        return
    labels = ["LOOT (newest first):"] + [f"  {i+1}  {f.name}" for i, f in enumerate(files)]
    keys = [str(i + 1) for i in range(len(files))]
    c = pick(stdscr, labels, keys)
    if c:
        f = files[int(c) - 1]
        run_in_terminal(stdscr, lambda: subprocess.run(f"less {f}", shell=True))


def act_shell(stdscr):
    shellbin = os.environ.get("SHELL", "/bin/bash")
    run_in_terminal(stdscr, lambda: subprocess.run([shellbin]))


def act_cmd(stdscr, item):
    cmd = item.get("cmd", "")
    if not cmd:
        return
    if item.get("needs_scope"):
        tgt = prompt(stdscr, "Target:")
        if not tgt or not confirm_scope(stdscr, tgt):
            flash(stdscr, "ABORTED", FACES["angry"])
            return
        cmd = cmd.replace("{t}", tgt).replace("{target}", tgt)
    run_in_terminal(stdscr, lambda: subprocess.run(cmd, shell=True))


# ------------------------------------------------------------ small widgets --
def flash(stdscr, msg, face="(o_o)", secs=1.3):
    h, w = stdscr.getmaxyx()
    stdscr.move(h - 2, 0); stdscr.clrtoeol()
    stdscr.addstr(h - 2, 0, f"{face}  {msg}"[: w - 1], curses.A_BOLD)
    stdscr.refresh()
    time.sleep(secs)


def pick(stdscr, lines, keys):
    """Blocking sub-menu: draw lines, return the key pressed (or None)."""
    h, w = stdscr.getmaxyx()
    stdscr.clear()
    for i, ln in enumerate(lines):
        if i < h - 1:
            attr = curses.A_BOLD if i == 0 else curses.A_NORMAL
            stdscr.addstr(i, 0, ln[: w - 1], attr)
    stdscr.addstr(min(len(lines) + 1, h - 1), 0, "(esc to cancel)"[: w - 1],
                  curses.A_DIM)
    stdscr.refresh()
    while True:
        ch = stdscr.getch()
        if ch in (27, ord("q")):
            return None
        try:
            c = chr(ch)
        except ValueError:
            continue
        if c in keys:
            return c


# ------------------------------------------------------------- main UI loop --
def draw(stdscr, items, sel, state, tick):
    h, w = stdscr.getmaxyx()
    stdscr.erase()
    C = curses.color_pair

    # top bar
    top = " ALL YOUR BASE "
    right = f"{state['batt']} {time.strftime('%H:%M')} "
    stdscr.addstr(0, 0, top[: w - 1], C(1) | curses.A_BOLD)
    if len(right) < w:
        stdscr.addstr(0, w - len(right) - 1, right, C(1))

    # mascot + identity
    face = FACES.get(state["mood"], FACES["idle"])
    stdscr.addstr(2, 1, face, C(2) | curses.A_BOLD)
    stdscr.addstr(2, 12, "ZeroBase", C(2) | curses.A_BOLD)
    stdscr.addstr(3, 1, "C A T S", C(1))
    info = f"{state['iface']}  {state['ip']}"
    stdscr.addstr(3, 12, info[: w - 13], C(3))

    # menu
    base = 5
    for i, it in enumerate(items):
        y = base + i
        if y >= h - 2:
            break
        marker = ">" if i == sel else " "
        line = f"{marker} {it['key']} {it['label']:<9} {it['desc']}"
        attr = (C(2) | curses.A_BOLD) if i == sel else curses.A_NORMAL
        stdscr.addstr(y, 0, line[: w - 1], attr)

    # footer ticker
    q = QUOTES[(tick // 20) % len(QUOTES)]
    stdscr.addstr(h - 1, 0, q[: w - 1], C(1) | curses.A_DIM)
    stdscr.refresh()


def refresh_state(state):
    state["ip"] = primary_ip()
    state["iface"] = default_iface()
    state["batt"] = battery()


def main(stdscr):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_CYAN, -1)
    stdscr.nodelay(True)
    stdscr.timeout(100)

    items = load_menu()
    sel = 0
    tick = 0
    state = {"mood": "idle", "ip": "...", "iface": "...", "batt": "--"}
    refresh_state(state)

    dispatch = {
        "recon": act_recon, "exploit": act_exploit, "wifi": act_wifi,
        "loot": act_loot, "shell": act_shell,
    }

    while True:
        draw(stdscr, items, sel, state, tick)
        tick += 1
        if tick % 100 == 0:          # periodic status refresh (~10s)
            refresh_state(state)
        ch = stdscr.getch()
        if ch == -1:
            continue

        if ch in (ord("q"), ord("0")):
            break
        elif ch in (curses.KEY_DOWN, ord("j")):
            sel = (sel + 1) % len(items)
        elif ch in (curses.KEY_UP, ord("k")):
            sel = (sel - 1) % len(items)
        elif ch == ord("r"):
            refresh_state(state)
            flash(stdscr, "status refreshed", FACES["happy"], 0.6)
        elif ch in (curses.KEY_ENTER, 10, 13, ord("l"), curses.KEY_RIGHT):
            activate(stdscr, items[sel], dispatch, state)
        else:
            # number hotkeys
            try:
                c = chr(ch)
            except ValueError:
                continue
            for i, it in enumerate(items):
                if it["key"] == c:
                    sel = i
                    activate(stdscr, it, dispatch, state)
                    break


def activate(stdscr, item, dispatch, state):
    act = item["action"]
    if act == "quit":
        raise SystemExit
    state["mood"] = "busy"
    draw_busy(stdscr, state)
    try:
        if act == "cmd":
            act_cmd(stdscr, item)
        elif act in dispatch:
            dispatch[act](stdscr)
    finally:
        state["mood"] = "idle"


def draw_busy(stdscr, state):
    h, w = stdscr.getmaxyx()
    stdscr.addstr(2, 1, FACES["busy"], curses.color_pair(2) | curses.A_BOLD)
    stdscr.refresh()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except (KeyboardInterrupt, SystemExit):
        pass
    os.system("clear")
    print("CATS: YOU HAVE NO CHANCE TO SURVIVE MAKE YOUR TIME. (bye)")
