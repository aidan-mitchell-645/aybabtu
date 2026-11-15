#!/usr/bin/env bash
# AYBABTU installer for the Beepy / Kali Pi.
# Installs the pixel-art graphical launcher and its one dependency (Pillow),
# then prints how to auto-start it on the console at boot.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${AYBABTU_HOME:-$HOME/aybabtu}"
if [ "$SRC" = "$DEST" ]; then
    echo "[*] running from the install dir ($DEST) -- no copy needed"
else
    echo "[*] installing AYBABTU -> $DEST"
    mkdir -p "$DEST"
    cp -v "$SRC"/aybabtu.py "$SRC"/aybabtu_tui.py "$SRC"/actions.py \
          "$SRC"/display.py "$SRC"/gfx.py "$SRC"/faces.py "$SRC"/campaign.py \
          "$SRC"/hw.py "$SRC"/menu.json "$DEST"/
fi
chmod +x "$DEST/aybabtu.py" "$DEST/aybabtu_tui.py"

echo
echo "[*] dependency: Pillow (pixel-art rendering). numpy is optional (faster"
echo "    565 packing). Installing via apt..."
sudo apt-get update -qq || true
sudo apt-get install -y python3-pil python3-numpy python3-evdev || \
    pip3 install --break-system-packages pillow numpy evdev || true

# framebuffer access: writing /dev/fb0 needs the 'video' group (or root)
if ! id -nG "$USER" | grep -qw video; then
    echo "[*] adding $USER to the 'video' group (needed to draw to /dev/fb0)"
    sudo usermod -aG video "$USER" || true
    echo "    -> log out/in (or reboot) for this to take effect."
fi

cat <<EOF

[+] installed.

RUN IT (must be on the console that owns the Sharp display, e.g. tty1):
    python3 "$DEST/aybabtu.py"

  Preview without hardware / over SSH (writes PNG frames to a dir):
    AYBABTU_SIM=/tmp/aybabtu python3 "$DEST/aybabtu.py"
  Pure-text fallback (no graphics):
    python3 "$DEST/aybabtu_tui.py"

AUTO-START ON BOOT (greets you pwnagotchi-style on tty1):
  Add to ~/.bash_profile:
    if [ "\$(tty)" = "/dev/tty1" ]; then python3 "$DEST/aybabtu.py"; fi

  Or a systemd service /etc/systemd/system/aybabtu.service:
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
  then: sudo systemctl enable --now aybabtu

INPUT: by default, when run as root AYBABTU reads the input devices directly
  (evdev) so the Beepy keyboard + trackpad-mapped arrows drive it even over SSH.
    AYBABTU_INPUT=tty    force reading only this terminal (e.g. laptop preview)
    AYBABTU_INPUT=evdev  force device reading
  A left-click (mapped to Tab) selects the highlighted item.

DISPLAY TUNING (if orientation/colours look wrong):
    AYBABTU_ROTATE=90  rotate UI 0/90/180/270 (fix sideways/upside-down)
    AYBABTU_INVERT=1   flip black/white (some mono panels are inverted)
    AYBABTU_FB=/dev/fb1  pick a specific framebuffer
    AYBABTU_NOSCAN=1   disable CRT scanlines
  Run 'python3 $DEST/display.py' to print the detected framebuffer.

BATTERY GAUGE (one-time): install the keyboard driver so the % goes live:
    git clone https://github.com/ardangelo/beepy-kbd
    cd beepy-kbd && make && sudo make install && sudo reboot

Richer menu tools (Kali usually has nmap already):
    sudo apt install -y nmap arp-scan exploitdb metasploit-framework
EOF
