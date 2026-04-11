from __future__ import annotations

import atexit
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
APP_PATH = ROOT_DIR / "app.py"
STARTUP_TIMEOUT_SECONDS = 30


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _wait_for_streamlit(url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.3)
    raise RuntimeError("O servidor Streamlit nao respondeu dentro do tempo esperado.")


def _start_streamlit(port: int) -> subprocess.Popen[bytes]:
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_PATH),
        "--server.headless=true",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
    ]
    return subprocess.Popen(command, cwd=str(ROOT_DIR))


def _stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> None:
    try:
        import webview
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "pywebview nao esta instalado. Rode `pip install -r requirements.txt` antes de abrir o desktop."
        ) from exc

    if not APP_PATH.exists():
        raise SystemExit(f"Arquivo Streamlit nao encontrado em {APP_PATH}")

    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"
    process = _start_streamlit(port)
    atexit.register(_stop_process, process)

    try:
        _wait_for_streamlit(url, STARTUP_TIMEOUT_SECONDS)
        webview.create_window(
            "AlphaForge",
            url,
            width=1440,
            height=960,
            min_size=(1100, 760),
        )
        webview.start()
    finally:
        _stop_process(process)


if __name__ == "__main__":
    main()
