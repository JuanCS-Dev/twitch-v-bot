import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

from bot.channel_control import is_dashboard_admin_authorized, parse_terminal_command
from bot.logic import BOT_BRAND, context
from bot.observability import observability
from bot.runtime_config import (
    BYTE_DASHBOARD_ADMIN_TOKEN,
    BYTE_VERSION,
    DASHBOARD_DIR,
    TWITCH_CHAT_MODE,
    irc_channel_control,
)


class HealthHandler(BaseHTTPRequestHandler):
    MAX_CONTROL_BODY_BYTES = 4096

    def _send_bytes(
        self, payload: bytes, content_type: str, status_code: int = 200
    ) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, payload: dict[str, Any], status_code: int = 200) -> None:
        serialized = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(
            serialized, "application/json; charset=utf-8", status_code=status_code
        )

    def _send_text(self, text: str, status_code: int = 200) -> None:
        self._send_bytes(
            text.encode("utf-8"), "text/plain; charset=utf-8", status_code=status_code
        )

    def _dashboard_authorized(self) -> bool:
        if not BYTE_DASHBOARD_ADMIN_TOKEN:
            return True
        return is_dashboard_admin_authorized(
            self.headers, BYTE_DASHBOARD_ADMIN_TOKEN
        )

    def _send_dashboard_auth_challenge(self) -> None:
        payload = b"Unauthorized"
        self.send_response(401)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("WWW-Authenticate", 'Basic realm="Byte Dashboard"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_payload(self) -> dict[str, Any]:
        raw_length = str(self.headers.get("Content-Length", "0") or "0")
        try:
            content_length = int(raw_length)
        except ValueError as error:
            raise ValueError("Invalid Content-Length header.") from error
        if content_length <= 0:
            raise ValueError("Request body is required.")
        if content_length > self.MAX_CONTROL_BODY_BYTES:
            raise ValueError("Request body is too large.")

        payload_bytes = self.rfile.read(content_length)
        if not payload_bytes:
            raise ValueError("Request body is empty.")
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Invalid JSON payload.") from error
        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object.")
        return payload

    def _send_dashboard_asset(self, relative_path: str, content_type: str) -> bool:
        target_path = (DASHBOARD_DIR / relative_path).resolve()
        if DASHBOARD_DIR not in target_path.parents:
            self._send_text("Not Found", status_code=404)
            return True
        if not target_path.is_file():
            self._send_text("Not Found", status_code=404)
            return True
        self._send_bytes(
            target_path.read_bytes(), content_type=content_type, status_code=200
        )
        return True

    def do_GET(self):
        parsed_path = urlparse(self.path or "/")
        route = parsed_path.path or "/"
        if route in {"/", "/healthz"}:
            self._send_text("AGENT_ONLINE", status_code=200)
            return

        protected_dashboard_routes = {
            "/api/observability",
            "/dashboard",
            "/dashboard/",
            "/dashboard/app.js",
            "/dashboard/styles.css",
            "/dashboard/channel-terminal.js",
        }
        if route in protected_dashboard_routes and not self._dashboard_authorized():
            if route.startswith("/dashboard"):
                self._send_dashboard_auth_challenge()
            else:
                self._send_json(
                    {"ok": False, "error": "forbidden", "message": "Forbidden"},
                    status_code=403,
                )
            return

        if route == "/api/observability":
            snapshot = observability.snapshot(
                bot_brand=BOT_BRAND,
                bot_version=BYTE_VERSION,
                bot_mode=TWITCH_CHAT_MODE,
                stream_context=context,
            )
            self._send_json(snapshot, status_code=200)
            return

        if route in {"/dashboard", "/dashboard/"}:
            self._send_dashboard_asset("index.html", "text/html; charset=utf-8")
            return
        if route == "/dashboard/app.js":
            self._send_dashboard_asset(
                "app.js", "application/javascript; charset=utf-8"
            )
            return
        if route == "/dashboard/styles.css":
            self._send_dashboard_asset("styles.css", "text/css; charset=utf-8")
            return
        if route == "/dashboard/channel-terminal.js":
            self._send_dashboard_asset(
                "channel-terminal.js", "application/javascript; charset=utf-8"
            )
            return

        self._send_text("Not Found", status_code=404)

    def do_POST(self):
        parsed_path = urlparse(self.path or "/")
        route = parsed_path.path or "/"
        if route != "/api/channel-control":
            self._send_text("Not Found", status_code=404)
            return

        if not is_dashboard_admin_authorized(self.headers, BYTE_DASHBOARD_ADMIN_TOKEN):
            self._send_json(
                {"ok": False, "error": "forbidden", "message": "Forbidden"},
                status_code=403,
            )
            return

        try:
            payload = self._read_json_payload()
        except ValueError as error:
            self._send_json(
                {"ok": False, "error": "invalid_request", "message": str(error)},
                status_code=400,
            )
            return

        action = str(payload.get("action", "") or "").strip().lower()
        channel_login = str(payload.get("channel", "") or "").strip()
        command_text = str(payload.get("command", "") or "").strip()
        if command_text:
            try:
                action, channel_login = parse_terminal_command(command_text)
            except ValueError as error:
                self._send_json(
                    {"ok": False, "error": "invalid_command", "message": str(error)},
                    status_code=400,
                )
                return

        result = irc_channel_control.execute(action=action, channel_login=channel_login)
        if result.get("ok"):
            self._send_json(result, status_code=200)
            return

        error_code = str(result.get("error", "") or "")
        if error_code in {"runtime_unavailable", "timeout"}:
            status_code = 503
        elif error_code in {"runtime_error"}:
            status_code = 500
        else:
            status_code = 400
        self._send_json(result, status_code=status_code)

    def log_message(self, format: str, *args: object) -> None:
        return


def run_server() -> None:
    port = int(os.environ.get("PORT", "8080"))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
