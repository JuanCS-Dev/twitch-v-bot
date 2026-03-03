# SPDX-License-Identifier: MIT
"""bytecli chat — Send a message through the agent to Twitch chat."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import output, print_header, print_success


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "chat",
        help="Send a message through the agent (processed by AI pipeline)",
        description=(
            "Sends a natural language prompt directly into the agent's cognitive pipeline. "
            "Unlike raw IRC messages, this triggers the full NLP, sentiment, and autonomy "
            "engines as if the streamer or a privileged user had commanded it."
        ),
        epilog=(
            "Examples:\n"
            '  bytecli chat "faz um ASCII do Goku"\n'
            '  bytecli chat "qual é o resumo da live até agora?"\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("message", help="Message text to send")
    parser.set_defaults(handler=_handle)


def _handle(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    payload: dict[str, Any] = {
        "text": args.message,
    }
    if config.channel != "default":
        payload["channel_id"] = config.channel

    data = client.post("/api/chat/send", payload)
    output(data, json_mode=config.json_output, human_fn=_human_chat)


def _human_chat(data: dict[str, Any]) -> None:
    replies = data.get("replies", [])
    text = data.get("text", "")

    print_success(f"Message sent: {text}")

    if replies:
        print_header("Agent Replies")
        for i, reply in enumerate(replies, 1):
            if isinstance(reply, str):
                print(f"  {i}. {reply}")
            elif isinstance(reply, dict):
                print(f"  {i}. {reply.get('text', reply)}")
