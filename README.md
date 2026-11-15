# AYBABTU

A pwnagotchi-style launcher skinned in *All Your Base Are Belong To Us*, built
for a **Beepy** (Pi Zero 2W + BlackBerry keyboard) running Kali in the
framebuffer console. Pure Python `curses` — no pip installs, no X server.

```
 ALL YOUR BASE                         84%  21:14
 (⌐■_■)  ZeroBase
 C A T S  wlan0  192.168.1.37
 > 1 RECON     nmap a target
   2 EXPLOIT   msf / searchsploit
   3 WIFI      interfaces & monitor
   4 LOOT      saved scan output
   5 TERMINAL  drop to a real shell
   6 WHOAMI    quick box self-check
   0 QUIT
 SOMEBODY SET UP US THE BOMB
```

## Controls
- `j`/`k` or up/down — move
- number keys — jump to an item
- `Enter` / `l` — select
- `r` — refresh IP / battery
- `q` / `0` — quit (back out of sub-menus with `esc`)

## Install on the Pi
```bash
scp -r aybabtu/ kali@<pi-ip>:~/
ssh kali@<pi-ip>
cd aybabtu && ./install.sh
python3 ~/aybabtu/aybabtu.py
```
The installer prints two ways to auto-launch it at boot (tty1 login line, or a
systemd service) so it greets you like a pwnagotchi.

## Adding your own buttons
Edit `menu.json`. `{t}` / `{target}` is replaced with whatever target you type;
set `"needs_scope": true` to force the authorized-target confirmation first.

```json
{ "key": "9", "label": "NIKTO", "desc": "web scan", "needs_scope": true,
  "cmd": "nikto -h {t}" }
```

## Scope / ethics
Recon actions make you type `YES` to confirm the target is yours or you're
authorized to test it. Only scan and exploit things you own or have written
permission to touch.

## Roadmap ideas
- Live mascot that reacts to scan results (open ports = angry CATS)
- Sharp-display framebuffer faces instead of text (like real pwnagotchi)
- Loot browser with per-host notes
- "Campaign" mode: scan -> suggest searchsploit terms from open services
