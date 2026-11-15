# AYBABTU

A pwnagotchi-style launcher skinned in *All Your Base Are Belong To Us*, built
for a **Beepy** (Pi Zero 2W + BlackBerry keyboard) running Kali in the
framebuffer console. Pure Python `curses` — no pip installs, no X server.

```
 ALL YOUR BASE                       [###--] 84% 21:14
 /\_/\   ZeroBase v0.2
( -.- )  wlan0 192.168.1.37
 >(_)<   ALL YOUR BASE ARE BELONG TO US
 > 1 RECON    nmap -> exploit leads
   2 EXPLOIT  msf / searchsploit
   3 WIFI     interfaces & monitor
   4 LOOT     saved scan output
   5 TERMINAL drop to a real shell
   9 DOCTOR   hardware self-check
   0 QUIT
```

The **CATS cat** changes expression as it works — focused while scanning,
happy when it finds open ports, wired when there are exploits to hunt.

## Controls
- `j`/`k` or up/down — move · number keys — jump · `Enter`/`l` — select
- `r` — refresh IP/battery · `q`/`0` — quit · `esc` — back out of a sub-menu

## What the buttons do
- **RECON** — pick a target (scope-confirmed), choose an nmap profile, scan.
  Output auto-saves to `loot/`, then AYBABTU **parses the open services and
  offers one-tap exploit leads** (searchsploit / msfconsole search). Recon
  flows straight into exploit.
- **EXPLOIT** — searchsploit lookup or drop into msfconsole.
- **WIFI** — interfaces + nearby APs.
- **LOOT** — browse saved scans in `less`.
- **TERMINAL** — real shell, returns to the UI on exit.
- **DOCTOR** — self-check: battery, display, i2c, wifi, and which tools are
  installed. Tells you how to fix anything missing.

## Install on the Pi
```bash
git clone https://github.com/aidan-mitchell-645/aybabtu.git
cd aybabtu && ./install.sh
python3 ~/aybabtu/aybabtu.py
```
The installer prints two ways to auto-launch at boot (tty1 login line, or a
systemd service) so it greets you pwnagotchi-style.

## Battery gauge (one-time driver setup)
The battery lives on the keyboard's RP2040. If `DOCTOR` says the gauge is
missing, install the Beepy keyboard driver — it publishes
`/sys/firmware/beepy/battery_percent`, which AYBABTU reads automatically:
```bash
git clone https://github.com/ardangelo/beepy-kbd
cd beepy-kbd && make && sudo make install && sudo reboot
```

## Files
| file          | role                                            |
|---------------|-------------------------------------------------|
| `aybabtu.py`  | main curses UI + actions                        |
| `faces.py`    | the CATS mascot + mood/taunt engine             |
| `campaign.py` | nmap output parser → searchsploit lead suggester|
| `hw.py`       | battery gauge + `doctor()` hardware self-check   |
| `menu.json`   | your custom buttons (no coding needed)          |

## Adding your own buttons
Edit `menu.json`. `{t}`/`{target}` is replaced with the target you type; set
`"needs_scope": true` to force the authorized-target confirm first.
```json
{ "key": "8", "label": "NIKTO", "desc": "web scan", "needs_scope": true,
  "cmd": "nikto -h {t}" }
```

## Scope / ethics
Recon makes you type `YES` to confirm the target is yours or you're authorized
to test it. Only scan and exploit what you own or have written permission to touch.

## Roadmap
- True framebuffer bitmap faces as an idle "screensaver" mode
- Per-host loot notes & a campaign history view
- Signal-strength driven mood (weak wifi = grumpy CATS)
