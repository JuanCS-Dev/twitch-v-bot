import mimetypes
from typing import Any
from urllib.parse import parse_qs, urlparse

from bot.autonomy_runtime import autonomy_runtime
from bot.clip_jobs_runtime import clip_jobs
from bot.control_plane import control_plane
from bot.logic import BOT_BRAND, context
from bot.observability import observability
from bot.runtime_config import BYTE_VERSION, TWITCH_CHAT_MODE

CHANNEL_CONTROL_IRC_ONLY_ACTIONS = {"join", "part"}
HEALTH_ROUTES = {"/", "/health", "/health/", "/healthz", "/healthz/"}


def _is_api_route(route: str) -> bool:
    return route.startswith("/api/")


def build_observability_payload() -> dict[str, Any]:
    snapshot = observability.snapshot(
        bot_brand=BOT_BRAND,
        bot_version=BYTE_VERSION,
        bot_mode=TWITCH_CHAT_MODE,
        stream_context=context,
    )
    capabilities = control_plane.build_capabilities(bot_mode=TWITCH_CHAT_MODE)
    autonomy = control_plane.runtime_snapshot()
    queue_window_60m = autonomy.get("queue_window_60m", {})
    current_outcomes = snapshot.get("agent_outcomes", {}) or {}
    snapshot["agent_outcomes"] = {
        **current_outcomes,
        "ignored_rate_60m": float(queue_window_60m.get("ignored_rate", 0.0)),
        "ignored_total_60m": int(queue_window_60m.get("ignored", 0)),
        "decisions_total_60m": int(queue_window_60m.get("decisions_total", 0)),
    }
    snapshot["capabilities"] = capabilities
    snapshot["autonomy"] = autonomy
    snapshot["ok"] = True
    return snapshot


def _dashboard_asset_route(handler: Any, route: str) -> bool:
    if route in {"/dashboard", "/dashboard/"}:
        handler._send_dashboard_asset("index.html", "text/html; charset=utf-8")
        return True
    if route.startswith("/dashboard/"):
        relative_path = route[len("/dashboard/") :]
        guessed_content_type, _ = mimetypes.guess_type(relative_path)
        content_type = guessed_content_type or "application/octet-stream"
        if content_type == "text/javascript":
            content_type = "application/javascript"
        if content_type.startswith("text/") or content_type in {
            "application/javascript",
            "application/json",
        }:
            content_type = f"{content_type}; charset=utf-8"
        handler._send_dashboard_asset(relative_path, content_type)
        return True
    return False


def handle_get(handler: Any) -> None:
    parsed_path = urlparse(handler.path or "/")
    route = parsed_path.path or "/"
    query = parse_qs(parsed_path.query or "")
    if route in HEALTH_ROUTES:
        handler._send_text("AGENT_ONLINE", status_code=200)
        return

    is_dashboard_route = route in {"/dashboard", "/dashboard/"} or route.startswith(
        "/dashboard/"
    )
    if (_is_api_route(route) or is_dashboard_route) and not handler._dashboard_authorized():
        if is_dashboard_route:
            handler._send_dashboard_auth_challenge()
        else:
            handler._send_forbidden()
        return

    if route == "/api/observability":
        handler._send_json(handler._build_observability_payload(), status_code=200)
        return

    if route == "/api/control-plane":
        handler._send_json(
            {
                "ok": True,
                "mode": TWITCH_CHAT_MODE,
                "config": control_plane.get_config(),
                "autonomy": control_plane.runtime_snapshot(),
                "capabilities": control_plane.build_capabilities(bot_mode=TWITCH_CHAT_MODE),
            },
            status_code=200,
        )
        return

    if route == "/api/action-queue":
        status_filter = str((query.get("status") or [""])[0] or "").strip().lower()
        limit_raw = str((query.get("limit") or ["80"])[0] or "80")
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 80
        queue_payload = control_plane.list_actions(
            status=status_filter or None,
            limit=limit,
        )
        handler._send_json(
            {
                "ok": True,
                "mode": TWITCH_CHAT_MODE,
                **queue_payload,
            },
            status_code=200,
        )
        return

    if route == "/api/clip-jobs":
        jobs = clip_jobs.get_jobs()
        handler._send_json(
            {
                "ok": True,
                "mode": TWITCH_CHAT_MODE,
                "items": jobs,
            },
            status_code=200,
        )
        return

    if _dashboard_asset_route(handler, route):
        return

    handler._send_text("Not Found", status_code=404)


def handle_put(handler: Any) -> None:
    parsed_path = urlparse(handler.path or "/")
    route = parsed_path.path or "/"
    if route != "/api/control-plane":
        handler._send_text("Not Found", status_code=404)
        return

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
        updated_config = control_plane.update_config(payload)
    except ValueError as error:
        handler._send_json(
            {"ok": False, "error": "invalid_request", "message": str(error)},
            status_code=400,
        )
        return

    handler._send_json(
        {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            "config": updated_config,
            "autonomy": control_plane.runtime_snapshot(),
            "capabilities": control_plane.build_capabilities(bot_mode=TWITCH_CHAT_MODE),
        },
        status_code=200,
    )


def handle_post(handler: Any) -> None:
    parsed_path = urlparse(handler.path or "/")
    route = parsed_path.path or "/"

    if route == "/api/channel-control":
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
        return

    if route == "/api/autonomy/tick":
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
        return

    if route.startswith("/api/action-queue/") and route.endswith("/decision"):
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
        return

    handler._send_text("Not Found", status_code=404)
