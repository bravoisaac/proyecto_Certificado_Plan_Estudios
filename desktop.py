from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer

from server import AppHandler


APP_TITLE = "Equivalencias · Plan de estudios"


class DesktopServer(ThreadingHTTPServer):
    """Servidor local que no deja solicitudes activas al cerrar la aplicación."""

    daemon_threads = True
    allow_reuse_address = True


def start_local_server() -> tuple[DesktopServer, threading.Thread, str]:
    """Inicia la API en un puerto local libre y devuelve su URL."""

    server = DesktopServer(("127.0.0.1", 0), AppHandler)
    thread = threading.Thread(
        target=server.serve_forever,
        name="equivalencias-local-server",
        daemon=True,
    )
    thread.start()
    port = server.server_address[1]
    return server, thread, f"http://127.0.0.1:{port}"


def main() -> None:
    import webview

    server, thread, url = start_local_server()
    try:
        # Las descargas están deshabilitadas por defecto en pywebview.
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.create_window(
            APP_TITLE,
            url,
            width=1280,
            height=820,
            min_size=(900, 640),
            background_color="#f4f7f6",
        )
        webview.start(debug=False, private_mode=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
