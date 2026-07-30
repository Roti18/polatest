import json
import sys
import os
from . import config


def load(filepath=None):
    filepath = filepath or config.PROXY_FILE
    if not os.path.exists(filepath):
        print(f"[!] File '{filepath}' not found.")
        if filepath == config.PROXY_FILE:
            print(f"    Import proxies first: python main.py set-proxy [file]")
        sys.exit(1)

    with open(filepath, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[!] Invalid JSON in {filepath}: {e}")
            sys.exit(1)

    if not isinstance(data, list):
        print("[!] proxies.json must be a JSON array.")
        sys.exit(1)

    proxies = []
    for entry in data:
        addr = entry.get("proxy", "").strip()
        if not addr or ":" not in addr:
            continue
        proxies.append({
            "addr": addr,
            "protocol": (entry.get("protocol") or "HTTP").upper(),
            "country": _shorten_country(entry.get("country", "")),
            "username": entry.get("username", ""),
            "password": entry.get("password", ""),
        })

    return proxies


def save(proxies, filepath=None):
    filepath = filepath or config.PROXY_FILE
    seen = set()
    unique = []
    for p in proxies:
        addr = p.get("addr") or p.get("proxy", "")
        if addr in seen:
            continue
        seen.add(addr)
        unique.append({
            "proxy": addr,
            "protocol": p.get("protocol", "HTTP").upper(),
            "country": p.get("country", ""),
            "username": p.get("username", ""),
            "password": p.get("password", ""),
        })

    with open(filepath, "w") as f:
        json.dump(unique, f, indent=2)
    return len(unique)


# ─── HELPERS ──────────────────────────────────────────────


def _is_ip_port(s):
    if ":" not in s:
        return False
    try:
        int(s.rsplit(":", 1)[1])
        return True
    except ValueError:
        return False


def _is_protocol(s):
    return s.upper() in ("HTTP", "HTTPS", "SOCKS4", "SOCKS5")


def _is_status(s):
    return s.upper() in ("ONLINE", "OFFLINE", "DEAD", "ALIVE")


_COUNTRY_SHORT = {
    "united states of america": "USA",
    "united states": "USA",
    "united kingdom": "UK",
    "south korea": "South Korea",
    "united arab emirates": "UAE",
    "antigua & barbuda": "Antigua",
    "trinidad & tobago": "Trinidad",
    "dominican republic": "Dominican Rep",
    "bosnia & herzegovina": "Bosnia",
    "czech republic": "Czechia",
    "costa rica": "Costa Rica",
    "saudi arabia": "Saudi Arabia",
    "new zealand": "New Zealand",
    "south africa": "South Africa",
    "hong kong": "Hong Kong",
    "puerto rico": "Puerto Rico",
    "papua new guinea": "Papua N Guinea",
}


def _shorten_country(name):
    if not name:
        return name
    lower = name.strip().lower()
    if lower in _COUNTRY_SHORT:
        return _COUNTRY_SHORT[lower]
    return name


def _clean(s):
    return s.strip().strip('"').strip("'").strip(",")


# ─── RAW PASTE (one line = one proxy) ────────────────────


def parse_pasted(text):
    """Parse raw pasted text — each line with ip:port becomes a proxy entry.
    Supports: ip:port, ip:port:user:pass."""
    proxies = []
    for line in text.replace("\t", "\n").replace(",", "\n").split("\n"):
        token = _clean(line)
        if not token or token in ("[", "]", "{", "}", "proxy", "PROXY"):
            continue
        if ":" not in token:
            continue

        seg = token.split(":")
        try:
            int(seg[1])
        except ValueError:
            continue

        entry = {"proxy": f"{seg[0]}:{seg[1]}", "protocol": "HTTP", "country": "", "username": "", "password": ""}
        if len(seg) >= 4 and seg[2] and seg[3]:
            entry["username"] = seg[2]
            entry["password"] = seg[3]
        proxies.append(entry)

    return proxies


# ─── BLOCK FORMAT ────────────────────────────────────────
#
# 45.3.53.131:3129
# HTTP
# Online
# Brazil
# qt5dbprrkokv
#                              <- blank line
# 5g9yqk9n1r0vb8f
#                              <- blank line
# 45.3.46.70:3129 ...
#
# Password line may sit in its own block separated by blank lines.


def parse_block(text):
    """State-machine parser for block-format proxies. Thread-safe, no globals."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    proxies = []
    current = None
    pending_pass = None

    for raw in lines:
        line = _clean(raw)
        if not line:
            if current and not current.get("_pass_set"):
                current["_need_pass"] = True
            continue

        if _is_ip_port(line):
            if current and current.get("_valid"):
                proxies.append(current)
            elif pending_pass and pending_pass.get("_valid"):
                pending_pass["password"] = line
                proxies.append(pending_pass)
                pending_pass = None

            current = {
                "proxy": line,
                "protocol": "HTTP",
                "country": "",
                "username": "",
                "password": "",
                "_valid": True,
                "_need_pass": False,
                "_pass_set": False,
            }
            continue

        if not current:
            if pending_pass and not pending_pass["password"]:
                pending_pass["password"] = line
                proxies.append(pending_pass)
                pending_pass = None
            continue

        if _is_protocol(line):
            current["protocol"] = line.upper()
        elif _is_status(line):
            pass
        elif not current["country"]:
            current["country"] = _shorten_country(line)
        elif not current["username"]:
            current["username"] = line
        elif not current["password"]:
            current["password"] = line
            current["_pass_set"] = True
            current["_need_pass"] = False

        current["_need_pass"] = False

    if current and current.get("_valid"):
        proxies.append(current)

    for p in proxies:
        p.pop("_valid", None)
        p.pop("_need_pass", None)
        p.pop("_pass_set", None)
        p.pop("_field_idx", None)

    return proxies


# ─── FILE PARSER (auto-detect) ─────────────────────────


def parse_file(filepath):
    if not os.path.exists(filepath):
        print(f"[!] File '{filepath}' not found.")
        return []

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    if not text.strip():
        return []

    lines = text.split("\n")
    block_hits = 0
    total_ips = 0
    for i, line in enumerate(lines):
        c = _clean(line)
        if _is_ip_port(c):
            total_ips += 1
            if i + 1 < len(lines) and _is_protocol(_clean(lines[i + 1])):
                block_hits += 1

    if total_ips > 0 and block_hits >= total_ips * 0.5:
        return parse_block(text)
    return parse_pasted(text)


# ─── PUBLIC API ─────────────────────────────────────────


def set_proxy_interactive(raw_text, filepath=None):
    parsed = parse_pasted(raw_text)
    if not parsed:
        print("[!] No valid proxies found in input.")
        return 0

    count = save(parsed, filepath or config.PROXY_FILE)
    print(f"[i] Saved {count} proxies to {filepath or config.PROXY_FILE}")
    return count


def set_proxy_from_file(filepath, out_file=None):
    proxies = parse_file(filepath)
    if not proxies:
        print(f"[!] No valid proxies found in '{filepath}'.")
        return 0

    out = out_file or config.PROXY_FILE
    count = save(proxies, out)
    print(f"[i] Saved {count} proxies from '{filepath}' to '{out}'")
    return count
