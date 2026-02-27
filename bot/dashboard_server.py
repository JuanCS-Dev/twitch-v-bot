import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar

from bot.channel_control import is_dashboard_admin_authorized, parse_terminal_command
from bot.dashboard_server_routes import (
    CHANNEL_CONTROL_IRC_ONLY_ACTIONS,
    build_observability_payload,
    handle_get,
    handle_post,
    handle_put,
)
from bot.persistence_layer import persistence
from bot.post_stream_report import build_post_stream_report
from bot.runtime_config import (
    BYTE_DASHBOARD_ADMIN_TOKEN,
    DASHBOARD_DIR,
    TWITCH_CHAT_MODE,
    irc_channel_control,
)


class HealthHandler(BaseHTTPRequestHandler):
    MAX_CONTROL_BODY_BYTES = 4096
    CHANNEL_CONTROL_IRC_ONLY_ACTIONS = CHANNEL_CONTROL_IRC_ONLY_ACTIONS
    _rate_limit_state: ClassVar[dict[str, list[float]]] = {}
    _rate_limit_max_requests = 100
    _rate_limit_window_seconds = 60
    _logger = logging.getLogger("byte.dashboard.server")

    def _check_rate_limit(self) -> bool:
        ip = self.client_address[0]
        now = time.time()

        # Cleanup old entries periodically (every 100 requests roughly)
        if len(self._rate_limit_state) > 1000:
            self._rate_limit_state.clear()

        history = self._rate_limit_state.get(ip, [])
        history = [ts for ts in history if now - ts < self._rate_limit_window_seconds]

        if len(history) >= self._rate_limit_max_requests:
            return False

        history.append(now)
        self._rate_limit_state[ip] = history
        return True

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers", "Content-Type, X-Byte-Admin-Token, Authorization"
        )

    def _send_bytes(self, payload: bytes, content_type: str, status_code: int = 200) -> None:
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, payload: dict[str, Any], status_code: int = 200) -> None:
        serialized = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(serialized, "application/json; charset=utf-8", status_code=status_code)

    def _send_text(self, text: str, status_code: int = 200) -> None:
        self._send_bytes(text.encode("utf-8"), "text/plain; charset=utf-8", status_code=status_code)

    def _dashboard_authorized(self) -> bool:
        if not BYTE_DASHBOARD_ADMIN_TOKEN:
            return True
        authorized = is_dashboard_admin_authorized(self.headers, BYTE_DASHBOARD_ADMIN_TOKEN)
        if not authorized:
            import hmac
            import urllib.parse

            parsed_path = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_path.query)
            if "auth" in query_params:
                provided_token = query_params["auth"][0].strip()
                authorized = hmac.compare_digest(provided_token, BYTE_DASHBOARD_ADMIN_TOKEN.strip())

        if not authorized:
            from bot.runtime_config import logger

            logger.warning("Auth rejection for route %s from %s", self.path, self.address_string())
        return authorized

    def _send_dashboard_auth_challenge(self) -> None:
        payload = b"Unauthorized"
        self.send_response(401)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("WWW-Authenticate", 'Basic realm="Byte Dashboard"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_forbidden(self) -> None:
        self._send_json(
            {"ok": False, "error": "forbidden", "message": "Forbidden"},
            status_code=403,
        )

    def _read_json_payload(self, *, allow_empty: bool = False) -> dict[str, Any]:
        raw_length = str(self.headers.get("Content-Length", "0") or "0")
        try:
            content_length = int(raw_length)
        except ValueError as error:
            raise ValueError("Invalid Content-Length header.") from error
        if content_length <= 0:
            if allow_empty:
                return {}
            raise ValueError("Request body is required.")
        if content_length > self.MAX_CONTROL_BODY_BYTES:
            raise ValueError("Request body is too large.")

        payload_bytes = self.rfile.read(content_length)
        if not payload_bytes:
            if allow_empty:
                return {}
            raise ValueError("Request body is empty.")
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Invalid JSON payload.") from error
        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object.")
        return payload

    def _send_dashboard_asset(self, relative_path: str, content_type: str) -> bool:
        if ".." in relative_path or relative_path.startswith("/"):
            self._send_text("Invalid path", status_code=400)
            return True
        target_path = (DASHBOARD_DIR / relative_path).resolve()
        if DASHBOARD_DIR not in target_path.parents:
            self._send_text("Not Found", status_code=404)
            return True
        if not target_path.is_file():
            self._send_text("Not Found", status_code=404)
            return True
        self._send_bytes(target_path.read_bytes(), content_type=content_type, status_code=200)
        return True

    def _build_observability_payload(self, channel_id: str | None = None) -> dict[str, Any]:
        return build_observability_payload(channel_id)

    def _handle_channel_control(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        action = str(payload.get("action", "") or "").strip().lower()
        channel_login = str(payload.get("channel", "") or "").strip()
        command_text = str(payload.get("command", "") or "").strip()
        if command_text:
            action, channel_login = parse_terminal_command(command_text)

        if TWITCH_CHAT_MODE != "irc":
            if action in self.CHANNEL_CONTROL_IRC_ONLY_ACTIONS:
                return (
                    {
                        "ok": False,
                        "error": "unsupported_mode",
                        "message": "Channel control de runtime so funciona em TWITCH_CHAT_MODE=irc.",
                        "mode": TWITCH_CHAT_MODE,
                        "action": action,
                    },
                    409,
                )
            if action == "list":
                return (
                    {
                        "ok": True,
                        "action": "list",
                        "channels": [],
                        "mode": TWITCH_CHAT_MODE,
                        "message": "Sem runtime IRC ativo neste modo. join/part ficam bloqueados em eventsub.",
                    },
                    200,
                )

        result = irc_channel_control.execute(action=action, channel_login=channel_login)
        result["mode"] = TWITCH_CHAT_MODE
        if result.get("ok") and action == "part":
            report_channel_id = (
                str(channel_login or result.get("channel") or "default").strip().lower()
            )
            report_channel_id = report_channel_id or "default"
            try:
                snapshot = build_observability_payload(report_channel_id)
                history_points = persistence.load_observability_channel_history_sync(
                    report_channel_id,
                    limit=120,
                )
                generated_report = build_post_stream_report(
                    channel_id=report_channel_id,
                    history_points=list(history_points or []),
                    observability_snapshot=snapshot,
                    trigger="auto_part_success",
                )
                persistence.save_post_stream_report_sync(
                    report_channel_id,
                    generated_report,
                    trigger="auto_part_success",
                )
                result["post_stream_report"] = {
                    "generated": True,
                    "channel_id": report_channel_id,
                    "trigger": "auto_part_success",
                }
            except Exception as error:
                self._logger.error(
                    "Falha ao gerar post_stream_report automatico para %s: %s",
                    report_channel_id,
                    error,
                )
        if result.get("ok"):
            return result, 200

        error_code = str(result.get("error", "") or "")
        if error_code in {"runtime_unavailable", "timeout"}:
            status_code = 503
        elif error_code in {"runtime_error"}:
            status_code = 500
        else:
            status_code = 400
        return result, status_code

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if not self._check_rate_limit():
            self._send_text("Too Many Requests", status_code=429)
            return
        handle_get(self)

    def do_PUT(self) -> None:
        if not self._check_rate_limit():
            self._send_text("Too Many Requests", status_code=429)
            return
        handle_put(self)

    def do_POST(self) -> None:
        if not self._check_rate_limit():
            self._send_text("Too Many Requests", status_code=429)
            return
        handle_post(self)

    def log_message(self, format: str, *args: object) -> None:
        return


def run_server() -> None:
    port = int(os.environ.get("PORT", "8080"))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
