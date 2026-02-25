from typing import Any
from urllib.parse import urlparse

from bot.autonomy_runtime import autonomy_runtime
from bot.control_plane import control_plane
from bot.runtime_config import TWITCH_CHAT_MODE
from bot.vision_runtime import vision_runtime


def handle_post(handler: Any) -> None:
    parsed_path = urlparse(handler.path or "/")
    route = parsed_path.path or "/"

    if route == "/api/channel-control":
        _handle_channel_control_post(handler)
        return

    if route == "/api/autonomy/tick":
        _handle_autonomy_tick(handler)
        return

    if route.startswith("/api/action-queue/") and route.endswith("/decision"):
        _handle_action_decision(handler, route)
        return

    if route == "/api/vision/ingest":
        _handle_vision_ingest(handler)
        return

    handler._send_text("Not Found", status_code=404)


def _handle_channel_control_post(handler: Any) -> None:
    if not handler._dashboard_authorized():
        handler._send_forbidden()
        return
    try:
        payload = handler._read_json_payload()
    except ValueError as error:
        handler._send_json(
            {"ok": False, "error": "invalid_request", "message": str(error)},
            status_code=400,
        )
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
    if not handler._dashboard_authorized():
        handler._send_forbidden()
        return
    try:
        payload = handler._read_json_payload(allow_empty=True)
    except ValueError as error:
        handler._send_json(
            {"ok": False, "error": "invalid_request", "message": str(error)},
            status_code=400,
        )
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


def _handle_action_decision(handler: Any, route: str) -> None:
    if not handler._dashboard_authorized():
        handler._send_forbidden()
        return
    action_id = route.removeprefix("/api/action-queue/").removesuffix("/decision").strip()
    if not action_id:
        handler._send_json(
            {"ok": False, "error": "invalid_request", "message": "Action id obrigatorio."},
            status_code=400,
        )
        return
    try:
        payload = handler._read_json_payload()
    except ValueError as error:
        handler._send_json(
            {"ok": False, "error": "invalid_request", "message": str(error)},
            status_code=400,
        )
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
        handler._send_json(
            {"ok": False, "error": "invalid_request", "message": str(error)},
            status_code=400,
        )
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
    if not handler._dashboard_authorized():
        handler._send_forbidden()
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
