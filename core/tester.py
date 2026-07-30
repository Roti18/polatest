import socket
import time
import urllib.request
import urllib.error
import http.client
import ssl
from . import config


def http_proxy_test(proxy, target_url=None):
    addr = proxy["addr"]
    user = proxy["username"]
    pwd = proxy["password"]
    url = target_url or config.TEST_URL

    if user and pwd:
        proxy_url = f"http://{user}:{pwd}@{addr}"
    else:
        proxy_url = f"http://{addr}"

    handler = urllib.request.ProxyHandler({
        "http": proxy_url,
        "https": proxy_url,
    })
    opener = urllib.request.build_opener(handler)

    # Header biar mirip browser asli, biar gak kena WAF/403
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Cache-Control": "no-cache",
    }

    req = urllib.request.Request(url, headers=headers)

    start = time.time()
    try:
        with opener.open(req, timeout=config.TIMEOUT) as resp:
            resp.read(200)
            elapsed = (time.time() - start) * 1000
            return True, elapsed, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - start) * 1000
        return True, elapsed, f"HTTP {e.code}"
    except Exception as e:
        return False, None, str(e)


def socks_proxy_test(proxy, socks_mod, target_url=None):
    addr = proxy["addr"]
    user = proxy["username"]
    pwd = proxy["password"]
    url = target_url or config.TEST_URL
    host, port_str = addr.rsplit(":", 1)
    port = int(port_str)
    proto = proxy["protocol"]
    socks_proto = socks_mod.SOCKS5 if proto == "SOCKS5" else socks_mod.SOCKS4
    proxy_auth = (user or None, pwd or None)

    class SocksHTTPConnection(http.client.HTTPConnection):
        def connect(self):
            self.sock = socks_mod.socksocket()
            self.sock.set_proxy(socks_proto, host, port, username=proxy_auth[0], password=proxy_auth[1])
            self.sock.settimeout(config.TIMEOUT)
            self.sock.connect((self.host, self.port))

    class SocksHTTPSConnection(http.client.HTTPSConnection):
        def connect(self):
            self.sock = socks_mod.socksocket()
            self.sock.set_proxy(socks_proto, host, port, username=proxy_auth[0], password=proxy_auth[1])
            self.sock.settimeout(config.TIMEOUT)
            self.sock.connect((self.host, self.port))
            self.sock = ssl.wrap_socket(self.sock, server_hostname=self.host)

    class SocksHTTPHandler(urllib.request.HTTPHandler):
        def http_open(self, req):
            return self.do_open(SocksHTTPConnection, req)

    class SocksHTTPSHandler(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(SocksHTTPSConnection, req)

    opener = urllib.request.build_opener(SocksHTTPHandler, SocksHTTPSHandler)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    req = urllib.request.Request(url, headers=headers)

    start = time.time()
    try:
        with opener.open(req, timeout=config.TIMEOUT) as resp:
            resp.read(200)
            elapsed = (time.time() - start) * 1000
            return True, elapsed, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - start) * 1000
        return True, elapsed, f"HTTP {e.code}"
    except Exception as e:
        return False, None, str(e)


def test_one(proxy, socks_mod=None, target_url=None):
    if proxy["protocol"] in ("HTTP", "HTTPS"):
        ok, ms, info = http_proxy_test(proxy, target_url)
        method = "HTTP"
    elif proxy["protocol"] in ("SOCKS4", "SOCKS5"):
        if socks_mod:
            ok, ms, info = socks_proxy_test(proxy, socks_mod, target_url)
            method = proxy["protocol"]
        else:
            host, port_str = proxy["addr"].rsplit(":", 1)
            port = int(port_str)
            start = time.time()
            try:
                with socket.create_connection((host, port), timeout=config.TIMEOUT):
                    ms = (time.time() - start) * 1000
                    ok, info = True, "TCP-ONLY (PySocks missing)"
            except Exception as e:
                ok, ms, info = False, None, str(e)
            method = "TCP-ONLY"
    else:
        host, port_str = proxy["addr"].rsplit(":", 1)
        port = int(port_str)
        start = time.time()
        try:
            with socket.create_connection((host, port), timeout=config.TIMEOUT):
                ms = (time.time() - start) * 1000
                ok, info = True, "TCP-ONLY (unknown protocol)"
        except Exception as e:
            ok, ms, info = False, None, str(e)
        method = "TCP-ONLY"

    return {
        **proxy,
        "ok": ok,
        "ms": ms,
        "info": info,
        "method": method,
    }


def test_one_retry(proxy, socks_mod, retry_count, target_url=None):
    latencies = []
    last_info = ""
    ok_count = 0

    for _ in range(retry_count):
        result = test_one(proxy, socks_mod, target_url)
        if result["ok"]:
            ok_count += 1
            latencies.append(result["ms"])
        last_info = result["info"]

    if ok_count == 0:
        return {
            **proxy,
            "ok": False,
            "ms": None,
            "min_ms": None,
            "avg_ms": None,
            "max_ms": None,
            "retry": retry_count,
            "ok_count": 0,
            "info": last_info,
            "method": proxy["protocol"],
        }

    avg = sum(latencies) / len(latencies)
    return {
        **proxy,
        "ok": True,
        "ms": avg,
        "min_ms": min(latencies),
        "avg_ms": avg,
        "max_ms": max(latencies),
        "retry": retry_count,
        "ok_count": ok_count,
        "info": last_info,
        "method": proxy["protocol"],
    }
