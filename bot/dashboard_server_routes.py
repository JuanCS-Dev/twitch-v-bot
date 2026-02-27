import asyncio
import mimetypes
from typing import Any
from urllib.parse import parse_qs, urlparse

from bot.clip_jobs_runtime import clip_jobs
from bot.control_plane import control_plane
from bot.hud_runtime import hud_runtime
from bot.logic import BOT_BRAND, context_manager
from bot.observability import observability
from bot.persistence_layer import persistence
from bot.runtime_config import BYTE_VERSION, TWITCH_CHAT_MODE
from bot.sentiment_engine import sentiment_engine
from bot.status_runtime import build_status_line
from bot.vision_runtime import vision_runtime

CHANNEL_CONTROL_IRC_ONLY_ACTIONS = {"join", "part"}
HEALTH_ROUTES = {"/health", "/health/", "/healthz", "/healthz/"}


def _is_api_route(route: str) -> bool:
    return route.startswith("/api/")


def _get_context_sync(channel_id: str | None = None) -> Any:
    """Helper para obter contexto de forma síncrona."""
    return context_manager.get(channel_id)


def _resolve_channel_id(
    query: dict[str, list[str]],
    payload: dict[str, Any] | None = None,
    *,
    required: bool = True,
    default: str = "default",
) -> str:
    from_query = str((query.get("channel") or [""])[0] or "").strip().lower()
    if from_query:
        return from_query
    from_payload = str((payload or {}).get("channel_id", "") or "").strip().lower()
    if from_payload:
        return from_payload
    if required:
        raise ValueError("channel_id obrigatorio.")
    return default


def _serialize_runtime_context(ctx: Any) -> dict[str, Any]:
    runtime_observability = getattr(ctx, "live_observability", {}) or {}
    return {
        "channel_id": str(getattr(ctx, "channel_id", "default") or "default"),
        "current_game": str(getattr(ctx, "current_game", "N/A") or "N/A"),
        "stream_vibe": str(getattr(ctx, "stream_vibe", "Conversa") or "Conversa"),
        "last_event": str(getattr(ctx, "last_event", "Bot Online") or "Bot Online"),
        "style_profile": str(getattr(ctx, "style_profile", "") or ""),
        "last_reply": str(getattr(ctx, "last_byte_reply", "") or ""),
        "agent_notes": str(getattr(ctx, "agent_notes", "") or ""),
        "channel_paused": bool(getattr(ctx, "channel_paused", False)),
        "observability": {
            str(key): str(value) for key, value in dict(runtime_observability).items() if str(key)
        },
        "recent_chat_entries": list(getattr(ctx, "recent_chat_entries", []) or [])[-12:],
    }


def _serialize_persisted_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not state:
        return None
    return {
        "channel_id": str(state.get("channel_id") or ""),
        "current_game": str(state.get("current_game") or "N/A"),
        "stream_vibe": str(state.get("stream_vibe") or "Conversa"),
        "last_event": str(state.get("last_event") or "Bot Online"),
        "style_profile": str(state.get("style_profile") or ""),
        "last_reply": str(state.get("last_reply") or ""),
        "updated_at": str(state.get("updated_at") or ""),
        "last_activity": str(state.get("last_activity") or ""),
        "observability": {
            str(key): str(value)
            for key, value in dict(state.get("observability") or {}).items()
            if str(key)
        },
    }


def _serialize_persisted_agent_notes(notes: dict[str, Any] | None) -> dict[str, Any] | None:
    if not notes:
        return None
    return {
        "channel_id": str(notes.get("channel_id") or ""),
        "notes": str(notes.get("notes") or ""),
        "has_notes": bool(notes.get("has_notes")),
        "updated_at": str(notes.get("updated_at") or ""),
        "source": str(notes.get("source") or ""),
    }


def build_observability_payload(channel_id: str | None = None) -> dict[str, Any]:
    ctx = _get_context_sync(channel_id)
    snapshot = observability.snapshot(
        bot_brand=BOT_BRAND,
        bot_version=BYTE_VERSION,
        bot_mode=TWITCH_CHAT_MODE,
        stream_context=ctx,
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
    snapshot["selected_channel"] = str(
        getattr(ctx, "channel_id", channel_id or "default") or "default"
    )
    snapshot["context"] = {
        **(snapshot.get("context") or {}),
        "channel_id": str(getattr(ctx, "channel_id", channel_id or "default") or "default"),
    }
    snapshot["ok"] = True
    return snapshot


def build_channel_context_payload(channel_id: str | None = None) -> dict[str, Any]:
    safe_channel_id = str(channel_id or "default").strip().lower() or "default"
    loaded_before_request = safe_channel_id in set(context_manager.list_active_channels())
    ctx = _get_context_sync(safe_channel_id)
    persisted_state = persistence.load_channel_state_sync(safe_channel_id)
    persisted_history = persistence.load_recent_history_sync(safe_channel_id)
    persisted_agent_notes = persistence.load_agent_notes_sync(safe_channel_id)
    channel_payload = {
        "channel_id": safe_channel_id,
        "runtime_loaded": loaded_before_request,
        "runtime": _serialize_runtime_context(ctx),
        "persisted_state": _serialize_persisted_state(persisted_state),
        "persisted_agent_notes": _serialize_persisted_agent_notes(persisted_agent_notes),
        "persisted_recent_history": list(persisted_history or []),
        "has_persisted_state": bool(persisted_state),
        "has_persisted_notes": bool(
            persisted_agent_notes and persisted_agent_notes.get("has_notes")
        ),
        "has_persisted_history": bool(persisted_history),
    }
    return {
        "ok": True,
        "mode": TWITCH_CHAT_MODE,
        "channel": channel_payload,
    }


def _dashboard_asset_route(handler: Any, route: str) -> bool:
    if route in {"/", "/dashboard", "/dashboard/"}:
        handler._send_dashboard_asset("index.html", "text/html; charset=utf-8")
        return True
    if route in {"/dashboard/hud", "/dashboard/hud/"}:
        handler._send_dashboard_asset("hud.html", "text/html; charset=utf-8")
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

    is_dashboard_route = route in {"/dashboard", "/dashboard/"} or route.startswith("/dashboard/")
    if _is_api_route(route) and not handler._dashboard_authorized():
        handler._send_forbidden()
        return

    if route == "/api/observability":
        channel_id = _resolve_channel_id(query, required=False)
        handler._send_json(handler._build_observability_payload(channel_id), status_code=200)
        return

    if route == "/api/channel-context":
        channel_id = _resolve_channel_id(query, required=False)
        handler._send_json(build_channel_context_payload(channel_id), status_code=200)
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

    if route == "/api/channel-config":
        try:
            channel_id = _resolve_channel_id(query)
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
                "channel": persistence.load_channel_config_sync(channel_id),
            },
            status_code=200,
        )
        return

    if route == "/api/agent-notes":
        try:
            channel_id = _resolve_channel_id(query)
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
                "note": persistence.load_agent_notes_sync(channel_id),
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
        # Usamos o canal default para o dashboard simplificado
        scores = sentiment_engine.get_scores("default")
        scores["vibe"] = sentiment_engine.get_vibe("default")
        handler._send_json({"ok": True, **scores}, status_code=200)
        return

    if route == "/api/vision/status":
        handler._send_json({"ok": True, **vision_runtime.get_status()}, status_code=200)
        return

    if route == "/dashboard/config.js":
        handle_get_config_js(handler)
        return

    if _dashboard_asset_route(handler, route):
        return

    handler._send_text("Not Found", status_code=404)


def handle_get_config_js(handler: Any) -> None:
    from bot.runtime_config import BYTE_DASHBOARD_ADMIN_TOKEN

    payload = f"window.BYTE_CONFIG = {{ adminToken: '{BYTE_DASHBOARD_ADMIN_TOKEN}' }};"
    handler._send_bytes(
        payload.encode("utf-8"), content_type="application/javascript; charset=utf-8"
    )


def handle_put(handler: Any) -> None:
    parsed_path = urlparse(handler.path or "/")
    route = parsed_path.path or "/"
    query = parse_qs(parsed_path.query or "")
    if route not in {"/api/control-plane", "/api/channel-config", "/api/agent-notes"}:
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

    if route == "/api/channel-config":
        try:
            channel_id = _resolve_channel_id(query, payload)
            current_config = persistence.load_channel_config_sync(channel_id)
            next_agent_paused = (
                payload.get("agent_paused")
                if "agent_paused" in payload
                else current_config.get("agent_paused", False)
            )
            channel_config = persistence.save_channel_config_sync(
                channel_id,
                temperature=payload.get("temperature"),
                top_p=payload.get("top_p"),
                agent_paused=next_agent_paused,
            )
            context_manager.apply_channel_config(
                channel_id,
                temperature=channel_config.get("temperature"),
                top_p=channel_config.get("top_p"),
                agent_paused=bool(channel_config.get("agent_paused", False)),
            )
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
                "channel": channel_config,
            },
            status_code=200,
        )
        return

    if route == "/api/agent-notes":
        try:
            channel_id = _resolve_channel_id(query, payload)
            agent_notes = persistence.save_agent_notes_sync(
                channel_id,
                notes=payload.get("notes"),
            )
            context_manager.apply_agent_notes(
                channel_id,
                notes=str(agent_notes.get("notes") or ""),
            )
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
                "note": agent_notes,
            },
            status_code=200,
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


from bot.dashboard_server_routes_post import handle_post

__all__ = [
    "CHANNEL_CONTROL_IRC_ONLY_ACTIONS",
    "_dashboard_asset_route",
    "build_observability_payload",
    "handle_get",
    "handle_get_config_js",
    "handle_post",
    "handle_put",
]
