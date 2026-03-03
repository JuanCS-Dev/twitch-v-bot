# SPDX-License-Identifier: MIT
"""bytecli observe — Observability, sentiment, and history."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import format_timestamp, output, print_header, print_kv, print_table


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("observe", help="Observability and telemetry")
    sub = parser.add_subparsers(dest="observe_cmd", metavar="<view>")
    parser.set_defaults(handler=_handle_overview)

    # sentiment
    p_sent = sub.add_parser("sentiment", help="Chat sentiment scores and vibe")
    p_sent.set_defaults(handler=_handle_sentiment)

    # history
    p_hist = sub.add_parser("history", help="Observability snapshot timeline")
    p_hist.add_argument("--limit", type=int, default=24, help="Max timeline entries (default: 24)")
    p_hist.set_defaults(handler=_handle_history)


def _handle_overview(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params = {"channel": config.channel} if config.channel != "default" else {}
    data = client.get("/api/observability", params)
    output(data, json_mode=config.json_output, human_fn=_human_overview)


def _human_overview(data: dict[str, Any]) -> None:
    counters = data.get("counters", {})
    cost = data.get("cost", {})
    interactions = data.get("interactions", {})

    print_header("Observability Snapshot")
    print_kv(
        {
            "Mode": data.get("mode", "—"),
            "Messages Received": counters.get("chat_messages_received", 0),
            "Replies Sent": counters.get("chat_replies_sent", 0),
            "Trigger Events": counters.get("trigger_events", 0),
            "Errors": counters.get("errors", 0),
            "Total Tokens": counters.get("total_tokens", 0),
            "Estimated Cost": f"${cost.get('total_usd', 0):.4f}",
        }
    )

    if interactions:
        print_header("Recent Interactions")
        rows = []
        for item in (interactions.get("recent", []) or [])[:10]:
            rows.append(
                [
                    str(item.get("type", "—")),
                    str(item.get("channel", "—")),
                    str(item.get("text", "—"))[:60],
                    format_timestamp(item.get("timestamp")),
                ]
            )
        if rows:
            print_table(["Type", "Channel", "Text", "Time"], rows)


def _handle_sentiment(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params = {"channel": config.channel} if config.channel != "default" else {}
    data = client.get("/api/sentiment/scores", params)
    output(data, json_mode=config.json_output, human_fn=_human_sentiment)


def _human_sentiment(data: dict[str, Any]) -> None:
    print_header("Sentiment Analysis")
    sentiment = data.get("sentiment", data)
    print_kv(
        {
            "Channel": data.get("channel_id", "—"),
            "Average": sentiment.get("avg", 0),
            "Total": sentiment.get("total", 0),
            "Count": sentiment.get("count", 0),
            "Positive": sentiment.get("positive", 0),
            "Negative": sentiment.get("negative", 0),
        }
    )

    health = data.get("stream_health", {})
    if health:
        print_header("Stream Health")
        print_kv(health)


def _handle_history(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params: dict[str, str] = {"limit": str(args.limit)}
    if config.channel != "default":
        params["channel"] = config.channel
    data = client.get("/api/observability/history", params)
    output(data, json_mode=config.json_output, human_fn=_human_history)


def _human_history(data: dict[str, Any]) -> None:
    timeline = data.get("timeline", [])
    print_header(f"Observability Timeline ({len(timeline)} points)")
    if not timeline:
        return

    rows = []
    for point in timeline[:30]:
        rows.append(
            [
                format_timestamp(point.get("captured_at")),
                str(point.get("channel_id", "—")),
                str(point.get("chat_messages_received", 0)),
                str(point.get("chat_replies_sent", 0)),
                str(point.get("errors", 0)),
            ]
        )
    print_table(["Captured At", "Channel", "Msgs In", "Replies", "Errors"], rows)
