from __future__ import annotations

import threading
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import webbrowser

import uvicorn


def open_browser() -> None:
    opener = build_opener(ProxyHandler({}))
    for _ in range(500):
        try:
            with opener.open("http://127.0.0.1:8765/api/v1/health", timeout=1):
                webbrowser.open("http://127.0.0.1:8765")
                return
        except (URLError, OSError):
            time.sleep(0.25)


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8765,
        log_level="warning",
        access_log=False,
    )

