# SPDX-License-Identifier: MIT
"""bytecli clips — Clip pipeline and vision status."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import format_timestamp, output, print_header, print_kv, print_table


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "clips",
        help="Clip pipeline and vision status",
        description="View the autonomic clipping pipeline jobs and the vision ingestion status.",
        epilog=("Examples:\n  bytecli clips jobs\n  bytecli clips vision\n"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="clips_cmd", metavar="<view>")
    parser.set_defaults(handler=_handle_jobs)

    p_jobs = sub.add_parser("jobs", help="List recent clip generation jobs")
    p_jobs.set_defaults(handler=_handle_jobs)

    p_vision = sub.add_parser("vision", help="Show vision pipeline ingestion status")
    p_vision.set_defaults(handler=_handle_vision)


def _handle_jobs(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    data = client.get("/api/clip-jobs")
    output(data, json_mode=config.json_output, human_fn=_human_jobs)


def _human_jobs(data: dict[str, Any]) -> None:
    items = data.get("items", [])
    print_header(f"Clip Jobs ({len(items)})")
    if not items:
        return

    rows = []
    for job in items:
        rows.append(
            [
                str(job.get("id", job.get("candidate_id", "—")))[:16],
                str(job.get("status", "—")),
                str(job.get("source", "—")),
                str(job.get("suggested_title", "—"))[:40],
                format_timestamp(job.get("created_at", job.get("source_ts"))),
            ]
        )
    print_table(["ID", "Status", "Source", "Title", "Created"], rows)


def _handle_vision(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    data = client.get("/api/vision/status")
    output(data, json_mode=config.json_output, human_fn=_human_vision)


def _human_vision(data: dict[str, Any]) -> None:
    print_header("Vision Pipeline")
    print_kv(
        {
            "Frame Count": data.get("frame_count", 0),
            "Last Ingest": format_timestamp(data.get("last_ingest_at")),
            "Last Analysis": data.get("last_analysis", "—") or "—",
        }
    )
