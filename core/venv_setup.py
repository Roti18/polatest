import subprocess
import sys
import os
from . import config


def site_packages_path():
    if os.name == "nt":
        base = os.path.join(config.VENV_DIR, "Lib", "site-packages")
    else:
        ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        base = os.path.join(config.VENV_DIR, "lib", f"python{ver}", "site-packages")
    return base if os.path.isdir(base) else None


def ensure_venv():
    need_create = not os.path.exists(config.VENV_DIR)

    if need_create:
        print(f"[i] Creating virtual environment at {config.VENV_DIR}...")
        subprocess.check_call(
            [sys.executable, "-m", "venv", config.VENV_DIR],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print("[i] Virtual environment created.")

    if os.name == "nt":
        venv_py = os.path.join(config.VENV_DIR, "Scripts", "python.exe")
    else:
        venv_py = os.path.join(config.VENV_DIR, "bin", "python")

    try:
        subprocess.check_call(
            [venv_py, "-c", "import socks"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        print("[i] Installing PySocks in venv...")
        subprocess.check_call(
            [venv_py, "-m", "pip", "install", "pysocks"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print("[i] PySocks ready.\n")

    sp = site_packages_path()
    if sp and sp not in sys.path:
        sys.path.insert(0, sp)


def ensure_venv_import():
    """Inject venv site-packages into sys.path, return socks module."""
    ensure_venv()
    try:
        import socks
        return socks
    except ImportError:
        if os.name == "nt":
            venv_py = os.path.join(config.VENV_DIR, "Scripts", "python.exe")
        else:
            venv_py = os.path.join(config.VENV_DIR, "bin", "python")
        os.execv(venv_py, [__file__] + sys.argv[1:])
