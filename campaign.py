# -*- coding: utf-8 -*-
"""
campaign.py -- turn nmap output into exploit leads.

Parses the normal (-sV) nmap output you already capture to loot/, pulls out
open services, and suggests searchsploit terms so RECON flows into EXPLOIT in
one tap. Pure functions, no deps -> trivially testable.
"""

import re

# open-port line, e.g. "80/tcp   open  http    Apache httpd 2.4.41 ((Ubuntu))"
_PORT_RE = re.compile(
    r"^(?P<port>\d+)/(?P<proto>tcp|udp)\s+(?P<state>\S+)\s+(?P<svc>\S+)\s*(?P<ver>.*)$"
)

# services where a generic term is more useful than the raw banner
_SERVICE_HINTS = {
    "microsoft-ds": "smb",
    "netbios-ssn": "smb",
    "ms-wbt-server": "rdp",
    "ssl/http": "http",
    "http-proxy": "http",
    "ipp": "cups",
}

# noise words to drop when building a product search term
_STOP = {
    "httpd", "server", "daemon", "service", "protocol", "linux", "unix",
    "ubuntu", "debian", "windows", "(ubuntu)", "((ubuntu))", "or", "later",
}


def parse_nmap(text):
    """Return a list of open-service dicts from nmap -sV normal output."""
    hosts = []
    found = []
    for line in text.splitlines():
        line = line.rstrip()
        m = _PORT_RE.match(line.strip())
        if not m:
            continue
        if m.group("state") != "open":
            continue
        found.append({
            "port": int(m.group("port")),
            "proto": m.group("proto"),
            "service": m.group("svc"),
            "version": m.group("ver").strip(),
        })
    return found


def _version_bits(ver):
    """Pull a product name + up to 2 version numbers out of a banner string."""
    if not ver:
        return "", ""
    # strip parenthetical notes
    ver = re.sub(r"\(.*?\)", " ", ver)
    tokens = ver.split()
    product_words = []
    version = ""
    for t in tokens:
        if re.match(r"^\d+(\.\d+){0,3}[a-z0-9]*$", t):
            # first thing that looks like a version
            m = re.match(r"^(\d+(?:\.\d+)?)", t)
            version = m.group(1) if m else t
            break
        if t.lower() not in _STOP:
            product_words.append(t)
    product = " ".join(product_words[:2])
    return product.strip(), version.strip()


def suggest_terms(services):
    """Map parsed services -> de-duped searchsploit query strings, ranked."""
    seen = set()
    out = []
    for s in services:
        svc = s["service"].lower()
        product, version = _version_bits(s["version"])

        if product:
            term = f"{product} {version}".strip()
        else:
            term = _SERVICE_HINTS.get(svc, svc)

        term = re.sub(r"\s+", " ", term).strip()
        if not term or term in seen:
            continue
        seen.add(term)
        out.append({
            "term": term,
            "port": s["port"],
            "why": f"{s['port']}/{s['proto']} {s['service']}"
                   + (f"  {s['version']}" if s["version"] else ""),
        })
    return out


if __name__ == "__main__":
    # tiny self-test
    SAMPLE = """\
Starting Nmap 7.94
Nmap scan report for 192.168.1.10
PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 8.2p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp   open  http        Apache httpd 2.4.41 ((Ubuntu))
139/tcp  open  netbios-ssn Samba smbd 4.6.2
443/tcp  open  ssl/http    nginx 1.18.0
3306/tcp open  mysql       MySQL 5.7.33
8080/tcp closed http-proxy
"""
    svcs = parse_nmap(SAMPLE)
    for s in svcs:
        print(s)
    print("---- leads ----")
    for lead in suggest_terms(svcs):
        print(f"[{lead['port']}] searchsploit {lead['term']:<18} <- {lead['why']}")
