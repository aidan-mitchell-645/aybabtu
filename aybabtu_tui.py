#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[fallback TUI] 
AYBABTU  --  A pwnagotchi-style launcher skinned in "All Your Base" glory.
Built for the Beepy (Pi Zero 2W + BlackBerry keyboard) running Kali in the
framebuffer console. Pure-stdlib curses: no pip installs, no X, no fuss.

Features:
  * CATS-cat mascot that changes expression as it works (see faces.py)
  * RECON -> nmap (scope-gated, auto-saved to loot/) that chains straight
    into exploit leads via searchsploit (see campaign.py)
  * Live battery gauge + DOCTOR self-check (see hw.py)

Controls:
    j / k  or  up/down     move            r   refresh status
    number keys            jump to item    q/0 quit
    Enter / l / right      select          esc back out of a sub-menu
"""

import curses
import json
import os
import socket
import subprocess
import time
from pathlib import Path

import campaign
import faces
import hw

VERSION = "0.2"
HERE = Path(__file__).resolve().parent
MENU_FILE = HERE / "menu.json"
LOOT_DIR = Path(os.environ.get("AYBABTU_LOOT", HERE / "loot"))
LOOT_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------- box utilities --
def sh(cmd):
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
    parts = sh("ip route show default").split()
    return parts[parts.index("dev") + 1] if "dev" in parts else "none"


# ---------------------------------------------------------------- menu model --
def builtin_menu():
    return [
        {"key": "1", "label": "RECON",    "desc": "nmap -> exploit leads", "action": "recon"},
        {"key": "2", "label": "EXPLOIT",  "desc": "msf / searchsploit",    "action": "exploit"},
        {"key": "3", "label": "WIFI",     "desc": "interfaces & monitor",  "action": "wifi"},
        {"key": "4", "label": "LOOT",     "desc": "saved scan output",     "action": "loot"},
        {"key": "5", "label": "TERMINAL", "desc": "drop to a real shell",  "action": "shell"},
        {"key": "9", "label": "DOCTOR",   "desc": "hardware self-check",   "action": "doctor"},
    ]


def load_menu():
    items = builtin_menu()
    if MENU_FILE.exists():
        try:
            extra = json.loads(MENU_FILE.read_text())
            for e in extra.get("tools", []):
                items.append({
                    "key": e.get("key", "?"), "label": e.get("label", "TOOL"),
                    "desc": e.get("desc", ""), "action": "cmd",
                    "cmd": e.get("cmd", ""), "needs_scope": e.get("needs_scope", False),
                })
        except Exception:
            pass
    items.append({"key": "0", "label": "QUIT", "desc": "", "action": "quit"})
    return items


# -------------------------------------------------------------- shell escape --
def run_in_terminal(stdscr, fn):
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


# --------------------------------------------------------------- small input --
def prompt(stdscr, question, default=""):
    curses.curs_set(1); curses.echo()
    h, w = stdscr.getmaxyx()
    stdscr.move(h - 2, 0); stdscr.clrtoeol()
    stdscr.addstr(h - 2, 0, (question + " ")[: w - 1], curses.A_BOLD)
    stdscr.refresh()
    try:
        val = stdscr.getstr(h - 2, min(len(question) + 1, w - 2), 80)
        val = val.decode("utf-8", "ignore").strip()
    except Exception:
        val = ""
    curses.noecho(); curses.curs_set(0)
    return val or default


def confirm_scope(stdscr, target):
    return prompt(stdscr, f"Authorized to scan {target}? type YES:").strip().upper() == "YES"


def flash(stdscr, msg, secs=1.2):
    h, w = stdscr.getmaxyx()
    stdscr.move(h - 2, 0); stdscr.clrtoeol()
    stdscr.addstr(h - 2, 0, msg[: w - 1], curses.A_BOLD | curses.color_pair(1))
    stdscr.refresh()
    time.sleep(secs)


def pick(stdscr, title, rows, keys):
    """Blocking sub-menu. rows parallel to keys; returns a key or None."""
    h, w = stdscr.getmaxyx()
    stdscr.clear()
    stdscr.addstr(0, 0, title[: w - 1], curses.A_BOLD | curses.color_pair(2))
    for i, r in enumerate(rows):
        if 2 + i < h - 1:
            stdscr.addstr(2 + i, 0, r[: w - 1])
    stdscr.addstr(h - 1, 0, "(esc to cancel)"[: w - 1], curses.A_DIM)
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


# -------------------------------------------------------------- the actions --
NMAP_PROFILES = {
    "1": ("Quick   (top 100 ports)",        "nmap -T4 -F {t}"),
    "2": ("Standard(top 1000 + versions)",  "nmap -T4 -sV {t}"),
    "3": ("Deep    (all ports +scripts)",   "nmap -T4 -p- -sV -sC {t}"),
    "4": ("Ping sweep (who's alive)",       "nmap -sn {t}"),
}


def act_recon(stdscr, state):
    suggested = primary_ip().rsplit(".", 1)[0] + ".0/24"
    target = prompt(stdscr, "Target (ip/host/cidr):", suggested)
    if not target:
        return
    if not confirm_scope(stdscr, target):
        state["mood"] = "fail"; flash(stdscr, "ABORTED - scope not confirmed"); return

    rows = [f"  {k}  {v[0]}" for k, v in NMAP_PROFILES.items()]
    choice = pick(stdscr, "CHOOSE SCAN:", rows, list(NMAP_PROFILES.keys()))
    if not choice:
        return
    cmd = NMAP_PROFILES[choice][1].format(t=target)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe = target.replace("/", "_").replace(":", "_")
    outfile = LOOT_DIR / f"nmap_{safe}_{stamp}.txt"

    state["mood"] = "scanning"

    def go():
        print(f"\033[1;32m>>> {cmd}\033[0m\n")
        subprocess.run(f"{cmd} | tee {outfile}", shell=True)
        print(f"\n\033[1;36msaved -> {outfile}\033[0m")
    run_in_terminal(stdscr, go)

    # ----- campaign chaining: parse what we just found -----
    try:
        text = outfile.read_text()
    except Exception:
        text = ""
    services = campaign.parse_nmap(text)
    if not services:
        state["mood"] = "empty"; flash(stdscr, "no open services parsed"); return
    state["mood"] = "hit"
    act_campaign(stdscr, state, services)


def act_campaign(stdscr, state, services):
    leads = campaign.suggest_terms(services)
    if not leads:
        return
    leads = leads[:8]
    rows = [f"  {i+1}  {l['term']:<16} <- {l['why']}"[:78]
            for i, l in enumerate(leads)]
    keys = [str(i + 1) for i in range(len(leads))]
    title = f"OPEN: {len(services)} svc  |  pick a lead to hunt exploits:"
    c = pick(stdscr, title, rows, keys)
    if not c:
        return
    lead = leads[int(c) - 1]
    state["mood"] = "pwn"
    how = pick(stdscr, f"HUNT '{lead['term']}' via:",
               ["  1  searchsploit (offline exploit-db)",
                "  2  msfconsole search",
                "  3  back"], ["1", "2", "3"])
    if how == "1":
        run_in_terminal(stdscr, lambda: subprocess.run(
            f"searchsploit {lead['term']}", shell=True))
    elif how == "2":
        q = lead["term"].replace("'", "")
        run_in_terminal(stdscr, lambda: subprocess.run(
            f"msfconsole -q -x 'search {q}; exit'", shell=True))


def act_exploit(stdscr, state):
    c = pick(stdscr, "EXPLOIT:",
             ["  1  searchsploit (offline exploit-db)",
              "  2  msfconsole (Metasploit)", "  3  back"], ["1", "2", "3"])
    if c == "1":
        term = prompt(stdscr, "searchsploit terms:")
        if term:
            run_in_terminal(stdscr, lambda: subprocess.run(
                f"searchsploit {term}", shell=True))
    elif c == "2":
        state["mood"] = "pwn"
        run_in_terminal(stdscr, lambda: subprocess.run("msfconsole", shell=True))


def act_wifi(stdscr, state):
    def go():
        print("\033[1;32m== interfaces ==\033[0m")
        subprocess.run("ip -brief addr", shell=True)
        print("\n\033[1;32m== nearby APs ==\033[0m")
        subprocess.run(
            "iwlist scan 2>/dev/null | grep -E 'ESSID|Signal|Channel' | head -40",
            shell=True)
    run_in_terminal(stdscr, go)


def act_loot(stdscr, state):
    files = sorted(LOOT_DIR.glob("*.txt"), reverse=True)[:20]
    if not files:
        state["mood"] = "empty"; flash(stdscr, "no loot yet - run a scan"); return
    rows = [f"  {i+1}  {f.name}" for i, f in enumerate(files)]
    keys = [str(i + 1) for i in range(len(files))]
    c = pick(stdscr, "LOOT (newest first):", rows, keys)
    if c:
        f = files[int(c) - 1]
        run_in_terminal(stdscr, lambda: subprocess.run(f"less {f}", shell=True))


def act_shell(stdscr, state):
    shellbin = os.environ.get("SHELL", "/bin/bash")
    run_in_terminal(stdscr, lambda: subprocess.run([shellbin]))


def act_doctor(stdscr, state):
    def go():
        print("\033[1;32m== AYBABTU DOCTOR ==\033[0m\n")
        for label, status, detail in hw.doctor():
            color = "32" if status == "OK" else ("33" if status == "??" else "31")
            print(f"  \033[1;{color}m[{status:>2}]\033[0m {label:<13} {detail}")
        if hw.battery_percent() is None:
            print("\n\033[1;33mBattery gauge not found.\033[0m Install the keyboard driver:")
            print("  git clone https://github.com/ardangelo/beepy-kbd")
            print("  cd beepy-kbd && make && sudo make install && sudo reboot")
            print("  -> creates /sys/firmware/beepy/battery_percent")
    run_in_terminal(stdscr, go)


def act_cmd(stdscr, state, item):
    cmd = item.get("cmd", "")
    if not cmd:
        return
    if item.get("needs_scope"):
        tgt = prompt(stdscr, "Target:")
        if not tgt or not confirm_scope(stdscr, tgt):
            state["mood"] = "fail"; flash(stdscr, "ABORTED"); return
        cmd = cmd.replace("{t}", tgt).replace("{target}", tgt)
    run_in_terminal(stdscr, lambda: subprocess.run(cmd, shell=True))


# ------------------------------------------------------------- main UI loop --
def draw(stdscr, items, sel, state, tick):
    h, w = stdscr.getmaxyx()
    stdscr.erase()
    C = curses.color_pair

    # top bar
    stdscr.addstr(0, 0, " ALL YOUR BASE "[: w - 1], C(1) | curses.A_BOLD)
    right = f"{hw.battery_bar()} {state['batt']} {time.strftime('%H:%M')} "
    if len(right) < w:
        stdscr.addstr(0, w - len(right) - 1, right, C(1))

    # mascot (left) + identity (right of it)
    art, say = faces.get(state["mood"], frame=tick // 5)
    for i, line in enumerate(art):
        if 1 + i < h:
            stdscr.addstr(1 + i, 1, line, C(2) | curses.A_BOLD)
    ix = 1 + faces.width() + 2
    if ix < w:
        stdscr.addstr(1, ix, f"ZeroBase v{VERSION}"[: w - ix], C(2) | curses.A_BOLD)
        stdscr.addstr(2, ix, f"{state['iface']} {state['ip']}"[: w - ix], C(3))
        stdscr.addstr(3, ix, say[: w - ix], curses.A_DIM)

    # scrolling menu
    base = 5
    avail = max(1, (h - 1) - base)
    top = 0
    if len(items) > avail:
        top = min(max(0, sel - avail // 2), len(items) - avail)
    for row, i in enumerate(range(top, min(len(items), top + avail))):
        it = items[i]
        y = base + row
        marker = ">" if i == sel else " "
        line = f"{marker} {it['key']} {it['label']:<8} {it['desc']}"
        attr = (C(2) | curses.A_BOLD) if i == sel else curses.A_NORMAL
        stdscr.addstr(y, 0, line[: w - 1], attr)

    # footer taunt
    stdscr.addstr(h - 1, 0, say[: w - 1], C(1) | curses.A_DIM)
    stdscr.refresh()


def refresh_state(state):
    state["ip"] = primary_ip()
    state["iface"] = default_iface()
    state["batt"] = hw.battery_str()


DISPATCH = {
    "recon": act_recon, "exploit": act_exploit, "wifi": act_wifi,
    "loot": act_loot, "shell": act_shell, "doctor": act_doctor,
}


def activate(stdscr, item, state):
    act = item["action"]
    if act == "quit":
        raise SystemExit
    try:
        if act == "cmd":
            act_cmd(stdscr, state, item)
        elif act in DISPATCH:
            DISPATCH[act](stdscr, state)
    finally:
        # drift back to idle after an action unless it set a lasting mood
        if state["mood"] in ("scanning",):
            state["mood"] = "idle"


def main(stdscr):
    curses.curs_set(0)
    curses.start_color(); curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_CYAN, -1)
    stdscr.nodelay(True); stdscr.timeout(100)

    items = load_menu()
    sel, tick = 0, 0
    state = {"mood": "boot", "ip": "...", "iface": "...", "batt": "--"}
    refresh_state(state)
    boot_until = time.time() + 1.5

    while True:
        if state["mood"] == "boot" and time.time() > boot_until:
            state["mood"] = "idle"
        draw(stdscr, items, sel, state, tick)
        tick += 1
        if tick % 100 == 0:
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
            refresh_state(state); flash(stdscr, "status refreshed", 0.5)
        elif ch in (curses.KEY_ENTER, 10, 13, ord("l"), curses.KEY_RIGHT):
            activate(stdscr, items[sel], state)
        else:
            try:
                c = chr(ch)
            except ValueError:
                continue
            for i, it in enumerate(items):
                if it["key"] == c:
                    sel = i
                    activate(stdscr, it, state)
                    break


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except (KeyboardInterrupt, SystemExit):
        pass
    os.system("clear")
    print("CATS: YOU HAVE NO CHANCE TO SURVIVE MAKE YOUR TIME. (bye)")
