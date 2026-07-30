import csv
import json
from . import config


def save_results(results, filepath=None):
    filepath = filepath or config.RESULTS_JSON_FILE

    data = []
    for r in results:
        entry = {
            "proxy": r["addr"],
            "protocol": r["protocol"],
            "country": r.get("country", ""),
            "status": "ONLINE" if r["ok"] else "DEAD",
            "method": r["method"],
            "info": r.get("info", ""),
        }
        if r.get("retry", 1) > 1:
            entry["avg_ms"] = round(r.get("avg_ms") or 0, 1)
            entry["min_ms"] = round(r.get("min_ms") or 0, 1)
            entry["max_ms"] = round(r.get("max_ms") or 0, 1)
            entry["ok_count"] = r.get("ok_count", 0)
            entry["retry"] = r.get("retry", 1)
            entry["latency"] = round(r.get("avg_ms") or 0, 1)
        else:
            entry["latency"] = round(r.get("ms") or 0, 1) if r.get("ms") else None

        data.append(entry)

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[i] Results saved to {filepath}")


def save_results_csv(results, filepath=None):
    filepath = filepath or config.RESULTS_CSV_FILE
    with open(filepath, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["proxy", "protocol", "country", "status", "latency_ms", "method", "info"])
        for r in results:
            latency = round(r.get("avg_ms") or r.get("ms") or 0, 1) if r["ok"] else ""
            w.writerow([
                r["addr"],
                r["protocol"],
                r.get("country", ""),
                "ONLINE" if r["ok"] else "DEAD",
                latency,
                r["method"],
                r.get("info", ""),
            ])
    print(f"[i] Results saved to {filepath}")


def export_working(results, max_count=0, filepath=None):
    """Generate proxies.working.json — only online proxies, sorted by latency, ready to use."""
    filepath = filepath or config.PROXY_WORKING_FILE
    online = sorted(
        [r for r in results if r["ok"]],
        key=lambda r: r.get("avg_ms") or r.get("ms") or 0,
    )
    if max_count > 0:
        online = online[:max_count]

    data = []
    for r in online:
        latency = round(r.get("avg_ms") or r.get("ms") or 0, 1)
        data.append({
            "proxy": r["addr"],
            "protocol": r["protocol"],
            "country": r.get("country", ""),
            "username": r.get("username", ""),
            "password": r.get("password", ""),
            "latency_ms": latency,
        })

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[i] {len(data)} working proxies saved to {filepath}")

    return data
