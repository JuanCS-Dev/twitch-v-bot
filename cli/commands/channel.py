# SPDX-License-Identifier: MIT
"""bytecli channel — Channel management (context, config, notes, join, part, list)."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import output, print_header, print_kv, print_success, print_table


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("channel", help="Channel management")
    sub = parser.add_subparsers(dest="channel_cmd", metavar="<action>")
    parser.set_defaults(handler=_handle_context)

    # context
    p_ctx = sub.add_parser("context", help="Show full channel context")
    p_ctx.set_defaults(handler=_handle_context)

    # config
    p_cfg = sub.add_parser("config", help="Channel config (show or set)")
    p_cfg_sub = p_cfg.add_subparsers(dest="config_cmd", metavar="<action>")
    p_cfg.set_defaults(handler=_handle_config_show)

    p_set = p_cfg_sub.add_parser("set", help="Update a channel config key")
    p_set.add_argument("key", help="Config key")
    p_set.add_argument("value", help="New value")
    p_set.set_defaults(handler=_handle_config_set)

    # notes
    p_notes = sub.add_parser("notes", help="Agent notes (show or set)")
    p_notes_sub = p_notes.add_subparsers(dest="notes_cmd", metavar="<action>")
    p_notes.set_defaults(handler=_handle_notes_show)

    p_notes_set = p_notes_sub.add_parser("set", help="Update agent notes")
    p_notes_set.add_argument("notes", help="New notes content")
    p_notes_set.set_defaults(handler=_handle_notes_set)

    # join
    p_join = sub.add_parser("join", help="Join an IRC channel")
    p_join.add_argument("channel_login", help="Twitch channel login to join")
    p_join.set_defaults(handler=_handle_join)

    # part
    p_part = sub.add_parser("part", help="Leave an IRC channel")
    p_part.add_argument("channel_login", help="Twitch channel login to leave")
    p_part.set_defaults(handler=_handle_part)

    # list
    p_list = sub.add_parser("list", help="List connected channels")
    p_list.set_defaults(handler=_handle_channel_list)


def _handle_context(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params = {"channel": config.channel} if config.channel != "default" else {}
    data = client.get("/api/channel-context", params)
    output(data, json_mode=config.json_output, human_fn=_human_context)


def _human_context(data: dict[str, Any]) -> None:
    ch = data.get("channel", data)
    print_header(f"Channel: {ch.get('channel_id', '?')}")
    runtime = ch.get("runtime", {})
    print_kv(
        {
            "Loaded": ch.get("runtime_loaded", False),
            "Game": runtime.get("game", "—"),
            "Vibe": runtime.get("vibe", "—"),
            "Persona": runtime.get("persona_name", "—"),
            "Tone": runtime.get("tone", "—"),
            "Agent Paused": runtime.get("agent_paused", False),
            "Temperature": runtime.get("temperature", "—"),
            "Top-P": runtime.get("top_p", "—"),
        }
    )

    history = ch.get("persisted_recent_history", [])
    if history:
        print_header(f"Recent Chat ({len(history)} messages)")
        rows = []
        for msg in history[-10:]:
            author = msg.get("author", msg.get("user", "—"))
            text = str(msg.get("text", msg.get("content", "—")))[:60]
            rows.append([str(author), text])
        print_table(["Author", "Message"], rows)


def _handle_config_show(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params = {"channel": config.channel} if config.channel != "default" else {}
    data = client.get("/api/channel-config", params)
    output(data, json_mode=config.json_output, human_fn=_human_config)


def _human_config(data: dict[str, Any]) -> None:
    ch = data.get("channel", data)
    print_header("Channel Configuration")
    print_kv(ch)


def _handle_config_set(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    # Type coercion
    raw = args.value
    value: Any
    if raw.lower() in ("true", "false"):
        value = raw.lower() == "true"
    else:
        try:
            value = float(raw)
            if value == int(value):
                value = int(value)
        except ValueError:
            value = raw

    payload = {args.key: value, "channel_id": config.channel}
    data = client.put("/api/channel-config", payload)
    output(
        data,
        json_mode=config.json_output,
        human_fn=lambda d: print_success(f"Channel config '{args.key}' set to '{value}'."),
    )


def _handle_notes_show(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params = {"channel": config.channel} if config.channel != "default" else {}
    data = client.get("/api/agent-notes", params)
    output(data, json_mode=config.json_output, human_fn=_human_notes)


def _human_notes(data: dict[str, Any]) -> None:
    note = data.get("note", {})
    print_header("Agent Notes")
    content = note.get("notes", note.get("content", "")) if isinstance(note, dict) else str(note)
    if content:
        print(content)
    else:
        print("  (no notes)")


def _handle_notes_set(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload = {"notes": args.notes, "channel_id": config.channel}
    data = client.put("/api/agent-notes", payload)
    output(
        data, json_mode=config.json_output, human_fn=lambda d: print_success("Agent notes updated.")
    )


def _handle_join(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload = {"action": "join", "channel_login": args.channel_login}
    data = client.post("/api/channel-control", payload)
    output(
        data,
        json_mode=config.json_output,
        human_fn=lambda d: print_success(f"Joined #{args.channel_login}."),
    )


def _handle_part(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload = {"action": "part", "channel_login": args.channel_login}
    data = client.post("/api/channel-control", payload)
    output(
        data,
        json_mode=config.json_output,
        human_fn=lambda d: print_success(f"Left #{args.channel_login}."),
    )


def _handle_channel_list(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload = {"action": "list"}
    data = client.post("/api/channel-control", payload)
    output(data, json_mode=config.json_output, human_fn=_human_channel_list)


def _human_channel_list(data: dict[str, Any]) -> None:
    channels = data.get("channels", [])
    print_header(f"Connected Channels ({len(channels)})")
    if not channels:
        return
    rows = [[str(ch)] for ch in channels]
    print_table(["Channel"], rows)
