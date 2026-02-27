from collections.abc import Callable
from typing import Any

from bot.autonomy_runtime import autonomy_runtime
from bot.control_plane import control_plane
from bot.dashboard_http_helpers import (
    build_control_plane_state_payload,
    parse_dashboard_request_path,
    read_json_payload_or_error,
    require_auth_and_read_payload,
    require_dashboard_auth,
    send_invalid_request,
)
from bot.runtime_config import TWITCH_CHAT_MODE
from bot.vision_runtime import vision_runtime


def handle_post(handler: Any) -> None:
    route, _query = parse_dashboard_request_path(handler.path)

    if route.startswith("/api/action-queue/") and route.endswith("/decision"):
        _handle_action_decision(handler, route)
        return

    route_handler = _POST_ROUTE_HANDLERS.get(route)
    if route_handler is not None:
        route_handler(handler)
        return

    handler._send_text("Not Found", status_code=404)


def _handle_channel_control_post(handler: Any) -> None:
    payload = require_auth_and_read_payload(handler)
    if payload is None:
        return

    try:
        response_payload, status_code = handler._handle_channel_control(payload)
    except ValueError as error:
        handler._send_json(
            {"ok": False, "error": "invalid_command", "message": str(error)},
            status_code=400,
        )
        return
    handler._send_json(response_payload, status_code=status_code)


def _handle_autonomy_tick(handler: Any) -> None:
    payload = require_auth_and_read_payload(handler, allow_empty=True)
    if payload is None:
        return
    force = bool(payload.get("force", True))
    reason = str(payload.get("reason", "manual") or "manual")
    try:
        tick_result = autonomy_runtime.run_manual_tick(force=force, reason=reason)
    except TimeoutError as error:
        handler._send_json(
            {"ok": False, "error": "timeout", "message": str(error)},
            status_code=503,
        )
        return
    handler._send_json(tick_result, status_code=200)


def _send_control_plane_state(handler: Any, *, action: str, reason: str) -> None:
    handler._send_json(
        {
            **build_control_plane_state_payload(),
            "action": action,
            "reason": reason,
        },
        status_code=200,
    )


def _handle_agent_suspend(handler: Any) -> None:
    payload = require_auth_and_read_payload(handler, allow_empty=True)
    if payload is None:
        return

    reason = str(payload.get("reason", "manual_dashboard") or "manual_dashboard")
    control_plane.suspend_agent(reason=reason)
    _send_control_plane_state(handler, action="suspend", reason=reason)


def _handle_agent_resume(handler: Any) -> None:
    payload = require_auth_and_read_payload(handler, allow_empty=True)
    if payload is None:
        return

    reason = str(payload.get("reason", "manual_dashboard") or "manual_dashboard")
    control_plane.resume_agent(reason=reason)
    _send_control_plane_state(handler, action="resume", reason=reason)


def _handle_action_decision(handler: Any, route: str) -> None:
    if not require_dashboard_auth(handler):
        return
    action_id = route.removeprefix("/api/action-queue/").removesuffix("/decision").strip()
    if not action_id:
        handler._send_json(
            {"ok": False, "error": "invalid_request", "message": "Action id obrigatorio."},
            status_code=400,
        )
        return
    payload = read_json_payload_or_error(handler)
    if payload is None:
        return
    decision = str(payload.get("decision", "") or "").strip().lower()
    note = str(payload.get("note", "") or "").strip()
    try:
        updated_item = control_plane.decide_action(
            action_id=action_id,
            decision=decision,
            note=note,
        )
    except ValueError as error:
        send_invalid_request(handler, str(error))
        return
    except KeyError:
        handler._send_json(
            {"ok": False, "error": "action_not_found", "message": "Action nao encontrada."},
            status_code=404,
        )
        return
    except RuntimeError as error:
        handler._send_json(
            {"ok": False, "error": "action_not_pending", "message": str(error)},
            status_code=409,
        )
        return

    handler._send_json(
        {
            "ok": True,
            "item": updated_item,
            "mode": TWITCH_CHAT_MODE,
        },
        status_code=200,
    )


def _handle_vision_ingest(handler: Any) -> None:
    if not require_dashboard_auth(handler):
        return

    content_type = str(handler.headers.get("Content-Type", "") or "").strip().lower()
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        handler._send_json(
            {
                "ok": False,
                "error": "invalid_content_type",
                "message": "Use image/jpeg, image/png or image/webp.",
            },
            status_code=400,
        )
        return

    content_length = int(handler.headers.get("Content-Length", 0) or 0)
    if content_length <= 0:
        handler._send_json(
            {"ok": False, "error": "empty_body", "message": "Frame body vazio."},
            status_code=400,
        )
        return

    frame_bytes = handler.rfile.read(content_length)
    result = vision_runtime.ingest_frame(frame_bytes, mime_type=content_type)
    status_code = (
        200 if result.get("ok") else 429 if result.get("reason") == "rate_limited" else 400
    )
    handler._send_json(result, status_code=status_code)


def _handle_ops_playbook_trigger(handler: Any) -> None:
    payload = require_auth_and_read_payload(handler, allow_empty=True)
    if payload is None:
        return

    playbook_id = str(payload.get("playbook_id", "") or "").strip().lower()
    channel_id = str(payload.get("channel_id", "default") or "default").strip().lower() or "default"
    reason = str(payload.get("reason", "manual_dashboard") or "manual_dashboard")
    force = bool(payload.get("force", False))
    if not playbook_id:
        send_invalid_request(handler, "playbook_id obrigatorio.")
        return
    try:
        snapshot = control_plane.trigger_ops_playbook(
            playbook_id=playbook_id,
            channel_id=channel_id,
            reason=reason,
            force=force,
        )
    except KeyError:
        handler._send_json(
            {
                "ok": False,
                "error": "playbook_not_found",
                "message": "Playbook nao encontrado.",
            },
            status_code=404,
        )
        return
    except RuntimeError as error:
        handler._send_json(
            {
                "ok": False,
                "error": str(error),
                "message": str(error),
            },
            status_code=409,
        )
        return

    handler._send_json(
        {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            "selected_channel": channel_id,
            **snapshot,
        },
        status_code=200,
    )


_POST_ROUTE_HANDLERS: dict[str, Callable[[Any], None]] = {
    "/api/channel-control": _handle_channel_control_post,
    "/api/autonomy/tick": _handle_autonomy_tick,
    "/api/agent/suspend": _handle_agent_suspend,
    "/api/agent/resume": _handle_agent_resume,
    "/api/ops-playbooks/trigger": _handle_ops_playbook_trigger,
    "/api/vision/ingest": _handle_vision_ingest,
}
