#!/usr/bin/env bash
# AYBABTU installer for the Beepy / Kali Pi.
# Copies the launcher into place and (optionally) auto-starts it on the
# console at boot, pwnagotchi-style.
set -euo pipefail

DEST="${AYBABTU_HOME:-$HOME/aybabtu}"
echo "[*] installing AYBABTU -> $DEST"
mkdir -p "$DEST"
cp -v aybabtu.py menu.json "$DEST"/
chmod +x "$DEST/aybabtu.py"

cat <<EOF

[+] installed.

Run it now:
    python3 "$DEST/aybabtu.py"

AUTO-START ON BOOT (so it greets you like a pwnagotchi):
  Option A - launch on tty1 login (simplest). Add to ~/.bash_profile:

    if [ "\$(tty)" = "/dev/tty1" ]; then python3 "$DEST/aybabtu.py"; fi

  Option B - systemd service on tty1. Create /etc/systemd/system/aybabtu.service:

    [Unit]
    Description=AYBABTU launcher
    After=multi-user.target

    [Service]
    Type=simple
    ExecStart=/usr/bin/python3 $DEST/aybabtu.py
    StandardInput=tty
    StandardOutput=tty
    TTYPath=/dev/tty1
    Restart=on-failure
    User=$USER

    [Install]
    WantedBy=multi-user.target

  then:  sudo systemctl enable --now aybabtu

Optional tools that make the menu richer (Kali usually has nmap already):
    sudo apt install -y nmap arp-scan exploitdb metasploit-framework
EOF
