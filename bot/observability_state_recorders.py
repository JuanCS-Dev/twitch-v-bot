from typing import Any

from bot.observability_helpers import clip_preview
from bot.observability_state_core import append_event_locked, bump_timeline_locked, prune_locked


def record_chat_message_locked(
    state: Any,
    *,
    now: float,
    author_name: str,
    source: str,
    text: str = "",
) -> None:
    safe_source = (source or "unknown").strip().lower() or "unknown"
    safe_author = (author_name or "").strip().lower()
    message_text = (text or "").strip()
    is_command = bool(message_text.startswith("!"))
    lowered_text = message_text.lower()
    has_url = "http://" in lowered_text or "https://" in lowered_text

    state._counters["chat_messages_total"] += 1
    state._counters[f"chat_messages_{safe_source}"] += 1
    bump_timeline_locked(state, now, chat_messages=1)
    state._chat_events.append(
        {
            "ts": now,
            "source": safe_source,
            "author": safe_author,
            "length": len(message_text),
            "is_command": is_command,
            "has_url": has_url,
        }
    )
    if safe_author:
        state._known_chatters.add(safe_author)
        state._chatter_last_seen[safe_author] = now
        state._chatter_message_totals[safe_author] += 1
    if is_command:
        state._counters["chat_prefixed_messages"] += 1
    if has_url:
        state._counters["chat_messages_with_url"] += 1
    prune_locked(state, now)


def record_byte_trigger_locked(
    state: Any,
    *,
    now: float,
    prompt: str,
    source: str,
    author_name: str = "",
) -> None:
    safe_source = (source or "unknown").strip().lower() or "unknown"
    safe_author_key = (author_name or "").strip().lower() or "viewer"
    safe_author = clip_preview(author_name or "viewer", max_chars=32)
    prompt_preview = clip_preview(prompt or "(empty prompt)", max_chars=120)

    state._counters["byte_triggers_total"] += 1
    state._counters[f"byte_triggers_{safe_source}"] += 1
    state._trigger_user_totals[safe_author_key] += 1
    state._byte_trigger_events.append({"ts": now, "author": safe_author_key, "source": safe_source})
    state._last_prompt = prompt_preview
    bump_timeline_locked(state, now, byte_triggers=1)
    append_event_locked(state, now, "INFO", "byte_trigger", f"{safe_author}: {prompt_preview}")
    prune_locked(state, now)


def record_reply_locked(state: Any, *, now: float, text: str) -> None:
    reply_preview = clip_preview(text or "", max_chars=140)
    if not reply_preview:
        return
    state._counters["replies_total"] += 1
    state._counters["reply_chars_total"] += len(reply_preview)
    state._last_reply = reply_preview
    bump_timeline_locked(state, now, replies_sent=1)
    prune_locked(state, now)


def record_quality_gate_locked(
    state: Any,
    *,
    now: float,
    outcome: str,
    reason: str,
) -> None:
    safe_outcome = (outcome or "unknown").strip().lower() or "unknown"
    safe_reason = clip_preview(reason or "n/a", max_chars=120)
    event_level = "WARN" if safe_outcome in {"retry", "fallback"} else "INFO"

    state._counters["quality_checks_total"] += 1
    state._counters[f"quality_{safe_outcome}_total"] += 1
    state._quality_events.append(
        {
            "ts": now,
            "outcome": safe_outcome,
            "reason": safe_reason,
        }
    )
    append_event_locked(state, now, event_level, "quality_gate", f"{safe_outcome}: {safe_reason}")
    prune_locked(state, now)


def record_byte_interaction_locked(
    state: Any,
    *,
    now: float,
    route: str,
    author_name: str,
    prompt_chars: int,
    reply_parts: int,
    reply_chars: int,
    serious: bool,
    follow_up: bool,
    current_events: bool,
    latency_ms: float,
) -> None:
    safe_route = (route or "unknown").strip().lower() or "unknown"
    safe_author = clip_preview(author_name or "viewer", max_chars=32)

    state._counters["interactions_total"] += 1
    state._route_counts[safe_route] += 1
    state._counters["prompt_chars_total"] += max(0, int(prompt_chars))
    state._counters["interaction_reply_parts_total"] += max(0, int(reply_parts))
    state._counters["interaction_reply_chars_total"] += max(0, int(reply_chars))
    llm_route = safe_route.startswith("llm")
    useful_llm = llm_route and "fallback" not in safe_route
    state._interaction_events.append(
        {
            "ts": now,
            "route": safe_route,
            "is_llm": llm_route,
            "is_useful_llm": useful_llm,
        }
    )
    if safe_route.startswith("llm"):
        state._counters["llm_interactions_total"] += 1
        bump_timeline_locked(state, now, llm_requests=1)
    if serious:
        state._counters["serious_interactions_total"] += 1
    if follow_up:
        state._counters["follow_up_interactions_total"] += 1
    if current_events:
        state._counters["current_events_interactions_total"] += 1
    if latency_ms >= 0:
        state._latencies_ms.append(float(latency_ms))
    details = (
        f"{safe_route} by {safe_author} | prompt={max(0, int(prompt_chars))} chars | "
        f"replies={max(0, int(reply_parts))} | latency={round(max(0.0, latency_ms), 1)}ms"
    )
    append_event_locked(state, now, "INFO", "byte_interaction", details)
    prune_locked(state, now)


def record_token_usage_locked(
    state: Any,
    *,
    now: float,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: float,
) -> None:
    safe_input = max(0, int(input_tokens))
    safe_output = max(0, int(output_tokens))
    safe_cost = max(0.0, float(estimated_cost_usd))

    state._counters["token_input_total"] += safe_input
    state._counters["token_output_total"] += safe_output
    state._estimated_cost_usd_total += safe_cost
    state._token_usage_events.append(
        {
            "ts": now,
            "input_tokens": safe_input,
            "output_tokens": safe_output,
            "estimated_cost_usd": safe_cost,
        }
    )
    prune_locked(state, now)


def record_autonomy_goal_locked(
    state: Any,
    *,
    now: float,
    risk: str,
    outcome: str,
    details: str = "",
) -> None:
    safe_risk = (risk or "unknown").strip().lower() or "unknown"
    safe_outcome = (outcome or "unknown").strip().lower() or "unknown"
    details_preview = clip_preview(details or "", max_chars=100)

    state._counters["autonomy_goals_total"] += 1
    state._counters[f"autonomy_{safe_risk}_{safe_outcome}_total"] += 1
    state._autonomy_goal_events.append(
        {
            "ts": now,
            "risk": safe_risk,
            "outcome": safe_outcome,
        }
    )
    append_event_locked(
        state,
        now,
        "INFO",
        "autonomy_goal",
        f"{safe_risk}/{safe_outcome}: {details_preview or 'ok'}",
    )
    prune_locked(state, now)


def record_auto_scene_update_locked(
    state: Any,
    *,
    now: float,
    update_types: list[str],
) -> None:
    if not update_types:
        return
    safe_types = sorted({(item or "").strip().lower() for item in update_types if item})
    if not safe_types:
        return
    state._counters["auto_scene_updates_total"] += len(safe_types)
    append_event_locked(state, now, "INFO", "scene_update", f"updated: {', '.join(safe_types)}")
    prune_locked(state, now)


def record_token_refresh_locked(state: Any, *, now: float, reason: str) -> None:
    safe_reason = clip_preview(reason or "n/a", max_chars=100)
    state._counters["token_refreshes_total"] += 1
    append_event_locked(state, now, "WARN", "token_refresh", safe_reason)
    prune_locked(state, now)


def record_auth_failure_locked(state: Any, *, now: float, details: str) -> None:
    safe_details = clip_preview(details or "n/a", max_chars=120)
    state._counters["auth_failures_total"] += 1
    state._counters["errors_total"] += 1
    bump_timeline_locked(state, now, errors=1)
    append_event_locked(state, now, "ERROR", "auth_failure", safe_details)
    prune_locked(state, now)


def record_error_locked(state: Any, *, now: float, category: str, details: str) -> None:
    safe_category = (category or "unknown").strip().lower() or "unknown"
    safe_details = clip_preview(details or "n/a", max_chars=140)
    state._counters["errors_total"] += 1
    state._counters[f"errors_{safe_category}"] += 1
    bump_timeline_locked(state, now, errors=1)
    append_event_locked(state, now, "ERROR", safe_category, safe_details)
    prune_locked(state, now)


def record_vision_frame_locked(state: Any, *, now: float, analysis: str) -> None:
    safe_analysis = clip_preview(analysis or "", max_chars=120)
    state._counters["vision_frames_total"] += 1
    append_event_locked(state, now, "INFO", "vision_frame", safe_analysis or "frame ingested")
    prune_locked(state, now)
