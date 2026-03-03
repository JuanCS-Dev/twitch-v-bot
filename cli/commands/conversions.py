# SPDX-License-Identifier: MIT
"""bytecli conversions — Revenue/conversion tracking (list, add). Alias: revenue."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import format_timestamp, output, print_header, print_success, print_table


def register(subparsers: argparse._SubParsersAction) -> None:
    # Primary command: conversions
    parser = subparsers.add_parser(
        "conversions",
        help="Revenue and conversion tracking (list, add)",
        description=(
            "Track business metrics, subscriptions, donations, and custom conversion events. "
            "This feeds into the agent's ROI and cost observability calculations."
        ),
        epilog=(
            "Examples:\n"
            "  bytecli conversions list --limit 10\n"
            "  bytecli conversions add --event 'tier1_sub' --value 4.99 --source 'twitch'\n"
            "  bytecli revenue add --event 'donation' --value 10.00\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="conv_cmd", metavar="<action>")
    parser.set_defaults(handler=_handle_list)

    p_list = sub.add_parser("list", help="List recent conversions and revenue events")
    p_list.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    p_list.set_defaults(handler=_handle_list)

    p_add = sub.add_parser(
        "add",
        help="Register a conversion event manually",
        description="Records a new conversion event. POST /api/observability/conversion.",
    )
    p_add.add_argument("--event", required=True, help="Conversion event type (e.g. 'sub', 'dono')")
    p_add.add_argument(
        "--value", required=True, type=float, help="Monetary or point value (e.g. 4.99)"
    )
    p_add.add_argument("--source", default="cli", help="Attribution source (default: cli)")
    p_add.set_defaults(handler=_handle_add)

    # Alias: revenue → conversions
    parser_alias = subparsers.add_parser("revenue", help="Alias for 'conversions'")
    sub_alias = parser_alias.add_subparsers(dest="conv_cmd", metavar="<action>")
    parser_alias.set_defaults(handler=_handle_list)

    p_list_a = sub_alias.add_parser("list", help="List recent revenue events")
    p_list_a.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    p_list_a.set_defaults(handler=_handle_list)

    p_add_a = sub_alias.add_parser("add", help="Register a revenue event manually")
    p_add_a.add_argument("--event", required=True, help="Event type")
    p_add_a.add_argument("--value", required=True, type=float, help="Monetary value")
    p_add_a.add_argument("--source", default="cli", help="Attribution source (default: cli)")
    p_add_a.set_defaults(handler=_handle_add)


def _handle_list(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params: dict[str, str] = {"limit": str(args.limit)}
    if config.channel != "default":
        params["channel"] = config.channel
    data = client.get("/api/observability/conversions", params)
    output(data, json_mode=config.json_output, human_fn=_human_list)


def _human_list(data: dict[str, Any]) -> None:
    conversions = data.get("conversions", [])
    print_header(f"Revenue Conversions ({len(conversions)})")
    if not conversions:
        return

    rows = []
    for c in conversions:
        rows.append(
            [
                str(c.get("event_type", c.get("event", "—"))),
                f"{c.get('value', 0):.2f}",
                str(c.get("source", "—")),
                format_timestamp(c.get("created_at", c.get("timestamp"))),
            ]
        )
    print_table(["Event", "Value", "Source", "Created"], rows)


def _handle_add(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload: dict[str, Any] = {
        "event_type": args.event,
        "value": args.value,
        "source": args.source,
    }
    if config.channel != "default":
        payload["channel_id"] = config.channel

    data = client.post("/api/observability/conversion", payload)
    output(
        data,
        json_mode=config.json_output,
        human_fn=lambda d: print_success(f"Conversion registered: {args.event} = {args.value}"),
    )
