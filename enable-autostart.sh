#!/usr/bin/env bash
# Simple autostart: run AYBABTU when you log in on the Pi's screen (tty1).
# No systemd, no boot races -- the framebuffer is always up by login time, and
# if the app ever exits/crashes you just land on a normal shell.
#
#   ./enable-autostart.sh            set it up
#   ./enable-autostart.sh --disable  remove it
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
    echo "run this WITHOUT sudo (it edits your shell config):  ./enable-autostart.sh" >&2
    exit 1
fi

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
A="# >>> AYBABTU autostart >>>"
B="# <<< AYBABTU autostart <<<"

strip() { [ -f "$1" ] && sed -i "\|$A|,\|$B|d" "$1" || true; }
append() {
    touch "$1"; strip "$1"
    printf '%s\n' "$A" \
        'if [ "$(tty)" = "/dev/tty1" ]; then' \
        "    sudo python3 \"$APP_DIR/aybabtu.py\"" \
        'fi' "$B" >> "$1"
}

# clean up the old (fragile) systemd boot service if it's still around
if [ -f /etc/systemd/system/aybabtu.service ]; then
    echo "[*] removing old systemd boot service (the one that fought tty1)"
    sudo systemctl disable --now aybabtu.service 2>/dev/null || true
    sudo rm -f /etc/systemd/system/aybabtu.service
    sudo systemctl daemon-reload || true
    sudo systemctl enable --now getty@tty1.service 2>/dev/null || true
fi

if [ "${1:-}" = "--disable" ]; then
    strip "$HOME/.zshrc"; strip "$HOME/.bash_profile"
    echo "[+] autostart removed. (login shell is back to normal)"
    exit 0
fi

append "$HOME/.zshrc"          # Kali's default shell
append "$HOME/.bash_profile"   # in case you use bash

cat <<EOF

[+] done. Log in on the Pi's screen (tty1) and AYBABTU starts automatically.
    (SSH logins are unaffected -- it only triggers on the physical console.)
    Quit the UI with 'q' to get a shell; it restarts next login.

    undo:  $APP_DIR/enable-autostart.sh --disable

Tip: it runs with sudo so the tools have root. To skip the password prompt at
login, you can allow just this one command without a password:
  echo "\$USER ALL=(root) NOPASSWD: \$(command -v python3) $APP_DIR/aybabtu.py" \\
      | sudo tee /etc/sudoers.d/aybabtu >/dev/null && sudo chmod 440 /etc/sudoers.d/aybabtu
EOF
