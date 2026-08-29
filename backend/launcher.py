import multiprocessing
import socket
import subprocess
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

from app.main import app


HOST, PORT = "127.0.0.1", 8765


def url_available(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1):
            return True
    except Exception:
        return False


def start_ollama_if_needed() -> None:
    if url_available("http://127.0.0.1:11434/api/tags"):
        return
    candidates = [
        Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
        Path("C:/Program Files/Ollama/ollama.exe"),
    ]
    executable = next((path for path in candidates if path.exists()), None)
    if executable:
        subprocess.Popen([str(executable), "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(20):
            if url_available("http://127.0.0.1:11434/api/tags"):
                return
            time.sleep(0.25)


def port_in_use() -> bool:
    with socket.socket() as sock:
        return sock.connect_ex((HOST, PORT)) == 0


def open_interface() -> None:
    for _ in range(60):
        if url_available(f"http://{HOST}:{PORT}/api/health"):
            webbrowser.open(f"http://{HOST}:{PORT}")
            return
        time.sleep(0.25)


def main() -> None:
    start_ollama_if_needed()
    if port_in_use():
        webbrowser.open(f"http://{HOST}:{PORT}")
        return
    threading.Thread(target=open_interface, daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

