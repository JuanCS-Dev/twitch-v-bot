# SPDX-License-Identifier: MIT
"""bytecli webhooks — Webhook management (list, add, test)."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import output, print_header, print_success, print_table


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "webhooks",
        help="Webhook management (list, add, test)",
        description=(
            "Manage outbound webhooks. The agent can push real-time events "
            "(like goal outcomes, memory insights, stream status) to external APIs."
        ),
        epilog=(
            "Examples:\n"
            "  bytecli webhooks list\n"
            "  bytecli webhooks add https://api.example.com/webhook --events 'goal_completed' --secret 'my-hmac-secret'\n"
            "  bytecli webhooks test wh_123abc\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="webhooks_cmd", metavar="<action>")
    parser.set_defaults(handler=_handle_list)

    p_list = sub.add_parser("list", help="List registered webhooks and their status")
    p_list.set_defaults(handler=_handle_list)

    p_add = sub.add_parser(
        "add",
        help="Register a new outbound webhook",
        description="Registers an endpoint to receive POST payloads on specific agent events.",
    )
    p_add.add_argument("url", help="Webhook destination URL")
    p_add.add_argument(
        "--events", default="", help="Comma-separated event types (empty = all events)"
    )
    p_add.add_argument(
        "--secret", default="", help="Optional HMAC-SHA256 signing secret for payload verification"
    )
    p_add.add_argument("--name", default="", help="Display name for the webhook")
    p_add.set_defaults(handler=_handle_add)

    p_test = sub.add_parser("test", help="Send a simulated ping event to a webhook")
    p_test.add_argument("webhook_id", help="Webhook ID to test")
    p_test.set_defaults(handler=_handle_test)


def _handle_list(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params = {"channel": config.channel} if config.channel != "default" else {}
    data = client.get("/api/webhooks", params)
    output(data, json_mode=config.json_output, human_fn=_human_list)


def _human_list(data: dict[str, Any]) -> None:
    webhooks = data.get("webhooks", [])
    print_header(f"Webhooks ({len(webhooks)})")
    if not webhooks:
        return

    rows = []
    for wh in webhooks:
        active = "✓" if wh.get("is_active") else "✗"
        events = ", ".join(wh.get("event_types", []) or []) or "(all)"
        rows.append(
            [
                str(wh.get("id", "—"))[:16],
                str(wh.get("url", "—"))[:40],
                active,
                events[:30],
            ]
        )
    print_table(["ID", "URL", "Active", "Events"], rows)


def _handle_add(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload: dict[str, Any] = {
        "url": args.url,
        "channel_id": config.channel,
        "is_active": True,
    }
    if args.events:
        payload["event_types"] = [e.strip() for e in args.events.split(",") if e.strip()]
    if args.secret:
        payload["secret"] = args.secret
    if args.name:
        payload["name"] = args.name

    data = client.put("/api/webhooks", payload)
    output(
        data,
        json_mode=config.json_output,
        human_fn=lambda d: print_success(f"Webhook registered: {args.url}"),
    )


def _handle_test(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload = {
        "webhook_id": args.webhook_id,
        "channel_id": config.channel,
    }
    data = client.post("/api/webhooks/test", payload)
    output(
        data,
        json_mode=config.json_output,
        human_fn=lambda d: print_success(f"Test event sent to webhook '{args.webhook_id}'."),
    )
