from typing import Any
from urllib.parse import parse_qs, urlparse

from bot.control_plane import control_plane
from bot.runtime_config import TWITCH_CHAT_MODE


def parse_dashboard_request_path(path: str | None) -> tuple[str, dict[str, list[str]]]:
    parsed_path = urlparse(path or "/")
    return parsed_path.path or "/", parse_qs(parsed_path.query or "")


def send_invalid_request(handler: Any, message: str) -> None:
    handler._send_json(
        {"ok": False, "error": "invalid_request", "message": str(message)},
        status_code=400,
    )


def require_dashboard_auth(handler: Any) -> bool:
    if handler._dashboard_authorized():
        return True
    handler._send_forbidden()
    return False


def read_json_payload_or_error(
    handler: Any,
    *,
    allow_empty: bool = False,
) -> dict[str, Any] | None:
    try:
        return handler._read_json_payload(allow_empty=allow_empty)
    except ValueError as error:
        send_invalid_request(handler, str(error))
        return None


def require_auth_and_read_payload(
    handler: Any,
    *,
    allow_empty: bool = False,
) -> dict[str, Any] | None:
    if not require_dashboard_auth(handler):
        return None
    return read_json_payload_or_error(handler, allow_empty=allow_empty)


def build_control_plane_state_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": TWITCH_CHAT_MODE,
        "config": control_plane.get_config(),
        "autonomy": control_plane.runtime_snapshot(),
        "capabilities": control_plane.build_capabilities(bot_mode=TWITCH_CHAT_MODE),
    }
