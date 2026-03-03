# SPDX-License-Identifier: MIT
"""Byte Agent CLI — Main dispatcher.

Registers all command groups and dispatches to their handlers.
Global flags (--json, --url, --token, --channel) are parsed here
and injected into every command via the resolved CLIConfig.
"""

from __future__ import annotations

import argparse
import sys
from typing import Final

from cli import __version__
from cli.client import (
    AuthenticationError,
    ByteClient,
    CLIClientError,
    ConnectionError_,
    NotFoundError,
    ServerError,
)
from cli.config import CLIConfig, load_config
from cli.formatters import print_error

PROG_NAME: Final[str] = "bytecli"
DESCRIPTION: Final[str] = """\
Byte Agent CLI — Full control over the Byte Twitch Agent.

All commands communicate with the agent's Dashboard HTTP API
(default: http://localhost:7860). Authentication is via admin token.
"""

EPILOG: Final[str] = """\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  COMMAND CHEAT-SHEET (43 commands)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  LIFECYCLE & STATUS
    status                          Agent health, mode, key metrics
    agent suspend [--reason R]      Suspend the agent
    agent resume  [--reason R]      Resume the agent
    agent tick    [--force]         Force an autonomy tick
    agent config                    Show control plane config
    agent config set <key> <val>    Update a config key

  OBSERVABILITY
    observe                         Telemetry snapshot (counters, cost)
    observe sentiment               Chat sentiment scores + vibe
    observe history [--limit N]     Observability snapshot timeline

  GOALS
    goals list                      List all goals with status
    goals show  <goal_id>           Detailed view of a single goal
    goals add   --id X --name Y ... Create a new goal
    goals enable  <goal_id>         Enable a goal
    goals disable <goal_id>         Disable a goal
    goals remove  <goal_id>         Remove a goal permanently

  ACTION QUEUE
    actions list    [--status S]    List queued actions
    actions pending                 Shortcut: pending actions only
    actions approve <id> [--note N] Approve an action
    actions reject  <id> [--note N] Reject an action

  CHANNEL
    channel context                 Full channel context (game, vibe, etc.)
    channel config                  Show channel configuration
    channel config set <key> <val>  Update channel config key
    channel notes                   Show agent notes
    channel notes set <text>        Update agent notes
    channel join  <login>           Join an IRC channel
    channel part  <login>           Leave an IRC channel
    channel list                    List connected channels

  MEMORY
    memory list   [--limit N]       List semantic memory entries
    memory search <query>           Search memory by text query
    memory add    <text> [--tags T] Add a memory entry

  PERSONA
    persona show                    Show persona profile
    persona update [--name/--tone]  Update persona profile

  CLIPS & VISION
    clips jobs                      List clip pipeline jobs
    clips vision                    Vision pipeline status

  PLAYBOOKS
    playbooks list                  List ops playbooks with status
    playbooks trigger <id> [--force] Trigger a playbook manually

  WEBHOOKS
    webhooks list                   List registered webhooks
    webhooks add  <url> [--events]  Register a new webhook
    webhooks test <id>              Send a test event

  REPORTS
    report show                     Show latest post-stream report
    report generate                 Generate a new report

  CHAT
    chat <message>                  Send message through AI pipeline

  REVENUE / CONVERSIONS
    conversions list [--limit N]    List revenue conversions
    conversions add --event E --value V   Register a conversion
    revenue list                    Alias for conversions list
    revenue add                     Alias for conversions add

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CONFIGURATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Config is resolved in priority order (highest wins):
    1. CLI flags:   --url, --token, --hf-token, --channel
    2. Env vars:    BYTE_API_URL, BYTE_ADMIN_TOKEN, HF_TOKEN
    3. Config file: ~/.byterc (INI format)
    4. Defaults:    http://localhost:7860, no token, channel=default

  ~/.byterc example:
    [default]
    url = http://localhost:7860
    token = my-admin-token
    hf_token = hf_123xyz

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  USAGE EXAMPLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # Check if agent is online
  bytecli status

  # Send a chat message through the AI pipeline
  bytecli chat "faz um ASCII do Goku"

  # List goals in JSON format
  bytecli --json goals list

  # Approve an action with a note
  bytecli actions approve abc123 --note "Looks good"

  # Suspend agent on a specific channel
  bytecli --channel xqcow agent suspend --reason "maintenance"

  # Search semantic memory
  bytecli memory search "favorite game"

  # Use a remote agent
  bytecli --url http://agent.example.com:7860 --token sk-xxx status

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  EXIT CODES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  0   Success
  1   No command specified / unknown command
  2   Authentication error (invalid token)
  3   Connection error (agent unreachable)
  4   Not found (endpoint does not exist)
  5   Server error (agent returned 5xx)
  6   Other API error
  130 Interrupted (Ctrl+C)
"""


# ---------------------------------------------------------------------------
# Command Registration
# ---------------------------------------------------------------------------


def _register_all_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register every command group."""
    # Imports are deferred to avoid circular deps and keep startup fast
    from cli.commands.actions import register as reg_actions
    from cli.commands.channel import register as reg_channel
    from cli.commands.chat import register as reg_chat
    from cli.commands.clips import register as reg_clips
    from cli.commands.control import register as reg_control
    from cli.commands.conversions import register as reg_conversions
    from cli.commands.goals import register as reg_goals
    from cli.commands.memory import register as reg_memory
    from cli.commands.observe import register as reg_observe
    from cli.commands.persona import register as reg_persona
    from cli.commands.playbooks import register as reg_playbooks
    from cli.commands.report import register as reg_report
    from cli.commands.status import register as reg_status
    from cli.commands.webhooks import register as reg_webhooks

    reg_status(subparsers)
    reg_control(subparsers)
    reg_observe(subparsers)
    reg_goals(subparsers)
    reg_actions(subparsers)
    reg_channel(subparsers)
    reg_memory(subparsers)
    reg_persona(subparsers)
    reg_clips(subparsers)
    reg_playbooks(subparsers)
    reg_webhooks(subparsers)
    reg_report(subparsers)
    reg_chat(subparsers)
    reg_conversions(subparsers)


# ---------------------------------------------------------------------------
# Parser Builder
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog=PROG_NAME,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Output raw JSON instead of human-readable tables. Useful for piping to jq or other tools.",
    )
    parser.add_argument(
        "--url",
        dest="api_url",
        default=None,
        metavar="URL",
        help="Override the agent API URL. Default: http://localhost:7860. Can also be set via BYTE_API_URL env var or ~/.byterc.",
    )
    parser.add_argument(
        "--token",
        dest="api_token",
        default=None,
        metavar="TOKEN",
        help="Override the admin authentication token. Can also be set via BYTE_ADMIN_TOKEN or BYTE_DASHBOARD_ADMIN_TOKEN env var or ~/.byterc.",
    )
    parser.add_argument(
        "--hf-token",
        dest="hf_token",
        default=None,
        metavar="HF_TOKEN",
        help="Hugging Face Bearer token for accessing Private Spaces. Can also be set via HF_TOKEN env var or ~/.byterc.",
    )
    parser.add_argument(
        "--channel",
        dest="channel",
        default=None,
        metavar="CHANNEL",
        help="Target channel name for multi-channel operations. Default: 'default'. Most commands accept this to scope data to a specific Twitch channel.",
    )

    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        metavar="<command>",
        description="Use 'bytecli <command> --help' for detailed help on each command.",
    )

    _register_all_commands(subparsers)

    return parser


# ---------------------------------------------------------------------------
# Execution Core
# ---------------------------------------------------------------------------


def _resolve_config(args: argparse.Namespace) -> CLIConfig:
    """Build CLIConfig from parsed CLI args + file + env."""
    cfg = load_config(
        cli_url=args.api_url,
        cli_token=args.api_token,
        cli_channel=args.channel,
        cli_json=args.json_output,
    )
    # Apply hf_token if present in args
    hf_tok = getattr(args, "hf_token", None)
    if hf_tok is not None:
        cfg = cfg.with_overrides(hf_token=hf_tok)
    return cfg


def _run(args: argparse.Namespace, config: CLIConfig) -> int:
    """Execute the dispatched command handler. Returns exit code."""
    handler = getattr(args, "handler", None)
    if handler is None:
        return 1  # no command selected

    client = ByteClient.from_config(config)

    try:
        handler(args, client, config)
        return 0
    except AuthenticationError as exc:
        print_error(f"Authentication failed: {exc}")
        print_error("Check your --token or BYTE_ADMIN_TOKEN environment variable.")
        return 2
    except ConnectionError_ as exc:
        print_error(f"Cannot reach agent: {exc}")
        print_error(f"Is the agent running at {config.url}?")
        return 3
    except NotFoundError as exc:
        print_error(f"Endpoint not found: {exc}")
        return 4
    except ServerError as exc:
        print_error(f"Server error: {exc}")
        return 5
    except CLIClientError as exc:
        print_error(f"API error: {exc}")
        return 6
    except KeyboardInterrupt:
        print_error("Interrupted.")
        return 130


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    config = _resolve_config(args)
    exit_code = _run(args, config)
    sys.exit(exit_code)
