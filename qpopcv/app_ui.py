"""
QPopCV main application — PyQt6 + QWebEngineView edition.

Architecture:
  - QMainWindow with QWebEngineView loads http://127.0.0.1:PORT/
  - A ThreadingHTTPServer runs on a random free port, serving static files
    and handling JSON API calls from JS
  - Server-Sent Events (SSE) push asynchronous events from Python to JS
  - Native file dialog is bridged to the Qt main thread via pyqtSignal
"""
from __future__ import annotations

import json
import logging
import queue
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

from .api import Api
from .config import APP_DIR, load_config

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_static_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent
    return base / "static"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ── HTTP server ────────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    """Handles all HTTP requests: static file serving, API calls, SSE."""

    def log_message(self, fmt, *args):
        pass  # Suppress HTTP access logs

    # CORS preflight
    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors()
        self.end_headers()

    # Static files + SSE
    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/events":
            self._handle_sse()
            return

        if path == "/":
            path = "/index.html"

        static_dir: Path = self.server.static_dir
        file_path = (static_dir / path.lstrip("/")).resolve()

        # Prevent path traversal
        try:
            file_path.relative_to(static_dir.resolve())
        except ValueError:
            self.send_error(403)
            return

        if not file_path.is_file():
            self.send_error(404)
            return

        ext = file_path.suffix.lower()
        mime = {".html": "text/html; charset=utf-8",
                ".css": "text/css",
                ".js": "application/javascript"}.get(ext, "application/octet-stream")

        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self._send_cors()
        self.end_headers()
        self.wfile.write(content)

    # JSON API
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body: dict = {}
        if length:
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                pass

        api: Api = self.server.api
        app: "QPopApp" = self.server.qpop_app
        path = self.path

        try:
            if path == "/api/initial_state":
                result = api.get_initial_state()
            elif path == "/api/start_watch":
                result = api.start_watch(body)
            elif path == "/api/stop_watch":
                result = api.stop_watch()
            elif path == "/api/test_discord":
                result = api.test_discord(body)
            elif path == "/api/browse_image":
                result = app.browse_image_sync()
            elif path == "/api/open_discord":
                api.open_discord()
                result = {"ok": True}
            elif path == "/api/check_updates":
                api.check_for_updates()
                result = {"ok": True}
            elif path == "/api/install_update":
                result = api.install_update()
            elif path == "/api/resize":
                h = max(240, min(int(body.get("height", 400)), 800))
                app.resize_window(h)
                result = {"ok": True}
            elif path == "/api/save_config":
                result = api.save_config_data(body)
            elif path == "/api/window_control":
                action = body.get("action", "")
                if action == "minimize":
                    app._bridge.request_minimize.emit()
                elif action == "close":
                    app._bridge.request_quit.emit()
                elif action == "drag_start":
                    app._bridge.request_drag.emit()
                result = {"ok": True}
            else:
                result = {"ok": False, "error": f"Unknown route: {path}"}
        except Exception as exc:
            logger.exception("API error on %s: %s", path, exc)
            result = {"ok": False, "error": str(exc)}

        response = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self._send_cors()
        self.end_headers()
        self.wfile.write(response)

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _handle_sse(self):
        eq: queue.Queue = self.server.event_queue
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._send_cors()
        self.end_headers()
        try:
            while True:
                try:
                    event = eq.get(timeout=25)
                    if event is None:  # shutdown sentinel
                        return
                    self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                    self.wfile.flush()
                except queue.Empty:
                    # heartbeat so the connection doesn't time out
                    self.wfile.write(b'data: {"type":"heartbeat"}\n\n')
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


# ── Qt bridge for main-thread operations ───────────────────────────────────────

class _Bridge(QObject):
    """QObject whose signals can cross the thread boundary to the Qt main loop."""
    request_browse   = pyqtSignal()
    request_quit     = pyqtSignal()
    request_resize   = pyqtSignal(int)   # content height in px
    request_minimize = pyqtSignal()
    request_drag     = pyqtSignal()


# ── Main application class ─────────────────────────────────────────────────────

class QPopApp:
    def __init__(self) -> None:
        config = load_config()
        self._static_dir = _get_static_dir()
        self._event_queue: queue.Queue = queue.Queue()

        # File-dialog plumbing
        self._browse_result: str | None = None
        self._browse_event = threading.Event()

        # Bridge (created before QApplication so Qt ownership is correct)
        self._bridge = _Bridge()

        # API — push_event and quit_fn are set here
        self._api = Api(
            config,
            push_event=self._push_event,
            quit_fn=self._request_quit,
        )

        # HTTP server
        self._port = _find_free_port()
        self._server = self._start_http_server()

    # ── HTTP server ────────────────────────────────────────────────────────────

    def _start_http_server(self) -> ThreadingHTTPServer:
        server = ThreadingHTTPServer(("127.0.0.1", self._port), _Handler)
        server.static_dir = self._static_dir
        server.api = self._api
        server.event_queue = self._event_queue
        server.qpop_app = self
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info("Local API server on port %d", self._port)
        return server

    def _push_event(self, event_type: str, data: dict | None = None) -> None:
        """Thread-safe SSE push."""
        payload: dict = {"type": event_type}
        if data:
            payload.update(data)
        self._event_queue.put(payload)

    # ── File dialog (main-thread bridge) ───────────────────────────────────────

    def browse_image_sync(self) -> dict:
        """Called from HTTP server thread. Blocks until user picks a file (or cancels)."""
        self._browse_result = None
        self._browse_event.clear()
        self._bridge.request_browse.emit()   # queued → runs on Qt main thread
        self._browse_event.wait(timeout=60)  # wait up to 60 s
        return {"path": self._browse_result}

    def _on_browse_requested(self) -> None:
        """Runs on Qt main thread."""
        path, _ = QFileDialog.getOpenFileName(
            self._window,
            "Select reference image",
            "",
            "Image files (*.png *.jpg *.jpeg *.bmp);;All files (*.*)",
        )
        self._browse_result = path or None
        self._browse_event.set()

    # ── Quit bridge ────────────────────────────────────────────────────────────

    def resize_window(self, height: int) -> None:
        """Called from HTTP server thread. Queues resize on Qt main thread."""
        self._bridge.request_resize.emit(height)

    def _on_resize_requested(self, height: int) -> None:
        """Runs on Qt main thread."""
        if self._window:
            self._window.resize(self._window.width(), height)

    def _request_quit(self) -> None:
        """Called from background thread. Queues close on Qt main thread."""
        self._bridge.request_quit.emit()

    def _on_quit_requested(self) -> None:
        """Runs on Qt main thread."""
        if self._window:
            self._window.close()

    def _on_minimize_requested(self) -> None:
        """Runs on Qt main thread."""
        if self._window:
            self._window.showMinimized()

    def _on_drag_requested(self) -> None:
        """Runs on Qt main thread. Initiates OS-native window move."""
        if self._window:
            handle = self._window.windowHandle()
            if handle:
                handle.startSystemMove()

    # ── Run ────────────────────────────────────────────────────────────────────

    def run(self) -> None:
        app = QApplication.instance() or QApplication(sys.argv)

        self._window = QMainWindow()
        self._window.setWindowTitle("QPopCV")
        self._window.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self._window.resize(440, 320)
        self._window.setMinimumSize(400, 240)

        # Wire bridge signals to main-thread slots
        self._bridge.request_browse.connect(
            self._on_browse_requested, Qt.ConnectionType.QueuedConnection
        )
        self._bridge.request_quit.connect(
            self._on_quit_requested, Qt.ConnectionType.QueuedConnection
        )
        self._bridge.request_resize.connect(
            self._on_resize_requested, Qt.ConnectionType.QueuedConnection
        )
        self._bridge.request_minimize.connect(
            self._on_minimize_requested, Qt.ConnectionType.QueuedConnection
        )
        self._bridge.request_drag.connect(
            self._on_drag_requested, Qt.ConnectionType.QueuedConnection
        )

        # Web view
        view = QWebEngineView()
        view.page().setBackgroundColor(QColor(49, 51, 56))
        s = view.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)

        self._window.setCentralWidget(view)

        def on_close(event):
            self._api._cleanup()
            self._event_queue.put(None)  # stop SSE handler
            self._server.shutdown()
            event.accept()

        self._window.closeEvent = on_close
        view.load(QUrl(f"http://127.0.0.1:{self._port}/"))
        self._window.show()
        app.exec()
