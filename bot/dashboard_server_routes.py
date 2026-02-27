import asyncio
import mimetypes
from collections.abc import Callable
from typing import Any

from bot.clip_jobs_runtime import clip_jobs
from bot.coaching_runtime import coaching_runtime
from bot.control_plane import control_plane
from bot.dashboard_http_helpers import (
    build_control_plane_state_payload,
    parse_dashboard_request_path,
    require_auth_and_read_payload,
    require_dashboard_auth,
    send_invalid_request,
)
from bot.hud_runtime import hud_runtime
from bot.logic import BOT_BRAND, context_manager
from bot.observability import observability
from bot.observability_history_contract import normalize_observability_history_point
from bot.persistence_layer import persistence
from bot.post_stream_report import build_post_stream_report
from bot.runtime_config import BYTE_VERSION, TWITCH_CHAT_MODE
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


def _resolve_int_query_param(
    query: dict[str, list[str]],
    key: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = str((query.get(key) or [str(default)])[0] or str(default)).strip()
    try:
        parsed = int(raw_value)
    except ValueError:
        return default
    if parsed < minimum:
        return minimum
    if parsed > maximum:
        return maximum
    return parsed


def _resolve_bool_query_param(
    query: dict[str, list[str]],
    key: str,
    *,
    default: bool = False,
) -> bool:
    fallback = "1" if default else "0"
    raw_value = str((query.get(key) or [fallback])[0] or fallback).strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


def _resolve_text_query_param(
    query: dict[str, list[str]],
    key: str,
    *,
    default: str = "",
) -> str:
    raw_value = str((query.get(key) or [default])[0] or default)
    return raw_value.strip()


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
        "persona_name": str(getattr(ctx, "persona_name", "") or ""),
        "tone": str(getattr(ctx, "persona_tone", "") or ""),
        "emote_vocab": list(getattr(ctx, "persona_emote_vocab", []) or []),
        "lore": str(getattr(ctx, "persona_lore", "") or ""),
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


def _serialize_persisted_channel_identity(
    identity: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not identity:
        return None
    return {
        "channel_id": str(identity.get("channel_id") or ""),
        "persona_name": str(identity.get("persona_name") or ""),
        "tone": str(identity.get("tone") or ""),
        "emote_vocab": list(identity.get("emote_vocab") or []),
        "lore": str(identity.get("lore") or ""),
        "has_identity": bool(identity.get("has_identity")),
        "updated_at": str(identity.get("updated_at") or ""),
        "source": str(identity.get("source") or ""),
    }


def _merge_channel_directives_payload(
    channel_config: dict[str, Any] | None,
    channel_identity: dict[str, Any] | None,
) -> dict[str, Any]:
    config = dict(channel_config or {})
    identity = dict(channel_identity or {})
    channel_id = str(config.get("channel_id") or identity.get("channel_id") or "default")

    return {
        "channel_id": channel_id,
        "temperature": config.get("temperature"),
        "top_p": config.get("top_p"),
        "agent_paused": bool(config.get("agent_paused", False)),
        "has_override": bool(config.get("has_override")),
        "updated_at": str(config.get("updated_at") or ""),
        "source": str(config.get("source") or ""),
        "persona_name": str(identity.get("persona_name") or ""),
        "tone": str(identity.get("tone") or ""),
        "emote_vocab": list(identity.get("emote_vocab") or []),
        "lore": str(identity.get("lore") or ""),
        "has_identity": bool(identity.get("has_identity")),
        "identity_updated_at": str(identity.get("updated_at") or ""),
        "identity_source": str(identity.get("source") or ""),
    }


def _serialize_observability_history_point(point: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_observability_history_point(point, default_channel_id="default")


def build_observability_payload(channel_id: str | None = None) -> dict[str, Any]:
    ctx = _get_context_sync(channel_id)
    selected_channel = str(getattr(ctx, "channel_id", channel_id or "default") or "default")
    snapshot = observability.snapshot(
        bot_brand=BOT_BRAND,
        bot_version=BYTE_VERSION,
        bot_mode=TWITCH_CHAT_MODE,
        stream_context=ctx,
        channel_id=selected_channel,
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
    snapshot["selected_channel"] = selected_channel
    snapshot["context"] = {
        **(snapshot.get("context") or {}),
        "channel_id": selected_channel,
    }
    snapshot["coaching"] = coaching_runtime.evaluate_and_emit(
        snapshot,
        channel_id=selected_channel,
    )
    snapshot["ok"] = True
    return snapshot


def build_channel_context_payload(channel_id: str | None = None) -> dict[str, Any]:
    safe_channel_id = str(channel_id or "default").strip().lower() or "default"
    loaded_before_request = safe_channel_id in set(context_manager.list_active_channels())
    ctx = _get_context_sync(safe_channel_id)
    persisted_state = persistence.load_channel_state_sync(safe_channel_id)
    persisted_history = persistence.load_recent_history_sync(safe_channel_id)
    persisted_agent_notes = persistence.load_agent_notes_sync(safe_channel_id)
    persisted_channel_identity = persistence.load_channel_identity_sync(safe_channel_id)
    channel_payload = {
        "channel_id": safe_channel_id,
        "runtime_loaded": loaded_before_request,
        "runtime": _serialize_runtime_context(ctx),
        "persisted_state": _serialize_persisted_state(persisted_state),
        "persisted_agent_notes": _serialize_persisted_agent_notes(persisted_agent_notes),
        "persisted_channel_identity": _serialize_persisted_channel_identity(
            persisted_channel_identity
        ),
        "persisted_recent_history": list(persisted_history or []),
        "has_persisted_state": bool(persisted_state),
        "has_persisted_notes": bool(
            persisted_agent_notes and persisted_agent_notes.get("has_notes")
        ),
        "has_persisted_identity": bool(
            persisted_channel_identity and persisted_channel_identity.get("has_identity")
        ),
        "has_persisted_history": bool(persisted_history),
    }
    return {
        "ok": True,
        "mode": TWITCH_CHAT_MODE,
        "channel": channel_payload,
    }


def build_observability_history_payload(
    channel_id: str | None = None,
    *,
    limit: int = 24,
    compare_limit: int = 6,
) -> dict[str, Any]:
    safe_channel_id = str(channel_id or "default").strip().lower() or "default"
    safe_limit = max(1, min(int(limit or 24), 120))
    safe_compare_limit = max(1, min(int(compare_limit or 6), 24))

    load_history = getattr(persistence, "load_observability_channel_history_sync", None)
    load_comparison = getattr(
        persistence,
        "load_latest_observability_channel_snapshots_sync",
        None,
    )
    timeline_points = (
        list(load_history(safe_channel_id, limit=safe_limit)) if callable(load_history) else []
    )
    comparison_points = (
        list(load_comparison(limit=safe_compare_limit)) if callable(load_comparison) else []
    )

    serialized_timeline = [
        _serialize_observability_history_point(point) for point in list(timeline_points or [])
    ]
    serialized_comparison = [
        _serialize_observability_history_point(point) for point in list(comparison_points or [])
    ]
    selected_present = any(
        str(point.get("channel_id") or "") == safe_channel_id for point in serialized_comparison
    )
    if not selected_present and serialized_timeline:
        serialized_comparison.insert(0, serialized_timeline[0])
    serialized_comparison.sort(key=lambda row: str(row.get("captured_at") or ""), reverse=True)
    serialized_comparison = serialized_comparison[:safe_compare_limit]

    return {
        "ok": True,
        "mode": TWITCH_CHAT_MODE,
        "selected_channel": safe_channel_id,
        "timeline": serialized_timeline,
        "comparison": serialized_comparison,
        "has_history": bool(serialized_timeline),
        "has_comparison": bool(serialized_comparison),
        "limits": {
            "timeline": safe_limit,
            "comparison": safe_compare_limit,
        },
    }


def build_sentiment_scores_payload(channel_id: str | None = None) -> dict[str, Any]:
    ctx = _get_context_sync(channel_id)
    selected_channel = str(getattr(ctx, "channel_id", channel_id or "default") or "default")
    snapshot = observability.snapshot(
        bot_brand=BOT_BRAND,
        bot_version=BYTE_VERSION,
        bot_mode=TWITCH_CHAT_MODE,
        stream_context=ctx,
        channel_id=selected_channel,
    )
    sentiment = dict(snapshot.get("sentiment") or {})
    stream_health = dict(snapshot.get("stream_health") or {})
    return {
        "ok": True,
        "mode": TWITCH_CHAT_MODE,
        "channel_id": selected_channel,
        **sentiment,
        "sentiment": sentiment,
        "stream_health": stream_health,
    }


def build_post_stream_report_payload(
    channel_id: str | None = None,
    *,
    generate: bool = False,
    trigger: str = "manual_dashboard",
) -> dict[str, Any]:
    safe_channel_id = str(channel_id or "default").strip().lower() or "default"
    history_points = persistence.load_observability_channel_history_sync(safe_channel_id, limit=120)
    latest_report = persistence.load_latest_post_stream_report_sync(safe_channel_id)
    if not generate:
        return {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            "selected_channel": safe_channel_id,
            "has_report": bool(latest_report),
            "generated": False,
            "report": dict(latest_report or {}),
            "history_points": len(history_points),
        }

    observability_payload = build_observability_payload(safe_channel_id)
    generated_report = build_post_stream_report(
        channel_id=safe_channel_id,
        history_points=list(history_points or []),
        observability_snapshot=observability_payload,
        trigger=trigger,
    )
    persisted_report = persistence.save_post_stream_report_sync(
        safe_channel_id,
        generated_report,
        trigger=trigger,
    )
    return {
        "ok": True,
        "mode": TWITCH_CHAT_MODE,
        "selected_channel": safe_channel_id,
        "has_report": True,
        "generated": True,
        "report": dict(persisted_report),
        "history_points": len(history_points),
    }


def build_semantic_memory_payload(
    channel_id: str | None = None,
    *,
    query: str = "",
    limit: int = 8,
    search_limit: int = 60,
) -> dict[str, Any]:
    safe_channel_id = str(channel_id or "default").strip().lower() or "default"
    safe_limit = max(1, min(int(limit or 8), 20))
    safe_search_limit = max(1, min(int(search_limit or 60), 360))
    safe_query = str(query or "").strip()

    entries = persistence.load_semantic_memory_entries_sync(
        safe_channel_id,
        limit=safe_search_limit,
    )
    matches = (
        persistence.search_semantic_memory_entries_sync(
            safe_channel_id,
            query=safe_query,
            limit=safe_limit,
            search_limit=safe_search_limit,
        )
        if safe_query
        else list(entries[:safe_limit])
    )
    selected_entries = list(entries[:safe_limit])

    return {
        "ok": True,
        "mode": TWITCH_CHAT_MODE,
        "selected_channel": safe_channel_id,
        "query": safe_query,
        "entries": selected_entries,
        "matches": list(matches or []),
        "has_entries": bool(selected_entries),
        "has_matches": bool(matches),
        "limits": {
            "list": safe_limit,
            "search": safe_search_limit,
        },
    }


def build_ops_playbooks_payload(
    channel_id: str | None = None,
) -> dict[str, Any]:
    safe_channel_id = str(channel_id or "default").strip().lower() or "default"
    snapshot = control_plane.ops_playbooks_snapshot(channel_id=safe_channel_id)
    return {
        "ok": True,
        "mode": TWITCH_CHAT_MODE,
        "selected_channel": safe_channel_id,
        **snapshot,
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


def handle_get_config_js(handler: Any) -> None:
    from bot.runtime_config import BYTE_DASHBOARD_ADMIN_TOKEN

    payload = f"window.BYTE_CONFIG = {{ adminToken: '{BYTE_DASHBOARD_ADMIN_TOKEN}' }};"
    handler._send_bytes(
        payload.encode("utf-8"), content_type="application/javascript; charset=utf-8"
    )


def _resolve_action_queue_limit(query: dict[str, list[str]]) -> int:
    limit_raw = str((query.get("limit") or ["80"])[0] or "80")
    try:
        return int(limit_raw)
    except ValueError:
        return 80


def _handle_get_observability(handler: Any, query: dict[str, list[str]]) -> None:
    channel_id = _resolve_channel_id(query, required=False)
    handler._send_json(handler._build_observability_payload(channel_id), status_code=200)


def _handle_get_channel_context(handler: Any, query: dict[str, list[str]]) -> None:
    channel_id = _resolve_channel_id(query, required=False)
    handler._send_json(build_channel_context_payload(channel_id), status_code=200)


def _handle_get_observability_history(handler: Any, query: dict[str, list[str]]) -> None:
    channel_id = _resolve_channel_id(query, required=False)
    limit = _resolve_int_query_param(
        query,
        "limit",
        default=24,
        minimum=1,
        maximum=120,
    )
    compare_limit = _resolve_int_query_param(
        query,
        "compare_limit",
        default=6,
        minimum=1,
        maximum=24,
    )
    handler._send_json(
        build_observability_history_payload(
            channel_id,
            limit=limit,
            compare_limit=compare_limit,
        ),
        status_code=200,
    )


def _handle_get_control_plane(handler: Any, _query: dict[str, list[str]]) -> None:
    handler._send_json(build_control_plane_state_payload(), status_code=200)


def _handle_get_channel_config(handler: Any, query: dict[str, list[str]]) -> None:
    try:
        channel_id = _resolve_channel_id(query)
    except ValueError as error:
        send_invalid_request(handler, str(error))
        return
    channel_config = persistence.load_channel_config_sync(channel_id)
    channel_identity = persistence.load_channel_identity_sync(channel_id)
    handler._send_json(
        {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            "channel": _merge_channel_directives_payload(channel_config, channel_identity),
        },
        status_code=200,
    )


def _handle_get_agent_notes(handler: Any, query: dict[str, list[str]]) -> None:
    try:
        channel_id = _resolve_channel_id(query)
    except ValueError as error:
        send_invalid_request(handler, str(error))
        return
    handler._send_json(
        {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            "note": persistence.load_agent_notes_sync(channel_id),
        },
        status_code=200,
    )


def _handle_get_action_queue(handler: Any, query: dict[str, list[str]]) -> None:
    status_filter = str((query.get("status") or [""])[0] or "").strip().lower()
    queue_payload = control_plane.list_actions(
        status=status_filter or None,
        limit=_resolve_action_queue_limit(query),
    )
    handler._send_json(
        {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            **queue_payload,
        },
        status_code=200,
    )


def _handle_get_clip_jobs(handler: Any, _query: dict[str, list[str]]) -> None:
    handler._send_json(
        {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            "items": clip_jobs.get_jobs(),
        },
        status_code=200,
    )


def _handle_get_hud_messages(handler: Any, query: dict[str, list[str]]) -> None:
    since_raw = str((query.get("since") or ["0"])[0] or "0")
    try:
        since = float(since_raw)
    except ValueError:
        since = 0.0
    messages = hud_runtime.get_messages(since=since)
    handler._send_json({"ok": True, "messages": messages}, status_code=200)


def _handle_get_sentiment_scores(handler: Any, query: dict[str, list[str]]) -> None:
    channel_id = _resolve_channel_id(query, required=False)
    handler._send_json(build_sentiment_scores_payload(channel_id), status_code=200)


def _handle_get_post_stream_report(handler: Any, query: dict[str, list[str]]) -> None:
    channel_id = _resolve_channel_id(query, required=False)
    generate = _resolve_bool_query_param(query, "generate", default=False)
    handler._send_json(
        build_post_stream_report_payload(
            channel_id,
            generate=generate,
            trigger="manual_dashboard",
        ),
        status_code=200,
    )


def _handle_get_semantic_memory(handler: Any, query: dict[str, list[str]]) -> None:
    channel_id = _resolve_channel_id(query, required=False)
    limit = _resolve_int_query_param(
        query,
        "limit",
        default=8,
        minimum=1,
        maximum=20,
    )
    search_limit = _resolve_int_query_param(
        query,
        "search_limit",
        default=60,
        minimum=1,
        maximum=360,
    )
    memory_query = _resolve_text_query_param(query, "query", default="")
    handler._send_json(
        build_semantic_memory_payload(
            channel_id,
            query=memory_query,
            limit=limit,
            search_limit=search_limit,
        ),
        status_code=200,
    )


def _handle_get_ops_playbooks(handler: Any, query: dict[str, list[str]]) -> None:
    channel_id = _resolve_channel_id(query, required=False)
    handler._send_json(
        build_ops_playbooks_payload(channel_id),
        status_code=200,
    )


def _handle_get_vision_status(handler: Any, _query: dict[str, list[str]]) -> None:
    handler._send_json({"ok": True, **vision_runtime.get_status()}, status_code=200)


def _handle_get_revenue_conversions(handler: Any, query: dict[str, list[str]]) -> None:
    channel_id = _resolve_channel_id(query, required=False)
    limit = _resolve_int_query_param(query, "limit", default=20, minimum=1, maximum=100)
    conversions = persistence.load_recent_revenue_conversions_sync(channel_id, limit=limit)
    handler._send_json(
        {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            "channel_id": channel_id,
            "conversions": conversions,
            "limit": limit,
        },
        status_code=200,
    )


def _handle_get_webhooks(handler: Any, query: dict[str, list[str]]) -> None:
    try:
        channel_id = _resolve_channel_id(query)
    except ValueError as error:
        send_invalid_request(handler, str(error))
        return
    webhooks = persistence.load_webhooks_sync(channel_id)
    handler._send_json(
        {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            "webhooks": webhooks,
        },
        status_code=200,
    )


def _handle_get_dashboard_config(handler: Any, _query: dict[str, list[str]]) -> None:
    handle_get_config_js(handler)


_GET_ROUTE_HANDLERS: dict[str, Callable[[Any, dict[str, list[str]]], None]] = {
    "/api/observability": _handle_get_observability,
    "/api/channel-context": _handle_get_channel_context,
    "/api/observability/history": _handle_get_observability_history,
    "/api/control-plane": _handle_get_control_plane,
    "/api/channel-config": _handle_get_channel_config,
    "/api/agent-notes": _handle_get_agent_notes,
    "/api/action-queue": _handle_get_action_queue,
    "/api/clip-jobs": _handle_get_clip_jobs,
    "/api/hud/messages": _handle_get_hud_messages,
    "/api/sentiment/scores": _handle_get_sentiment_scores,
    "/api/observability/post-stream-report": _handle_get_post_stream_report,
    "/api/semantic-memory": _handle_get_semantic_memory,
    "/api/ops-playbooks": _handle_get_ops_playbooks,
    "/api/vision/status": _handle_get_vision_status,
    "/api/observability/conversions": _handle_get_revenue_conversions,
    "/api/webhooks": _handle_get_webhooks,
    "/dashboard/config.js": _handle_get_dashboard_config,
}


def handle_get(handler: Any) -> None:
    route, query = parse_dashboard_request_path(handler.path)
    if route in HEALTH_ROUTES:
        handler._send_text("AGENT_ONLINE", status_code=200)
        return

    if _is_api_route(route) and not require_dashboard_auth(handler):
        return

    route_handler = _GET_ROUTE_HANDLERS.get(route)
    if route_handler is not None:
        route_handler(handler, query)
        return

    if _dashboard_asset_route(handler, route):
        return

    handler._send_text("Not Found", status_code=404)


def _handle_put_channel_config(
    handler: Any,
    query: dict[str, list[str]],
    payload: dict[str, Any],
) -> None:
    try:
        channel_id = _resolve_channel_id(query, payload)
        current_config = persistence.load_channel_config_sync(channel_id)
        current_identity = persistence.load_channel_identity_sync(channel_id)
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
        channel_identity = persistence.save_channel_identity_sync(
            channel_id,
            persona_name=(
                payload.get("persona_name")
                if "persona_name" in payload
                else current_identity.get("persona_name")
            ),
            tone=payload.get("tone") if "tone" in payload else current_identity.get("tone"),
            emote_vocab=(
                payload.get("emote_vocab")
                if "emote_vocab" in payload
                else current_identity.get("emote_vocab")
            ),
            lore=payload.get("lore") if "lore" in payload else current_identity.get("lore"),
        )
        context_manager.apply_channel_config(
            channel_id,
            temperature=channel_config.get("temperature"),
            top_p=channel_config.get("top_p"),
            agent_paused=bool(channel_config.get("agent_paused", False)),
        )
        context_manager.apply_channel_identity(
            channel_id,
            persona_name=str(channel_identity.get("persona_name") or ""),
            tone=str(channel_identity.get("tone") or ""),
            emote_vocab=list(channel_identity.get("emote_vocab") or []),
            lore=str(channel_identity.get("lore") or ""),
        )
    except ValueError as error:
        send_invalid_request(handler, str(error))
        return

    handler._send_json(
        {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            "channel": _merge_channel_directives_payload(channel_config, channel_identity),
        },
        status_code=200,
    )


def _handle_put_agent_notes(
    handler: Any,
    query: dict[str, list[str]],
    payload: dict[str, Any],
) -> None:
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
        send_invalid_request(handler, str(error))
        return

    handler._send_json(
        {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            "note": agent_notes,
        },
        status_code=200,
    )


def _handle_put_control_plane(
    handler: Any,
    _query: dict[str, list[str]],
    payload: dict[str, Any],
) -> None:
    try:
        updated_config = control_plane.update_config(payload)
    except ValueError as error:
        send_invalid_request(handler, str(error))
        return

    handler._send_json(
        {
            **build_control_plane_state_payload(),
            "config": updated_config,
        },
        status_code=200,
    )


def _handle_put_semantic_memory(
    handler: Any,
    query: dict[str, list[str]],
    payload: dict[str, Any],
) -> None:
    try:
        channel_id = _resolve_channel_id(query, payload)
        entry = persistence.save_semantic_memory_entry_sync(
            channel_id,
            content=payload.get("content"),
            memory_type=payload.get("memory_type"),
            tags=payload.get("tags"),
            context=payload.get("context"),
            entry_id=payload.get("entry_id"),
        )
    except ValueError as error:
        send_invalid_request(handler, str(error))
        return

    handler._send_json(
        {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            "entry": entry,
        },
        status_code=200,
    )


def _handle_put_webhooks(
    handler: Any,
    query: dict[str, list[str]],
    payload: dict[str, Any],
) -> None:
    try:
        channel_id = _resolve_channel_id(query, payload)
        webhook = persistence.save_webhook_sync(channel_id, payload)
    except ValueError as error:
        send_invalid_request(handler, str(error))
        return

    handler._send_json(
        {
            "ok": True,
            "mode": TWITCH_CHAT_MODE,
            "webhook": webhook,
        },
        status_code=200,
    )


_PUT_ROUTE_HANDLERS: dict[str, Callable[[Any, dict[str, list[str]], dict[str, Any]], None]] = {
    "/api/control-plane": _handle_put_control_plane,
    "/api/channel-config": _handle_put_channel_config,
    "/api/agent-notes": _handle_put_agent_notes,
    "/api/semantic-memory": _handle_put_semantic_memory,
    "/api/webhooks": _handle_put_webhooks,
}


def handle_put(handler: Any) -> None:
    route, query = parse_dashboard_request_path(handler.path)
    route_handler = _PUT_ROUTE_HANDLERS.get(route)
    if route_handler is None:
        handler._send_text("Not Found", status_code=404)
        return

    payload = require_auth_and_read_payload(handler)
    if payload is None:
        return

    route_handler(handler, query, payload)


from bot.dashboard_server_routes_post import handle_post

__all__ = [
    "CHANNEL_CONTROL_IRC_ONLY_ACTIONS",
    "_dashboard_asset_route",
    "build_channel_context_payload",
    "build_observability_history_payload",
    "build_observability_payload",
    "build_ops_playbooks_payload",
    "build_post_stream_report_payload",
    "build_semantic_memory_payload",
    "build_sentiment_scores_payload",
    "handle_get",
    "handle_get_config_js",
    "handle_post",
    "handle_put",
]
