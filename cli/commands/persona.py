# SPDX-License-Identifier: MIT
"""bytecli persona — Persona profile management (show, update)."""

from __future__ import annotations

import argparse
from typing import Any

from cli.client import ByteClient
from cli.config import CLIConfig
from cli.formatters import output, print_header, print_kv, print_success


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "persona",
        help="Persona profile management (show, update)",
        description=(
            "Manage the agent's persona profile. The persona determines how the agent "
            "speaks and behaves. You can update the base identity, tonality engine, "
            "behavioral constraints, and model routing."
        ),
        epilog=(
            "Examples:\n"
            "  bytecli persona show\n"
            "  bytecli persona update --name 'Byte' --tone 'helpful, sarcastic'\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="persona_cmd", metavar="<action>")
    parser.set_defaults(handler=_handle_show)

    # show
    p_show = sub.add_parser("show", help="Show the current persona configuration")
    p_show.set_defaults(handler=_handle_show)

    # update
    p_update = sub.add_parser(
        "update",
        help="Update persona profile attributes",
        description="Update specific fields of the persona profile. Leave fields empty to keep current values. PUT /api/persona-profile.",
    )
    p_update.add_argument("--name", default=None, help="Base persona name (e.g. 'Byte')")
    p_update.add_argument(
        "--tone", default=None, help="Tonality/voice style (e.g. 'sarcastic, helpful')"
    )
    p_update.add_argument("--lore", default=None, help="Character lore/backstory")
    p_update.add_argument(
        "--constraints", default=None, help="Behavioral constraints (valid JSON string)"
    )
    p_update.add_argument(
        "--routing", default=None, help="Model routing config (valid JSON string)"
    )
    p_update.set_defaults(handler=_handle_update)


def _handle_show(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    params = {"channel": config.channel} if config.channel != "default" else {}
    data = client.get("/api/persona-profile", params)
    output(data, json_mode=config.json_output, human_fn=_human_show)


def _human_show(data: dict[str, Any]) -> None:
    profile = data.get("profile", data)
    print_header("Persona Profile")
    if not profile or not profile.get("has_profile", True):
        print("  (no profile configured)")
        return

    display: dict[str, Any] = {}
    for key in ("base_identity", "tonality_engine", "behavioral_constraints", "model_routing"):
        val = profile.get(key)
        if val is not None:
            display[key] = val
    if not display:
        display = profile
    print_kv(display)


def _handle_update(args: argparse.Namespace, client: ByteClient, config: CLIConfig) -> None:
    import json as json_mod

    payload: dict[str, Any] = {"channel_id": config.channel}

    if args.name is not None:
        payload["base_identity"] = args.name
    if args.tone is not None:
        payload["tonality_engine"] = args.tone
    if args.lore is not None:
        # Lore goes through channel identity, not persona profile directly
        # but the PUT /api/persona-profile endpoint handles it
        payload["base_identity"] = payload.get("base_identity", "")
    if args.constraints is not None:
        try:
            payload["behavioral_constraints"] = json_mod.loads(args.constraints)
        except json_mod.JSONDecodeError:
            payload["behavioral_constraints"] = args.constraints
    if args.routing is not None:
        try:
            payload["model_routing"] = json_mod.loads(args.routing)
        except json_mod.JSONDecodeError:
            payload["model_routing"] = args.routing

    data = client.put("/api/persona-profile", payload)
    output(
        data,
        json_mode=config.json_output,
        human_fn=lambda d: print_success("Persona profile updated."),
    )
