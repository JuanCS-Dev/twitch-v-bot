from collections import Counter
from typing import Any

from bot.observability_helpers import (
    LEADERBOARD_LIMIT,
    percentage,
)


def compute_chat_metrics(
    chat_events: list[dict[str, Any]],
    now: float,
) -> dict[str, Any]:
    cutoff_10m = now - 600
    cutoff_60m = now - 3600

    events_10m = [e for e in chat_events if float(e.get("ts", 0.0)) >= cutoff_10m]
    events_60m = [e for e in chat_events if float(e.get("ts", 0.0)) >= cutoff_60m]

    count_10m = len(events_10m)
    count_60m = len(events_60m)

    avg_len_10m = (
        round(sum(int(e.get("length", 0)) for e in events_10m) / count_10m, 1) if count_10m else 0.0
    )
    avg_len_60m = (
        round(sum(int(e.get("length", 0)) for e in events_60m) / count_60m, 1) if count_60m else 0.0
    )

    command_60m = sum(1 for e in events_60m if bool(e.get("is_command", False)))
    url_60m = sum(1 for e in events_60m if bool(e.get("has_url", False)))

    return {
        "messages_10m": count_10m,
        "messages_60m": count_60m,
        "messages_per_minute_10m": round(count_10m / 10, 2),
        "messages_per_minute_60m": round(count_60m / 60, 2),
        "avg_message_length_10m": avg_len_10m,
        "avg_message_length_60m": avg_len_60m,
        "prefixed_commands_60m": command_60m,
        "prefixed_command_ratio_60m": percentage(command_60m, count_60m),
        "url_messages_60m": url_60m,
        "url_ratio_60m": percentage(url_60m, count_60m),
        "events_60m": events_60m,  # return for further processing (e.g. source counts)
    }


def compute_interaction_metrics(
    interaction_events: list[dict[str, Any]],
    now: float,
) -> dict[str, Any]:
    cutoff_60m = now - 3600
    events_60m = [e for e in interaction_events if float(e.get("ts", 0.0)) >= cutoff_60m]

    llm_60m = sum(1 for e in events_60m if bool(e.get("is_llm", False)))
    useful_60m = sum(1 for e in events_60m if bool(e.get("is_useful_llm", False)))

    return {
        "llm_interactions_60m": llm_60m,
        "useful_llm_interactions_60m": useful_60m,
        "useful_engagement_rate_60m": percentage(useful_60m, llm_60m),
    }


def compute_quality_metrics(
    quality_events: list[dict[str, Any]],
    llm_interactions_60m: int,
    now: float,
) -> dict[str, Any]:
    cutoff_60m = now - 3600
    events_60m = [e for e in quality_events if float(e.get("ts", 0.0)) >= cutoff_60m]

    retry_60m = sum(1 for e in events_60m if str(e.get("outcome", "")).strip().lower() == "retry")
    success_60m = sum(
        1 for e in events_60m if str(e.get("outcome", "")).strip().lower() == "retry_success"
    )
    fallback_60m = sum(
        1 for e in events_60m if str(e.get("outcome", "")).strip().lower() == "fallback"
    )

    return {
        "quality_retry_60m": retry_60m,
        "quality_retry_success_60m": success_60m,
        "quality_fallback_60m": fallback_60m,
        "correction_rate_60m": percentage(success_60m, retry_60m),
        "correction_trigger_rate_60m": percentage(retry_60m, llm_interactions_60m),
    }


def compute_token_metrics(
    token_usage_events: list[dict[str, Any]],
    now: float,
) -> dict[str, Any]:
    cutoff_60m = now - 3600
    events_60m = [e for e in token_usage_events if float(e.get("ts", 0.0)) >= cutoff_60m]

    input_60m = sum(max(0, int(e.get("input_tokens", 0) or 0)) for e in events_60m)
    output_60m = sum(max(0, int(e.get("output_tokens", 0) or 0)) for e in events_60m)
    cost_60m = sum(max(0.0, float(e.get("estimated_cost_usd", 0.0) or 0.0)) for e in events_60m)

    return {
        "token_input_60m": input_60m,
        "token_output_60m": output_60m,
        "estimated_cost_usd_60m": cost_60m,
    }


def compute_autonomy_metrics(
    autonomy_events: list[dict[str, Any]],
    now: float,
) -> dict[str, Any]:
    cutoff_60m = now - 3600
    events_60m = [e for e in autonomy_events if float(e.get("ts", 0.0)) >= cutoff_60m]

    total_60m = len(events_60m)
    ignored_60m = sum(
        1 for e in events_60m if str(e.get("outcome", "")).strip().lower() == "ignored"
    )

    return {
        "autonomy_goals_60m": total_60m,
        "ignored_total_60m": ignored_60m,
        "ignored_rate_60m": percentage(ignored_60m, total_60m),
    }


def compute_leaderboards(
    chat_events_60m: list[dict[str, Any]],
    trigger_events_60m: list[dict[str, Any]],
    chatter_totals: dict[str, int],
    trigger_totals: dict[str, int],
) -> dict[str, Any]:
    chatters_60m: Counter[str] = Counter()
    source_counts_60m: Counter[str] = Counter()

    for e in chat_events_60m:
        author = str(e.get("author", "") or "").strip().lower()
        source = str(e.get("source", "unknown") or "unknown")
        if author:
            chatters_60m[author] += 1
        source_counts_60m[source] += 1

    triggers_60m: Counter[str] = Counter()
    for e in trigger_events_60m:
        author = str(e.get("author", "") or "").strip().lower()
        if author:
            triggers_60m[author] += 1

    top_chatters_60m = [
        {"author": a, "messages": c} for a, c in chatters_60m.most_common(LEADERBOARD_LIMIT)
    ]
    top_chatters_total = [
        {"author": a, "messages": c}
        for a, c in Counter(chatter_totals).most_common(LEADERBOARD_LIMIT)
    ]
    top_triggers_60m = [
        {"author": a, "triggers": c} for a, c in triggers_60m.most_common(LEADERBOARD_LIMIT)
    ]
    top_triggers_total = [
        {"author": a, "triggers": c}
        for a, c in Counter(trigger_totals).most_common(LEADERBOARD_LIMIT)
    ]

    return {
        "top_chatters_60m": top_chatters_60m,
        "top_chatters_total": top_chatters_total,
        "top_trigger_users_60m": top_triggers_60m,
        "top_trigger_users_total": top_triggers_total,
        "source_counts_60m": source_counts_60m,
    }
