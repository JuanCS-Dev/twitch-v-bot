from unittest.mock import MagicMock, patch

from bot.dashboard_http_helpers import (
    build_control_plane_state_payload,
    parse_dashboard_request_path,
    read_json_payload_or_error,
    require_auth_and_read_payload,
    require_dashboard_auth,
    send_invalid_request,
)
from bot.runtime_config import TWITCH_CHAT_MODE


def test_parse_dashboard_request_path_returns_route_and_query():
    route, query = parse_dashboard_request_path("/api/action-queue?status=pending&limit=10")

    assert route == "/api/action-queue"
    assert query["status"] == ["pending"]
    assert query["limit"] == ["10"]


def test_send_invalid_request_uses_standard_payload():
    handler = MagicMock()

    send_invalid_request(handler, "bad request")

    handler._send_json.assert_called_once_with(
        {"ok": False, "error": "invalid_request", "message": "bad request"},
        status_code=400,
    )


def test_require_dashboard_auth_allows_authorized_requests():
    handler = MagicMock()
    handler._dashboard_authorized.return_value = True

    allowed = require_dashboard_auth(handler)

    assert allowed is True
    handler._send_forbidden.assert_not_called()


def test_require_dashboard_auth_blocks_unauthorized_requests():
    handler = MagicMock()
    handler._dashboard_authorized.return_value = False

    allowed = require_dashboard_auth(handler)

    assert allowed is False
    handler._send_forbidden.assert_called_once()


def test_read_json_payload_or_error_returns_payload():
    handler = MagicMock()
    handler._read_json_payload.return_value = {"channel_id": "canal_a"}

    payload = read_json_payload_or_error(handler)

    assert payload == {"channel_id": "canal_a"}
    handler._send_json.assert_not_called()


def test_read_json_payload_or_error_sends_invalid_request_on_error():
    handler = MagicMock()
    handler._read_json_payload.side_effect = ValueError("bad json")

    payload = read_json_payload_or_error(handler)

    assert payload is None
    handler._send_json.assert_called_once_with(
        {"ok": False, "error": "invalid_request", "message": "bad json"},
        status_code=400,
    )


def test_require_auth_and_read_payload_returns_payload_when_authorized():
    handler = MagicMock()
    handler._dashboard_authorized.return_value = True
    handler._read_json_payload.return_value = {"force": True}

    payload = require_auth_and_read_payload(handler, allow_empty=True)

    assert payload == {"force": True}
    handler._send_forbidden.assert_not_called()


def test_require_auth_and_read_payload_blocks_unauthorized_requests():
    handler = MagicMock()
    handler._dashboard_authorized.return_value = False

    payload = require_auth_and_read_payload(handler)

    assert payload is None
    handler._send_forbidden.assert_called_once()


@patch("bot.dashboard_http_helpers.control_plane")
def test_build_control_plane_state_payload(mock_control_plane):
    mock_control_plane.get_config.return_value = {"temperature": 0.3}
    mock_control_plane.runtime_snapshot.return_value = {"queue_window_60m": {}}
    mock_control_plane.build_capabilities.return_value = {"manual_tick": True}

    payload = build_control_plane_state_payload()

    assert payload == {
        "ok": True,
        "mode": TWITCH_CHAT_MODE,
        "config": {"temperature": 0.3},
        "autonomy": {"queue_window_60m": {}},
        "capabilities": {"manual_tick": True},
    }
