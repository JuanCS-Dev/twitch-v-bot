# SPDX-License-Identifier: MIT
"""bytecli agent — Agent lifecycle control (suspend, resume, tick, config)."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import output, print_header, print_kv, print_success


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "agent",
        help="Agent lifecycle and configuration",
        description=(
            "Control the agent's lifecycle (suspend, resume), force autonomy ticks, "
            "and view or update the control plane configuration. These operations "
            "affect the agent's global behavior across all channels."
        ),
        epilog=(
            "Examples:\n"
            "  bytecli agent suspend --reason 'deploying update'\n"
            "  bytecli agent resume\n"
            "  bytecli agent tick --force\n"
            "  bytecli agent config\n"
            "  bytecli agent config set autonomy_enabled true\n"
            "  bytecli agent config set budget_limit 5.00\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="agent_cmd", metavar="<action>")

    # suspend
    p_suspend = sub.add_parser(
        "suspend",
        help="Suspend the agent (stops all autonomous actions)",
        description="Suspends the agent. While suspended, no autonomy ticks will execute and no automatic replies will be sent. POST /api/agent/suspend.",
    )
    p_suspend.add_argument(
        "--reason",
        default="",
        help="Human-readable reason for suspension (e.g. 'maintenance', 'deploying')",
    )
    p_suspend.set_defaults(handler=_handle_suspend)

    # resume
    p_resume = sub.add_parser(
        "resume",
        help="Resume the agent (restarts autonomous actions)",
        description="Resumes a previously suspended agent. Normal autonomy ticks and automatic replies will restart. POST /api/agent/resume.",
    )
    p_resume.add_argument("--reason", default="", help="Human-readable reason for resumption")
    p_resume.set_defaults(handler=_handle_resume)

    # tick
    p_tick = sub.add_parser(
        "tick",
        help="Force an autonomy tick (executes pending goals)",
        description="Forces an immediate autonomy tick cycle. The agent will evaluate all enabled goals and execute any that are due. POST /api/autonomy/tick.",
    )
    p_tick.add_argument(
        "--force",
        action="store_true",
        help="Force execution even if no goals are due or conditions aren't met",
    )
    p_tick.set_defaults(handler=_handle_tick)

    # config (show)
    p_config = sub.add_parser(
        "config",
        help="Show or update control plane configuration",
        description=(
            "View the current control plane configuration (autonomy settings, budgets, "
            "intervals, goals, suspension status). Use 'config set' to update individual keys."
        ),
        epilog=(
            "Settable keys include:\n"
            "  autonomy_enabled    bool   Enable/disable autonomy\n"
            "  budget_limit        float  Max cost budget\n"
            "  agent_suspended     bool   Suspend/resume flag\n"
            "  heartbeat_interval  int    Seconds between ticks\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_config_sub = p_config.add_subparsers(dest="config_cmd", metavar="<action>")

    p_config.set_defaults(handler=_handle_config_show)

    # config set
    p_set = p_config_sub.add_parser(
        "set",
        help="Update a config key (auto-detects type: bool/int/float/str)",
        description="Update a single control plane config key. Values are auto-coerced: 'true'/'false' → bool, numbers → int/float, otherwise string. PUT /api/control-plane.",
    )
    p_set.add_argument("key", help="Config key to update (e.g. 'autonomy_enabled', 'budget_limit')")
    p_set.add_argument(
        "value",
        help="New value (auto-detected type: 'true'→bool, '42'→int, '3.14'→float, else string)",
    )
    p_set.set_defaults(handler=_handle_config_set)


def _handle_suspend(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload: dict[str, Any] = {}
    if args.reason:
        payload["reason"] = args.reason

    data = client.post("/api/agent/suspend", payload)
    output(data, json_mode=config.json_output, human_fn=lambda d: print_success("Agent suspended."))


def _handle_resume(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload: dict[str, Any] = {}
    if args.reason:
        payload["reason"] = args.reason

    data = client.post("/api/agent/resume", payload)
    output(data, json_mode=config.json_output, human_fn=lambda d: print_success("Agent resumed."))


def _handle_tick(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload = {"force": args.force}
    data = client.post("/api/autonomy/tick", payload)
    output(data, json_mode=config.json_output, human_fn=_human_tick)


def _human_tick(data: dict[str, Any]) -> None:
    print_success("Autonomy tick executed.")
    result = data.get("result", data)
    goals = result.get("goals_processed", result.get("goals", []))
    if goals:
        print_header("Goals Processed")
        for g in goals:
            if isinstance(g, dict):
                print_kv({"Goal": g.get("id", "—"), "Result": g.get("outcome", "—")})
            else:
                print_kv({"Goal": str(g)})


def _handle_config_show(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    data = client.get("/api/control-plane")
    output(data, json_mode=config.json_output, human_fn=_human_config)


def _human_config(data: dict[str, Any]) -> None:
    cfg = data.get("config", data)
    print_header("Control Plane Configuration")
    # Show top-level config keys
    display = {}
    for key, value in cfg.items():
        if key == "goals":
            display["Goals Count"] = len(value) if isinstance(value, list) else value
        elif isinstance(value, str | int | float | bool):
            display[key] = value
    print_kv(display)


def _handle_config_set(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    key = args.key
    raw_value = args.value

    # Type coercion: try bool, int, float, then string
    value: Any
    if raw_value.lower() in ("true", "false"):
        value = raw_value.lower() == "true"
    else:
        try:
            value = int(raw_value)
        except ValueError:
            try:
                value = float(raw_value)
            except ValueError:
                value = raw_value

    payload = {key: value}
    data = client.put("/api/control-plane", payload)
    output(
        data,
        json_mode=config.json_output,
        human_fn=lambda d: print_success(f"Config '{key}' updated to '{value}'."),
    )
