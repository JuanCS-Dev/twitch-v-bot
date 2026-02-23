import mimetypes
from typing import Any
from urllib.parse import parse_qs, urlparse

from bot.clip_jobs_runtime import clip_jobs
from bot.control_plane import control_plane
from bot.hud_runtime import hud_runtime
from bot.logic import BOT_BRAND, context
from bot.observability import observability
from bot.runtime_config import BYTE_VERSION, TWITCH_CHAT_MODE
from bot.sentiment_engine import sentiment_engine
from bot.vision_runtime import vision_runtime

CHANNEL_CONTROL_IRC_ONLY_ACTIONS = {"join", "part"}
HEALTH_ROUTES = {"/health", "/health/", "/healthz", "/healthz/"}


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
    if route in {"/", "/dashboard", "/dashboard/"}:
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
    if _is_api_route(route) and not handler._dashboard_authorized():
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

    if route == "/api/hud/messages":
        since_raw = str((query.get("since") or ["0"])[0] or "0")
        try:
            since = float(since_raw)
        except ValueError:
            since = 0.0
        messages = hud_runtime.get_messages(since=since)
        handler._send_json({"ok": True, "messages": messages}, status_code=200)
        return

    if route == "/api/sentiment/scores":
        scores = sentiment_engine.get_scores()
        scores["vibe"] = sentiment_engine.get_vibe()
        handler._send_json({"ok": True, **scores}, status_code=200)
        return

    if route == "/api/vision/status":
        handler._send_json({"ok": True, **vision_runtime.get_status()}, status_code=200)
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


from bot.dashboard_server_routes_post import handle_post  # noqa: E402, F401

__all__ = [
    "build_observability_payload",
    "handle_get",
    "handle_put",
    "handle_post",
]

