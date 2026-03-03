# SPDX-License-Identifier: MIT
"""bytecli actions — Action queue management (list, approve, reject)."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import format_timestamp, output, print_header, print_success, print_table


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("actions", help="Manage the action queue")
    sub = parser.add_subparsers(dest="actions_cmd", metavar="<action>")
    parser.set_defaults(handler=_handle_list)

    # list
    p_list = sub.add_parser("list", help="List actions in the queue")
    p_list.add_argument(
        "--status", default="", help="Filter by status (pending, approved, rejected, expired)"
    )
    p_list.add_argument("--limit", type=int, default=80, help="Max results (default: 80)")
    p_list.set_defaults(handler=_handle_list)

    # pending (shortcut)
    p_pending = sub.add_parser("pending", help="List pending actions only")
    p_pending.add_argument("--limit", type=int, default=80, help="Max results")
    p_pending.set_defaults(handler=_handle_pending)

    # approve
    p_approve = sub.add_parser("approve", help="Approve an action")
    p_approve.add_argument("action_id", help="Action ID to approve")
    p_approve.add_argument("--note", default="", help="Approval note")
    p_approve.set_defaults(handler=_handle_approve)

    # reject
    p_reject = sub.add_parser("reject", help="Reject an action")
    p_reject.add_argument("action_id", help="Action ID to reject")
    p_reject.add_argument("--note", default="", help="Rejection note")
    p_reject.set_defaults(handler=_handle_reject)


def _handle_list(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params: dict[str, str] = {"limit": str(args.limit)}
    status = getattr(args, "status", "")
    if status:
        params["status"] = status
    data = client.get("/api/action-queue", params)
    output(data, json_mode=config.json_output, human_fn=_human_list)


def _handle_pending(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params = {"status": "pending", "limit": str(args.limit)}
    data = client.get("/api/action-queue", params)
    output(data, json_mode=config.json_output, human_fn=_human_list)


def _human_list(data: dict[str, Any]) -> None:
    actions = data.get("actions", data.get("items", []))
    print_header(f"Action Queue ({len(actions)} actions)")
    if not actions:
        return

    rows = []
    for a in actions:
        rows.append(
            [
                str(a.get("id", "—"))[:12],
                str(a.get("kind", "—")),
                str(a.get("risk", "—")),
                str(a.get("title", "—"))[:40],
                str(a.get("status", "—")),
                format_timestamp(a.get("created_at")),
            ]
        )
    print_table(["ID", "Kind", "Risk", "Title", "Status", "Created"], rows)


def _handle_approve(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload = {"decision": "approve"}
    if args.note:
        payload["note"] = args.note
    data = client.post(f"/api/action-queue/{args.action_id}/decision", payload)
    output(
        data,
        json_mode=config.json_output,
        human_fn=lambda d: print_success(f"Action '{args.action_id}' approved."),
    )


def _handle_reject(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload = {"decision": "reject"}
    if args.note:
        payload["note"] = args.note
    data = client.post(f"/api/action-queue/{args.action_id}/decision", payload)
    output(
        data,
        json_mode=config.json_output,
        human_fn=lambda d: print_success(f"Action '{args.action_id}' rejected."),
    )
