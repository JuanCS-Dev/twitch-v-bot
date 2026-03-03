# SPDX-License-Identifier: MIT
"""bytecli goals — Goal management (list, show, add, enable, disable, remove)."""

from __future__ import annotations

import argparse
import json
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import output, print_error, print_header, print_kv, print_success, print_table


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "goals",
        help="Manage agent goals",
        description=(
            "Goals are recurring tasks the agent executes autonomously on a schedule. "
            "Each goal has an ID, prompt, risk level, interval/cron schedule, and KPI tracking. "
            "Default goals include: chat_pulse (900s), streamer_hint (600s), "
            "safety_watch (300s), detect_clip (600s, disabled).\n\n"
            "All goal mutations use read-modify-write against GET/PUT /api/control-plane."
        ),
        epilog=(
            "Risk levels:\n"
            "  auto_chat           Agent sends a chat message autonomously\n"
            "  suggest_streamer    Agent suggests something to the streamer\n"
            "  moderation_action   Agent takes a moderation action\n"
            "  clip_candidate      Agent detects a clip-worthy moment\n\n"
            "Examples:\n"
            "  bytecli goals list\n"
            "  bytecli goals show chat_pulse\n"
            "  bytecli goals add --id fun_fact --name 'Fun Facts' --prompt 'Share a fun fact' --risk auto_chat --interval 1800\n"
            "  bytecli goals enable detect_clip\n"
            "  bytecli goals disable chat_pulse\n"
            "  bytecli goals remove fun_fact\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="goals_cmd", metavar="<action>")
    parser.set_defaults(handler=_handle_list)

    # list
    p_list = sub.add_parser(
        "list", help="List all goals with ID, name, risk, schedule, and enabled status"
    )
    p_list.set_defaults(handler=_handle_list)

    # show
    p_show = sub.add_parser(
        "show",
        help="Show full details of a specific goal",
        description="Displays all fields of a goal: id, name, prompt, risk, interval, cron, enabled, kpi_name, target_value, window_minutes, comparison, session_result.",
    )
    p_show.add_argument("goal_id", help="Goal ID to inspect (e.g. 'chat_pulse', 'detect_clip')")
    p_show.set_defaults(handler=_handle_show)

    # add
    p_add = sub.add_parser(
        "add",
        help="Add a new goal",
        description="Creates a new goal and appends it to the goals list. All required fields must be specified. KPI tracking is auto-configured based on the risk level.",
    )
    p_add.add_argument(
        "--id",
        required=True,
        dest="goal_id",
        help="Unique goal ID (e.g. 'fun_fact', 'daily_recap'). Must not already exist.",
    )
    p_add.add_argument("--name", required=True, help="Human-readable display name for the goal")
    p_add.add_argument(
        "--prompt", required=True, help="Prompt instruction sent to the AI when this goal fires"
    )
    p_add.add_argument(
        "--risk",
        required=True,
        choices=["auto_chat", "suggest_streamer", "moderation_action", "clip_candidate"],
        help="Risk level that determines how the action is processed",
    )
    p_add.add_argument(
        "--interval",
        type=int,
        required=True,
        help="Interval in seconds between goal executions (e.g. 900 = every 15 minutes)",
    )
    p_add.add_argument(
        "--cron",
        default="",
        help="Cron expression (optional, overrides interval if provided). Format: '*/5 * * * *'",
    )
    p_add.add_argument(
        "--enabled",
        action="store_true",
        default=True,
        help="Enable the goal immediately (default: true)",
    )
    p_add.set_defaults(handler=_handle_add)

    # enable
    p_enable = sub.add_parser("enable", help="Enable a goal (sets enabled=true)")
    p_enable.add_argument("goal_id", help="Goal ID to enable")
    p_enable.set_defaults(handler=_handle_enable)

    # disable
    p_disable = sub.add_parser(
        "disable", help="Disable a goal (sets enabled=false, goal is kept but won't fire)"
    )
    p_disable.add_argument("goal_id", help="Goal ID to disable")
    p_disable.set_defaults(handler=_handle_disable)

    # remove
    p_remove = sub.add_parser("remove", help="Remove a goal permanently from the list")
    p_remove.add_argument("goal_id", help="Goal ID to remove")
    p_remove.set_defaults(handler=_handle_remove)


def _get_goals(client: ByteClient) -> list[dict[str, Any]]:
    """Fetch current goals list from control plane."""
    data = client.get("/api/control-plane")
    cfg = data.get("config", data)
    return list(cfg.get("goals", []))


def _update_goals(client: ByteClient, goals: list[dict[str, Any]]) -> dict[str, Any]:
    """Push updated goals list to control plane."""
    return client.put("/api/control-plane", {"goals": goals})


def _find_goal(goals: list[dict[str, Any]], goal_id: str) -> tuple[int, dict[str, Any] | None]:
    """Find a goal by ID. Returns (index, goal) or (-1, None)."""
    for i, g in enumerate(goals):
        if g.get("id") == goal_id:
            return i, g
    return -1, None


def _handle_list(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    goals = _get_goals(client)
    output(goals, json_mode=config.json_output, human_fn=_human_list)


def _human_list(goals: list[dict[str, Any]]) -> None:
    print_header(f"Goals ({len(goals)})")
    if not goals:
        return

    rows = []
    for g in goals:
        enabled = "✓" if g.get("enabled") else "✗"
        interval = str(g.get("interval_seconds", "—"))
        cron = g.get("cron_expression", "")
        schedule = cron if cron else f"{interval}s"
        rows.append(
            [
                str(g.get("id", "—")),
                str(g.get("name", "—")),
                str(g.get("risk", "—")),
                schedule,
                enabled,
            ]
        )
    print_table(["ID", "Name", "Risk", "Schedule", "On"], rows)


def _handle_show(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    goals = _get_goals(client)
    _, goal = _find_goal(goals, args.goal_id)
    if goal is None:
        print_error(f"Goal '{args.goal_id}' not found.")
        return

    output(goal, json_mode=config.json_output, human_fn=_human_show)


def _human_show(goal: dict[str, Any]) -> None:
    print_header(f"Goal: {goal.get('name', goal.get('id', '?'))}")
    print_kv(
        {
            "ID": goal.get("id"),
            "Name": goal.get("name"),
            "Prompt": goal.get("prompt"),
            "Risk": goal.get("risk"),
            "Interval (s)": goal.get("interval_seconds"),
            "Cron": goal.get("cron_expression", "—"),
            "Enabled": goal.get("enabled"),
            "KPI Name": goal.get("kpi_name"),
            "Target Value": goal.get("target_value"),
            "Window (min)": goal.get("window_minutes"),
            "Comparison": goal.get("comparison"),
            "Session Result": goal.get("session_result", {}),
        }
    )


def _handle_add(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    goals = _get_goals(client)
    _, existing = _find_goal(goals, args.goal_id)
    if existing is not None:
        print_error(f"Goal '{args.goal_id}' already exists. Use 'goals remove' first.")
        return

    kpi_map = {
        "auto_chat": "auto_chat_sent",
        "clip_candidate": "clip_candidate_queued",
    }
    new_goal: dict[str, Any] = {
        "id": args.goal_id,
        "name": args.name,
        "prompt": args.prompt,
        "risk": args.risk,
        "interval_seconds": args.interval,
        "enabled": args.enabled,
        "kpi_name": kpi_map.get(args.risk, "action_queued"),
        "target_value": 1.0,
        "window_minutes": 60,
        "comparison": "gte",
        "session_result": {},
    }
    if args.cron:
        new_goal["cron_expression"] = args.cron

    goals.append(new_goal)
    _update_goals(client, goals)
    print_success(f"Goal '{args.goal_id}' created.")


def _handle_enable(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    _toggle_goal(client, args.goal_id, enabled=True)


def _handle_disable(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    _toggle_goal(client, args.goal_id, enabled=False)


def _toggle_goal(client: ByteClient, goal_id: str, *, enabled: bool) -> None:
    goals = _get_goals(client)
    idx, goal = _find_goal(goals, goal_id)
    if goal is None:
        print_error(f"Goal '{goal_id}' not found.")
        return

    goals[idx]["enabled"] = enabled
    _update_goals(client, goals)
    verb = "enabled" if enabled else "disabled"
    print_success(f"Goal '{goal_id}' {verb}.")


def _handle_remove(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    goals = _get_goals(client)
    idx, _ = _find_goal(goals, args.goal_id)
    if idx < 0:
        print_error(f"Goal '{args.goal_id}' not found.")
        return

    goals.pop(idx)
    _update_goals(client, goals)
    print_success(f"Goal '{args.goal_id}' removed.")
