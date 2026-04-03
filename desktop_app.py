from __future__ import annotations

import threading
import time

import webview
from werkzeug.serving import make_server

from webapp import create_app


class ServerThread(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._app = create_app()
        self._server = make_server("127.0.0.1", 5000, self._app)
        self._context = self._app.app_context()
        self._context.push()

    def run(self) -> None:
        self._server.serve_forever()

    def shutdown(self) -> None:
        self._server.shutdown()


if __name__ == "__main__":
    server = ServerThread()
    server.start()
    time.sleep(1.0)

    window = webview.create_window(
        "AlphaForge",
        "http://127.0.0.1:5000",
        width=1440,
        height=960,
        min_size=(1100, 760),
    )
    webview.start()
    server.shutdown()
