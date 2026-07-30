#!/usr/bin/env python3
"""
Proxy Latency Tester — CLI gateway.

Usage:
  python main.py test                    -> Test all proxies (--retry=N for retries)
  python main.py set-proxy               -> Set proxy from text input or file
  python main.py export                  -> Export last test results
  python main.py export --top 10         -> Export top 10 fastest
  python main.py test --top 5 --working  -> Test + auto-export top 5 working proxies
"""

import concurrent.futures
import sys
import argparse
import datetime
import os

from core import config
from core.venv_setup import ensure_venv_import
from core import proxy_db
from core import tester
from core import exporter


def _utf8_safe():
    """Cek apakah terminal support UTF-8 atau gak."""
    if sys.platform == "win32":
        return os.environ.get("PYTHONIOENCODING") == "utf-8" or hasattr(sys.stdout, "encoding") and sys.stdout.encoding and "UTF" in sys.stdout.encoding.upper()
    return True


_USE_UTF = _utf8_safe()
_BAR = "━" if _USE_UTF else "="
_GREEN = "" if not _USE_UTF else "\033[32m"   # hijau biasa
_RED = "" if not _USE_UTF else "\033[31m"       # merah biasa
_CYAN = "" if not _USE_UTF else "\033[36m"      # cyan biasa
_GRN = "" if not _USE_UTF else "\033[92m"       # hijau terang
_RED2 = "" if not _USE_UTF else "\033[91m"      # merah terang
_CYN2 = "" if not _USE_UTF else "\033[96m"      # cyan terang
_YLW = "" if not _USE_UTF else "\033[93m"       # kuning
_DIM = "" if not _USE_UTF else "\033[90m"       # abu-abu
_BOLD = "" if not _USE_UTF else "\033[1m"
_RESET = "" if not _USE_UTF else "\033[0m"


def cmd_test(args, socks_mod):
    proxies = proxy_db.load()
    if not proxies:
        print("[-] No valid proxies to test.")
        return

    retry_count = max(1, args.retry)
    top_n = args.top
    target_url = args.target or config.TEST_URL

    if args.protocol:
        proxies = [p for p in proxies if p["protocol"].upper() == args.protocol.upper()]
        print(f"[i] Filtered by protocol: {args.protocol.upper()} — {len(proxies)} proxies")

    if args.country:
        proxies = [p for p in proxies if p.get("country", "").lower() == args.country.lower()]
        print(f"[i] Filtered by country: {args.country} — {len(proxies)} proxies")

    if not proxies:
        print("[-] No proxies match the filters.")
        return

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(_CYN2 + _BAR * 90 + _RESET)
    print(f"  {_BOLD}{_CYN2}Proxy Latency Test{_RESET} — {now}")
    if top_n > 0:
        print(f"  {_YLW}Mode: top {top_n} fastest only{_RESET}")
    print(_CYN2 + _BAR * 90 + _RESET)

    print(f"  {_DIM}Loaded {len(proxies)} proxies | {config.MAX_WORKERS} threads | {config.TIMEOUT}s timeout | {retry_count}x retry | target: {target_url}{_RESET}")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as ex:
        futures = {ex.submit(tester.test_one_retry, p, socks_mod, retry_count, target_url): p for p in proxies}
        for fut in concurrent.futures.as_completed(futures):
            results.append(fut.result())

    results.sort(key=lambda r: (not r["ok"], r.get("avg_ms") or r.get("ms") or 999999))

    online = [r for r in results if r["ok"]]
    display = online[:top_n] if top_n > 0 else results

    if retry_count > 1:
        print(f"\n{_DIM}{'PROXY':<22} {'PROTO':<6} {'COUNTRY':<22} {'STATUS':<7} {'MIN':<8} {'AVG':<8} {'MAX':<8} {'OK':<6} INFO{_RESET}")
        print(_DIM + _BAR * 110 + _RESET)
        for r in display:
            if r["ok"]:
                status = f"{_GRN}UP{_RESET}"
                min_ms = f"{r['min_ms']:.0f} ms"
                avg_ms = f"{_BOLD}{r['avg_ms']:.0f} ms{_RESET}"
                max_ms = f"{r['max_ms']:.0f} ms"
                ok_str = f"{r['ok_count']}/{r['retry']}"
            else:
                status = f"{_RED2}DOWN{_RESET}"
                min_ms = "-"; avg_ms = "-"; max_ms = "-"; ok_str = f"0/{r['retry']}"
            country = r.get("country") or "-"
            print(f"{_DIM}{r['addr']:<22}{_RESET} {r['protocol']:<6} {country:<22} {status:<7} {min_ms:<8} {avg_ms:<8} {max_ms:<8} {ok_str:<6} {r['info']}")
    else:
        print(f"\n{_DIM}{'PROXY':<25} {'PROTO':<6} {'COUNTRY':<22} {'STATUS':<7} {'LATENCY':<8} {'METHOD':<10} INFO{_RESET}")
        print(_DIM + _BAR * 110 + _RESET)
        for r in display:
            if r["ok"]:
                status = f"{_GRN}UP{_RESET}"
                ms = f"{_BOLD}{r['ms']:.0f} ms{_RESET}" if r["ms"] is not None else "-"
            else:
                status = f"{_RED2}DOWN{_RESET}"
                ms = "-"
            country = r.get("country") or "-"
            print(f"{_DIM}{r['addr']:<25}{_RESET} {r['protocol']:<6} {country:<22} {status:<7} {ms:<8} {r['method']:<10} {r['info']}")

    print(f"\n  {_GRN}Done. {len(online)}/{len(results)} proxies online.{_RESET}")

    exporter.save_results(results)

    if args.working or top_n > 0:
        exporter.export_working(online, max_count=top_n)

    if top_n > 0 and len(online) > top_n:
        print(f"  {_YLW}Top {top_n} of {len(online)} online proxies -> proxies.working.json{_RESET}")
    elif online:
        fastest = online[0]
        lbl = "avg " if retry_count > 1 else ""
        print(f"  {_GRN}Fastest: {fastest['addr']} — {fastest.get('avg_ms', fastest.get('ms')):.0f} ms {lbl}({fastest['protocol']}){_RESET}")


def cmd_set_proxy(args):
    filepath = args.file

    if filepath:
        count = proxy_db.set_proxy_from_file(filepath)
        if count > 0:
            print(f"[+] {count} proxies saved to {config.PROXY_FILE} from '{filepath}'")
        return

    print("=== Set Proxy ===")
    print("Paste proxy text (free format — ip:port, blocks, etc.)")
    print("Press Ctrl+Z then Enter (Windows) or Ctrl+D (Linux/Mac) when done:\n")

    lines = []
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            lines.append(line)
    except KeyboardInterrupt:
        pass

    raw_text = "".join(lines)
    if not raw_text.strip():
        print("[!] No input. Aborted.")
        return

    count = proxy_db.set_proxy_interactive(raw_text)
    if count > 0:
        print(f"\n[+] {count} proxies saved to {config.PROXY_FILE}")


def cmd_export(args):
    if not hasattr(config, 'RESULTS_JSON_FILE') or not __import__('os').path.exists(config.RESULTS_JSON_FILE):
        try:
            with open(config.RESULTS_JSON_FILE) as f:
                import json
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print("[!] No test results found. Run 'python main.py test' first.")
            return

        results = []
        for d in data:
            results.append({
                "addr": d["proxy"],
                "protocol": d.get("protocol", "HTTP"),
                "ok": d.get("status") == "ONLINE",
                "ms": d.get("latency"),
                "avg_ms": d.get("avg_ms"),
                "min_ms": d.get("min_ms"),
                "max_ms": d.get("max_ms"),
                "country": d.get("country", ""),
                "method": d.get("method", ""),
                "info": d.get("info", ""),
            })
    else:
        print("[!] No test results found.")
        return

    online = sorted(
        [r for r in results if r.get("ok")],
        key=lambda r: r.get("avg_ms") or r.get("ms") or 0,
    )

    top_n = args.top
    if top_n > 0:
        online = online[:top_n]
        print(f"[i] Exporting top {top_n} fastest proxies:")

    exporter.save_results(online, config.RESULTS_JSON_FILE)
    exporter.save_results_csv(online, config.RESULTS_CSV_FILE)
    exporter.export_working(online, max_count=top_n)
    print("[+] Export complete.")


def main():
    EPILOG = """
FLAG DETAILS:
  --retry=N
      Send N HTTP requests per proxy instead of 1. Shows min/avg/max latency.
      Higher values give more accurate rankings but take longer.
      Example: --retry 5

  --top=N
      Only show and/or export the N fastest (lowest latency) proxies.
      Automatically saves them to proxies.working.json.
      Example: --top 10

  --working
      Generate proxies.working.json with all online proxies sorted by speed.
      When combined with --top=N, only exports the N fastest.
      This file is ready to plug into other tools (sqlmap, curl, etc.).

  --protocol=PROTO
      Filter proxies by protocol before testing.
      Valid values: HTTP, HTTPS, SOCKS4, SOCKS5
      Example: --protocol HTTP

  --country=NAME
      Filter proxies by country name before testing.
      Uses the "country" field from proxies.json. Case-insensitive.
      Wrap in quotes if the name has spaces, e.g. --country "United States of America"
      Example: --country Germany

  file (positional, set-proxy only)
      Path to a text file containing proxy data. Supports block format
      (ip:port + protocol + status + country + user/pass) and raw line format.
      If omitted, reads from standard input (paste mode).

OUTPUT FILES:
  results.json          Full test results with all metrics
  results.csv           Same results in CSV format
  proxies.working.json  Only online proxies, sorted by latency, ready to use

EXAMPLES:
    python main.py set-proxy proxies.txt       Import from file
    python main.py set-proxy                   Paste interactively
    python main.py test                        Test all proxies
    python main.py test --retry 5              Test with 5 retries for accuracy
    python main.py test --top 10 --working     Test + save 10 fastest
    python main.py test --protocol HTTP --country Germany
    python main.py export                      Export last results
    python main.py export --top 5              Export 5 fastest only
"""
    parser = argparse.ArgumentParser(
        description="Proxy Latency Tester — test, filter, and export proxy latency with real HTTP requests.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_test = sub.add_parser("test", help="Test all proxies", epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    p_test.add_argument("--retry", type=int, default=1, help="Requests per proxy (default: 1). More retries = more accurate min/avg/max.")
    p_test.add_argument("--top", type=int, default=0, help="Only show/save the N fastest proxies. Auto-generates proxies.working.json.")
    p_test.add_argument("--working", action="store_true", help="Generate proxies.working.json with all online proxies sorted by speed.")
    p_test.add_argument("--protocol", help='Filter by protocol before testing. Valid: HTTP, HTTPS, SOCKS4, SOCKS5. Example: --protocol HTTP')
    p_test.add_argument("--country", help='Filter by country before testing. Use quotes for multi-word names, e.g. --country "United States of America"')
    p_test.add_argument("--target", help='Test against a custom URL instead of httpbin.org. Example: --target https://www.hostgator.com.br/')

    p_set = sub.add_parser("set-proxy", help="Import proxies from text or file", epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    p_set.add_argument("file", nargs="?", default=None,
                       help="File containing proxies (block/raw format). If omitted, reads from stdin (paste mode).")

    p_export = sub.add_parser("export", help="Export test results to JSON/CSV", epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    p_export.add_argument("--top", type=int, default=0, help="Only export the N fastest proxies. Generates JSON, CSV, and working.json.")

    args = parser.parse_args()

    if args.command == "set-proxy":
        cmd_set_proxy(args)
        return

    socks_mod = ensure_venv_import()

    if args.command == "test":
        cmd_test(args, socks_mod)
    elif args.command == "export":
        cmd_export(args)


if __name__ == "__main__":
    main()
