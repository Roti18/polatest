# Proxy Latency Tester

Test real proxy latency with actual HTTP requests. Supports HTTP/HTTPS and SOCKS4/SOCKS5.

## Features

- **HTTP/HTTPS** - uses Python's built-in urllib. No extra deps.
- **SOCKS4/SOCKS5** - uses PySocks with per-request sockets (no global monkey-patch). Thread-safe.
- **Auto venv** - auto-creates `.venv` + installs PySocks on first run. No manual setup.
- **Retry** (`--retry=N`) - hits each proxy N times for accurate min/avg/max latency.
- **Top** (`--top=N`) - only keep the N fastest proxies. Auto-saves to `proxies.working.json`.
- **Working** (`--working`) - generates `proxies.working.json` with online proxies sorted by speed.
- **Custom target** (`--target=URL`) - test proxies against any URL instead of httpbin.org.
- **Filter** (`--protocol`, `--country`) - test only a subset of proxies.
- **Bulk import** - paste raw text or load a file. Auto-detects block format and raw line format.

## Commands

### `python main.py set-proxy [file]`

Import proxies from a file or paste interactively.

**From a file** (auto-detects format):
```bash
python main.py set-proxy proxies.txt
```

**Paste interactively:**
```bash
python main.py set-proxy
```

#### Supported import formats

**Block format** (auto-detected):
```
45.3.53.131:3129          <-- ip:port
HTTP                      <-- protocol (optional, default: HTTP)
Online                    <-- status (skipped)
Brazil                    <-- country
qt5dbprrkokv              <-- username (if auth required)

5g9yqk9n1r0vb8f           <-- password (can be in a separate block)

45.3.46.70:3129           <-- next proxy
HTTP
Online
Canada
...
```

**Raw line format:**
```
185.162.231.1:3128
185.162.231.2:3128:user:pass
185.162.231.3:3128
```

### `python main.py test [flags]`

Test all imported proxies.

```bash
python main.py test                          # Test all, 1 request each
python main.py test --retry 5                # 5 requests per proxy (accurate avg)
python main.py test --top 10 --working       # Test + save 10 fastest
python main.py test --protocol HTTP --country "United States of America"  # USA proxies only (quotes! contains spaces)
python main.py test --limit 5 --retry 3 --top 3 --working  # Limit 5 proxy pertama
python main.py test --target "https://www.hostgator.com.br/"  # Custom target
python main.py test --target "https://example.com/page?id=1" --retry 5 --top 10  # SQLi target
```

#### Flags

| Flag | Description |
|------|-------------|
| `--limit=N` | Only test the first N proxies from the list (takes from top of file). Useful for quick checks. |
| `file` (export) | Save export to a custom JSON file instead of default CSV/working. Example: `hasil.json` |
| `--retry=N` | Send N requests per proxy. Shows min/avg/max. Default: 1. Higher = more accurate but slower. |
| `--top=N` | Only show and export the N fastest proxies. Automatically generates `proxies.working.json`. |
| `--working` | Generate `proxies.working.json` with all online proxies sorted by speed. |
| `--protocol=PROTO` | Filter by protocol before testing. Valid: `HTTP`, `HTTPS`, `SOCKS4`, `SOCKS5`. |
| `--country=NAME` | Filter by country before testing. Case-insensitive. **Wrap in quotes if the name has spaces**, e.g. `--country "United States of America"` |
| `--target=URL` | Test against a custom URL instead of `httpbin.org`. Example: `--target "https://www.hostgator.com.br/"` |

#### Output with `--retry=5`

```
PROXY                PROTO  COUNTRY    STATUS   MIN      AVG      MAX      OK     INFO
----------------------------------------------------------------------------------------------------
209.50.182.178:3129  HTTP   Germany    ONLINE   594 ms   663 ms   776 ms   10/10  HTTP 200
65.111.24.175:3129   HTTP   Germany    ONLINE   601 ms   670 ms   792 ms   10/10  HTTP 200
```

### `python main.py export [file] [--top=N]`

Display and export results from the last test without re-testing.

```bash
python main.py export                    # Display all online + export to CSV/working
python main.py export --top 5            # Display top 5 + export to CSV/working
python main.py export hasil.json         # Save all online to hasil.json
python main.py export hasil.json --top 5 # Save top 5 to hasil.json
```

## Output files

| File | Contents |
|------|----------|
| `results.json` | Full test results with all metrics |
| `results.csv` | Spreadsheet format |
| `proxies.working.json` | Only online proxies, sorted by speed, ready to plug into other tools |

## JSON database format (`proxies.json`)

```json
[
  {
    "proxy": "185.162.231.1:3128",
    "protocol": "HTTP",
    "country": "Germany",
    "username": "user",
    "password": "pass"
  }
]
```

Only `"proxy"` is required. Everything else is optional.
Valid protocols: `HTTP`, `HTTPS`, `SOCKS4`, `SOCKS5`.

## Example workflow

```bash
# 1. Import proxies from a file
python main.py set-proxy proxies.txt

# 2. Test all proxies with 5 retries, save top 20
python main.py test --retry 5 --top 20 --working

# 3. Use the top 20 in another tool
curl --proxy http://user:pass@fastest-proxy:3129 https://target.com
```
