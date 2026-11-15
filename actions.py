# -*- coding: utf-8 -*-
"""
actions.py -- what the buttons actually do, as plain console flows.

The graphical UI (aybabtu.py) drops to the text console to run these, so they
use ordinary input()/print()/subprocess and reuse the tested campaign + hw
modules. Each takes the shared `state` dict and may set state['mood'] so the
mascot reflects the outcome when the UI comes back.

Scope rule lives here: recon makes you confirm the target is yours.
"""

import os
import socket
import subprocess
import time
from pathlib import Path

import campaign
import hw

HERE = Path(__file__).resolve().parent
LOOT_DIR = Path(os.environ.get("AYBABTU_LOOT", HERE / "loot"))
LOOT_DIR.mkdir(parents=True, exist_ok=True)

G, C, R, Z = "\033[1;32m", "\033[1;36m", "\033[1;31m", "\033[0m"


def _ask(q, default=""):
    try:
        v = input(f"{G}{q}{Z} ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    return v or default


def _pause():
    try:
        input(f"\n{G}[ Enter to return to AYBABTU ]{Z}")
    except (EOFError, KeyboardInterrupt):
        pass


def _run(cmd):
    print(f"{G}>>> {cmd}{Z}\n")
    subprocess.run(cmd, shell=True)


def _primary_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1)); ip = s.getsockname()[0]; s.close()
        return ip
    except Exception:
        return "0.0.0.0"


def _confirm_scope(target):
    return _ask(f"Authorized to scan {target}? type YES:").upper() == "YES"


NMAP_PROFILES = {
    "1": ("Quick   (top 100 ports)",       "nmap -T4 -F {t}"),
    "2": ("Standard(top 1000 +versions)",  "nmap -T4 -sV {t}"),
    "3": ("Deep    (all ports +scripts)",  "nmap -T4 -p- -sV -sC {t}"),
    "4": ("Ping sweep (who's alive)",      "nmap -sn {t}"),
}


# ------------------------------------------------------------------ recon ----
def recon(state):
    print(f"{C}== RECON =={Z}")
    suggested = _primary_ip().rsplit(".", 1)[0] + ".0/24"
    target = _ask("Target (ip/host/cidr):", suggested)
    if not target:
        return
    if not _confirm_scope(target):
        state["mood"] = "fail"; print(f"{R}aborted - scope not confirmed{Z}"); _pause(); return

    for k, (desc, _) in NMAP_PROFILES.items():
        print(f"  {k}  {desc}")
    prof = _ask("scan #:", "2")
    if prof not in NMAP_PROFILES:
        return
    cmd = NMAP_PROFILES[prof][1].format(t=target)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe = target.replace("/", "_").replace(":", "_")
    outfile = LOOT_DIR / f"nmap_{safe}_{stamp}.txt"
    state["mood"] = "scanning"
    _run(f"{cmd} | tee {outfile}")
    print(f"\n{C}saved -> {outfile}{Z}")

    # ---- campaign chaining ----
    try:
        text = outfile.read_text()
    except Exception:
        text = ""
    services = campaign.parse_nmap(text)
    if not services:
        state["mood"] = "empty"; _pause(); return
    state["mood"] = "hit"
    _campaign(state, services)
    _pause()


def _campaign(state, services):
    leads = campaign.suggest_terms(services)[:8]
    if not leads:
        return
    print(f"\n{G}== {len(services)} open services -> exploit leads =={Z}")
    for i, l in enumerate(leads):
        print(f"  {i+1}  searchsploit {l['term']:<16}  <- {l['why']}")
    pick = _ask("hunt lead # (Enter to skip):")
    if not pick.isdigit() or not (1 <= int(pick) <= len(leads)):
        return
    lead = leads[int(pick) - 1]
    state["mood"] = "pwn"
    how = _ask(f"[1] searchsploit  [2] msf search  '{lead['term']}' ?:", "1")
    if how == "1":
        _run(f"searchsploit {lead['term']}")
    elif how == "2":
        q = lead["term"].replace("'", "")
        _run(f"msfconsole -q -x 'search {q}; exit'")


# ---------------------------------------------------------------- others -----
def exploit(state):
    print(f"{C}== EXPLOIT =={Z}")
    how = _ask("[1] searchsploit  [2] msfconsole:", "1")
    if how == "1":
        term = _ask("searchsploit terms:")
        if term:
            _run(f"searchsploit {term}")
    elif how == "2":
        state["mood"] = "pwn"
        _run("msfconsole")
    _pause()


def wifi(state):
    print(f"{C}== WIFI =={Z}")
    _run("ip -brief addr")
    print()
    _run("iwlist scan 2>/dev/null | grep -E 'ESSID|Signal|Channel' | head -40")
    _pause()


def loot(state):
    files = sorted(LOOT_DIR.glob("*.txt"), reverse=True)[:20]
    if not files:
        state["mood"] = "empty"; print(f"{R}no loot yet{Z}"); _pause(); return
    for i, f in enumerate(files):
        print(f"  {i+1}  {f.name}")
    pick = _ask("view #:")
    if pick.isdigit() and 1 <= int(pick) <= len(files):
        _run(f"less {files[int(pick)-1]}")


def shell(state):
    print(f"{G}dropping to shell. type 'exit' to return to AYBABTU.{Z}\n")
    subprocess.run([os.environ.get("SHELL", "/bin/bash")])


def doctor(state):
    import display
    print(f"{C}== AYBABTU DOCTOR =={Z}\n")
    print(f"  display : {display.Display().info}")
    for label, status, detail in hw.doctor():
        col = "32" if status == "OK" else ("33" if status == "??" else "31")
        print(f"  \033[1;{col}m[{status:>2}]{Z} {label:<13} {detail}")
    if hw.battery_percent() is None:
        print(f"\n{G}Battery gauge missing.{Z} Install the keyboard driver:")
        print("  git clone https://github.com/ardangelo/beepy-kbd")
        print("  cd beepy-kbd && make && sudo make install && sudo reboot")
    _pause()


def run_cmd(state, item):
    cmd = item.get("cmd", "")
    if not cmd:
        return
    if item.get("needs_scope"):
        tgt = _ask("Target:")
        if not tgt or not _confirm_scope(tgt):
            state["mood"] = "fail"; print(f"{R}aborted{Z}"); _pause(); return
        cmd = cmd.replace("{t}", tgt).replace("{target}", tgt)
    _run(cmd)
    _pause()


DISPATCH = {
    "recon": recon, "exploit": exploit, "wifi": wifi,
    "loot": loot, "shell": shell, "doctor": doctor,
}
