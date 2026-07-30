import os

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEST_URL = "http://httpbin.org/ip"
TIMEOUT = 10
MAX_WORKERS = 20

PROXY_FILE = os.path.join(SCRIPT_DIR, "proxies.json")
PROXY_WORKING_FILE = os.path.join(SCRIPT_DIR, "proxies.working.json")
RESULTS_JSON_FILE = os.path.join(SCRIPT_DIR, "results.json")
RESULTS_CSV_FILE = os.path.join(SCRIPT_DIR, "results.csv")

VENV_DIR = os.path.join(SCRIPT_DIR, ".venv")
