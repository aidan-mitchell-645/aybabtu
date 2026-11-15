#!/usr/bin/env bash
# Install AYBABTU as a boot service that owns tty1 (pwnagotchi-style).
# Run with sudo from inside the repo:   sudo ./enable-boot.sh
# Undo with:                            sudo ./enable-boot.sh --disable
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
UNIT=/etc/systemd/system/aybabtu.service

if [ "${1:-}" = "--disable" ]; then
    echo "[*] disabling AYBABTU boot service"
    systemctl disable --now aybabtu.service 2>/dev/null || true
    rm -f "$UNIT"
    systemctl daemon-reload
    systemctl enable --now getty@tty1.service   # restore the login prompt
    echo "[+] done. tty1 login prompt restored."
    exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "run me with sudo:  sudo ./enable-boot.sh" >&2
    exit 1
fi

echo "[*] installing $UNIT  (app: $APP_DIR)"
cat > "$UNIT" <<EOF
[Unit]
Description=AYBABTU launcher
After=systemd-user-sessions.service getty@tty1.service
Conflicts=getty@tty1.service
# never stop retrying (don't fall into a dead state that blanks the screen)
StartLimitIntervalSec=0

[Service]
Type=simple
# wait for the framebuffer to actually exist before starting (fixes blank
# screen when the service races the display driver at boot)
ExecStartPre=/bin/sh -c 'for i in \$(seq 1 60); do [ -s /sys/class/graphics/fb0/virtual_size ] && exit 0; sleep 0.5; done; exit 0'
ExecStart=/usr/bin/python3 $APP_DIR/aybabtu.py
WorkingDirectory=$APP_DIR
User=root
Restart=always
RestartSec=2
# own the console so "drop to terminal" and tool output work on the screen
StandardInput=tty
StandardOutput=tty
StandardError=journal
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes

[Install]
WantedBy=multi-user.target
EOF

echo "[*] stepping the login prompt aside on tty1"
systemctl disable --now getty@tty1.service 2>/dev/null || true

echo "[*] enabling + starting AYBABTU"
systemctl daemon-reload
systemctl enable --now aybabtu.service

cat <<EOF

[+] done. AYBABTU now starts on boot and owns the Pi's screen (tty1).

  status:   sudo systemctl status aybabtu
  stop now: sudo systemctl stop aybabtu
  logs:     journalctl -u aybabtu -b
  UNDO:     sudo $APP_DIR/enable-boot.sh --disable

SSH still works independently, so you can always get in to manage it.
EOF
