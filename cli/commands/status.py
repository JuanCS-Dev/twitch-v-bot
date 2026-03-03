# SPDX-License-Identifier: MIT
"""bytecli status — Quick health and status overview of the agent."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import (
    format_timestamp,
    output,
    print_error,
    print_header,
    print_kv,
    print_success,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "status",
        help="Show agent health, mode, and key metrics",
        description=(
            "Quick dashboard showing whether the agent is online, its current mode "
            "(IRC/EventSub), active goals count, messages processed, errors, and "
            "estimated cost. Combines data from /health, /api/control-plane, and "
            "/api/observability into a single view."
        ),
        epilog=(
            "Examples:\n"
            "  bytecli status              # Check if agent is running\n"
            "  bytecli --json status       # Get raw JSON for scripting\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.set_defaults(handler=_handle)


def _handle(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    online = client.health_check()
    cp_data: dict[str, Any] = {}
    obs_data: dict[str, Any] = {}

    if online:
        cp_data = client.get("/api/control-plane")
        obs_data = client.get("/api/observability")

    combined = {
        "online": online,
        "url": config.url,
        "control_plane": cp_data,
        "observability": obs_data,
    }

    output(combined, json_mode=config.json_output, human_fn=_human_output)


def _human_output(data: dict[str, Any]) -> None:
    online = data.get("online", False)
    url = data.get("url", "")

    if online:
        print_success(f"Agent ONLINE at {url}")
    else:
        print_error(f"Agent OFFLINE at {url}")
        return

    cp = data.get("control_plane", {})
    obs = data.get("observability", {})

    # Control Plane
    cp_config = cp.get("config", {})
    print_header("Control Plane")
    print_kv(
        {
            "Mode": cp.get("mode", "—"),
            "Agent Suspended": cp_config.get("agent_suspended", False),
            "Autonomy Enabled": cp_config.get("autonomy_enabled", True),
            "Active Goals": len(cp_config.get("goals", [])),
            "Budget": f"{cp_config.get('budget_used', 0)}/{cp_config.get('budget_limit', 0)}",
        }
    )

    # Observability
    counters = obs.get("counters", {})
    cost = obs.get("cost", {})
    print_header("Observability")
    print_kv(
        {
            "Messages Received": counters.get("chat_messages_received", 0),
            "Replies Sent": counters.get("chat_replies_sent", 0),
            "Triggers": counters.get("trigger_events", 0),
            "Errors": counters.get("errors", 0),
            "Tokens Used": counters.get("total_tokens", 0),
            "Estimated Cost": f"${cost.get('total_usd', 0):.4f}",
            "Last Activity": format_timestamp(obs.get("last_activity_at")),
        }
    )
