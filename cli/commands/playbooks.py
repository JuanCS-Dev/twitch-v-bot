# SPDX-License-Identifier: MIT
"""bytecli playbooks — Ops playbook management (list, trigger)."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import output, print_header, print_kv, print_success, print_table


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "playbooks",
        help="Operational playbooks management (list, trigger)",
        description=(
            "Manage ops playbooks. Playbooks are predefined operational strategies "
            "(like dynamic slow mode, ad breaks) that trigger automatically based on metrics."
        ),
        epilog=(
            "Examples:\n"
            "  bytecli playbooks list\n"
            "  bytecli playbooks trigger dynamic_slow_mode --force\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="playbooks_cmd", metavar="<action>")
    parser.set_defaults(handler=_handle_list)

    p_list = sub.add_parser("list", help="List playbooks with status and outcomes")
    p_list.set_defaults(handler=_handle_list)

    p_trigger = sub.add_parser(
        "trigger",
        help="Manually trigger a playbook",
        description="Forces a playbook to execute immediately. POST /api/ops-playbooks/trigger.",
    )
    p_trigger.add_argument("playbook_id", help="Playbook ID to trigger (e.g. 'dynamic_slow_mode')")
    p_trigger.add_argument("--force", action="store_true", help="Force trigger even if on cooldown")
    p_trigger.set_defaults(handler=_handle_trigger)


def _handle_list(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params = {"channel": config.channel} if config.channel != "default" else {}
    data = client.get("/api/ops-playbooks", params)
    output(data, json_mode=config.json_output, human_fn=_human_list)


def _human_list(data: dict[str, Any]) -> None:
    playbooks = data.get("playbooks", data.get("definitions", []))
    print_header(f"Ops Playbooks ({len(playbooks)})")
    if not playbooks:
        return

    rows = []
    for pb in playbooks:
        if isinstance(pb, dict):
            rows.append(
                [
                    str(pb.get("id", "—")),
                    str(pb.get("name", "—")),
                    str(pb.get("state", pb.get("status", "—"))),
                    str(pb.get("trigger_metric", "—")),
                    str(pb.get("last_outcome", "—")),
                ]
            )
    print_table(["ID", "Name", "State", "Trigger Metric", "Outcome"], rows)


def _handle_trigger(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload: dict[str, Any] = {
        "playbook_id": args.playbook_id,
        "channel_id": config.channel,
        "force": args.force,
    }
    data = client.post("/api/ops-playbooks/trigger", payload)
    output(
        data,
        json_mode=config.json_output,
        human_fn=lambda d: print_success(f"Playbook '{args.playbook_id}' triggered."),
    )
