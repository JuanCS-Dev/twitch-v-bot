# SPDX-License-Identifier: MIT
"""bytecli memory — Semantic memory management (list, search, add)."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import (
    format_timestamp,
    output,
    print_header,
    print_kv,
    print_success,
    print_table,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "memory",
        help="Semantic memory management (list, search, add)",
        description=(
            "Manage the agent's long-term semantic memory. The agent stores observations, "
            "rules, and facts here to recall them in future conversations.\n\n"
            "Endpoints: GET /api/memory, POST /api/memory, GET /api/memory/search"
        ),
        epilog=(
            "Examples:\n"
            "  bytecli memory list --limit 10\n"
            "  bytecli memory search 'favorite game'\n"
            "  bytecli memory add 'Streamer hates backseating' --tags rule,preference\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="memory_cmd", metavar="<action>")
    parser.set_defaults(handler=_handle_list)

    # list
    p_list = sub.add_parser("list", help="List recent semantic memory entries")
    p_list.add_argument("--limit", type=int, default=8, help="Max entries to return (default: 8)")
    p_list.set_defaults(handler=_handle_list)

    # search
    p_search = sub.add_parser(
        "search",
        help="Search memory by text/similarity",
        description="Searches semantic memory using embedding similarity or full-text search.",
    )
    p_search.add_argument("query", help="Search query text")
    p_search.add_argument("--limit", type=int, default=8, help="Max results (default: 8)")
    p_search.set_defaults(handler=_handle_search)

    # add
    p_add = sub.add_parser(
        "add",
        help="Add a new manually-authored memory entry",
        description="Inserts a new semantic memory entry. The agent will read this context automatically based on relevance.",
    )
    p_add.add_argument("content", help="The memory content to store")
    p_add.add_argument(
        "--type", dest="memory_type", default="manual", help="Memory type (default: manual)"
    )
    p_add.add_argument("--tags", default="", help="Comma-separated tags (e.g. 'rule,preference')")
    p_add.set_defaults(handler=_handle_add)


def _handle_list(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params: dict[str, str] = {"limit": str(args.limit)}
    if config.channel != "default":
        params["channel"] = config.channel
    data = client.get("/api/semantic-memory", params)
    output(data, json_mode=config.json_output, human_fn=_human_list)


def _human_list(data: dict[str, Any]) -> None:
    entries = data.get("entries", [])
    print_header(f"Semantic Memory ({len(entries)} entries)")
    if not entries:
        return

    rows = []
    for e in entries:
        content = str(e.get("content", ""))[:50]
        mem_type = str(e.get("memory_type", e.get("type", "—")))
        tags = ", ".join(e.get("tags", []) or [])
        rows.append([content, mem_type, tags[:30], format_timestamp(e.get("created_at"))])
    print_table(["Content", "Type", "Tags", "Created"], rows)


def _handle_search(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params: dict[str, str] = {
        "query": args.query,
        "limit": str(args.limit),
    }
    if config.channel != "default":
        params["channel"] = config.channel
    data = client.get("/api/semantic-memory", params)
    output(data, json_mode=config.json_output, human_fn=_human_search)


def _human_search(data: dict[str, Any]) -> None:
    matches = data.get("matches", [])
    diag = data.get("search_diagnostics", {})
    print_header(f"Search Results ({len(matches)} matches)")

    if diag:
        print_kv(
            {
                "Engine": diag.get("engine", "—"),
                "Candidates": diag.get("candidate_count", 0),
                "Min Similarity": diag.get("min_similarity", "—"),
            }
        )
        print()

    if not matches:
        return

    rows = []
    for m in matches:
        content = str(m.get("content", ""))[:50]
        similarity = m.get("similarity", m.get("score", "—"))
        if isinstance(similarity, float):
            similarity = f"{similarity:.4f}"
        rows.append([content, str(similarity)])
    print_table(["Content", "Similarity"], rows)


def _handle_add(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload: dict[str, Any] = {
        "content": args.content,
        "memory_type": args.memory_type,
        "channel_id": config.channel,
    }
    if args.tags:
        payload["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()]

    data = client.put("/api/semantic-memory", payload)
    output(
        data, json_mode=config.json_output, human_fn=lambda d: print_success("Memory entry added.")
    )
