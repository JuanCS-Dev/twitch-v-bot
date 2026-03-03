# SPDX-License-Identifier: MIT
"""bytecli report — Post-stream reports (show, generate)."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import format_timestamp, output, print_header, print_kv, print_success


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "report",
        help="Post-stream analysis reports (show, generate)",
        description=(
            "View or generate post-stream reports. These reports synthesize the "
            "stream's observational data, sentiment, chat history, and executed playbooks "
            "into a comprehensive summarization."
        ),
        epilog=("Examples:\n  bytecli report show\n  bytecli report generate\n"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="report_cmd", metavar="<action>")
    parser.set_defaults(handler=_handle_show)

    p_show = sub.add_parser("show", help="Display the latest post-stream report")
    p_show.set_defaults(handler=_handle_show)

    p_gen = sub.add_parser("generate", help="Force generate a new post-stream report now")
    p_gen.set_defaults(handler=_handle_generate)


def _handle_show(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params: dict[str, str] = {}
    if config.channel != "default":
        params["channel"] = config.channel
    data = client.get("/api/observability/post-stream-report", params)
    output(data, json_mode=config.json_output, human_fn=_human_report)


def _handle_generate(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params: dict[str, str] = {"generate": "true"}
    if config.channel != "default":
        params["channel"] = config.channel
    data = client.get("/api/observability/post-stream-report", params)
    output(data, json_mode=config.json_output, human_fn=_human_report_generated)


def _human_report(data: dict[str, Any]) -> None:
    has_report = data.get("has_report", False)
    print_header("Post-Stream Report")
    if not has_report:
        print("  (no report available — use 'bytecli report generate' to create one)")
        return

    report = data.get("report", {})
    print_kv(
        {
            "Channel": data.get("selected_channel", "—"),
            "Generated": data.get("generated", False),
            "History Points": data.get("history_points", 0),
        }
    )

    if report:
        print()
        # Print report content if available
        for key, value in report.items():
            if key in ("id", "channel_id", "created_at", "trigger"):
                continue
            if isinstance(value, str) and len(value) > 100:
                print(f"  {key}:")
                for line in value.split("\n"):
                    print(f"    {line}")
            elif isinstance(value, dict):
                print(f"  {key}: {value}")
            else:
                print(f"  {key}: {value}")


def _human_report_generated(data: dict[str, Any]) -> None:
    print_success("Report generated successfully.")
    _human_report(data)
