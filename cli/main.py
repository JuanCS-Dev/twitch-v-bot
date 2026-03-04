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

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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

DESCRIPTION: Final[str] = """
[bold magenta]Byte Agent CLI[/bold magenta] [bold cyan]v{version}[/bold cyan] 🤖
[italic white]Controle total sobre o seu Agente Byte no Twitch.[/italic white]
"""

# ---------------------------------------------------------------------------
# Rich Help Formatter
# ---------------------------------------------------------------------------


def print_rich_help(parser: argparse.ArgumentParser) -> None:
    """Print a beautiful help screen using Rich."""
    console = Console()

    # Header / Description
    console.print(
        Panel(DESCRIPTION.format(version=__version__), border_style="magenta", expand=False)
    )

    # Commands Section
    console.print("\n[bold yellow]🚀 COMANDOS PRINCIPAIS[/bold yellow]")

    # Categorized Command Table
    def create_cmd_table(title: str, color: str) -> Table:
        table = Table(
            title=f"[bold {color}]{title}[/bold {color}]",
            show_header=True,
            header_style=f"bold {color}",
            box=None,
            padding=(0, 2),
        )
        table.add_column("Comando", style="cyan", width=25)
        table.add_column("Descrição", style="white")
        return table

    # Lifecycle & Status
    t_life = create_cmd_table("🛸 CICLO DE VIDA & STATUS", "green")
    t_life.add_row("status", "Saúde do agente, modo e métricas")
    t_life.add_row("agent suspend", "Suspende o agente (ex: --reason maintenance)")
    t_life.add_row("agent resume", "Retoma as atividades")
    t_life.add_row("agent tick", "Força um ciclo de autonomia")
    t_life.add_row("agent config", "Ver/Alterar configurações do Control Plane")

    # Observability & Goals
    t_obs = create_cmd_table("📊 MONITORAMENTO & METAS", "blue")
    t_obs.add_row("observe", "Snapshot de telemetria e custos")
    t_obs.add_row("observe sentiment", "Vibe e sentimentos do chat")
    t_obs.add_row("goals list", "Listar todas as metas ativas")
    t_obs.add_row("actions list", "Ver fila de ações pendentes")

    # Channel & Memory
    t_chan = create_cmd_table("🧠 CANAL & MEMÓRIA", "magenta")
    t_chan.add_row("channel context", "Contexto atual do canal (jogo, vibe)")
    t_chan.add_row("channel notes", "Notas persistentes do agente")
    t_chan.add_row("memory search", "Busca na memória semântica")
    t_chan.add_row("persona show", "Perfil e tom de voz da persona")

    # Others (Clips, Playbooks, Webhooks)
    t_others = create_cmd_table("🛠️ FERRAMENTAS & OPS", "yellow")
    t_others.add_row("clips jobs", "Status do pipeline de clips")
    t_others.add_row("playbooks list", "Lista playbooks de operação")
    t_others.add_row("webhooks list", "Gerenciar webhooks de saída")
    t_others.add_row("report generate", "Gerar relatório pós-stream")

    # Render Tables in Columns
    console.print(Columns([t_life, t_obs, t_chan, t_others], equal=True, expand=True))

    # Global Options Section
    console.print("\n[bold white]⚙️ OPÇÕES GLOBAIS[/bold white]")
    opt_table = Table(box=None, show_header=False, padding=(0, 2))
    opt_table.add_column("Flag", style="bold cyan")
    opt_table.add_column("Descrição", style="dim")
    opt_table.add_row("--json", "Saída em JSON bruto para automação")
    opt_table.add_row("--url URL", "Sobrescreve a URL da API (ou BYTE_API_URL)")
    opt_table.add_row("--token TK", "Token de admin (ou BYTE_ADMIN_TOKEN)")
    opt_table.add_row("--channel CH", "Nome do canal alvo (default: 'default')")
    console.print(opt_table)

    # Usage Example
    console.print(
        Panel(
            "[bold cyan]Exemplo rápido:[/bold cyan]\n"
            "[white]python -m cli [bold green]status[/bold green][/white]\n"
            '[white]python -m cli [bold magenta]chat[/bold magenta] [italic]"Oi Byte, faz um ASCII do Goku"[/italic][/white]',
            title="[bold yellow]💡 DICA[/bold yellow]",
            border_style="yellow",
            expand=False,
        )
    )

    console.print(
        f"\n[dim white]Use 'bytecli <comando> --help' para detalhes. [bold magenta]Byte Agent v{__version__}[/bold magenta][/dim white]"
    )


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

    # Override standard help to use our colorful Rich version
    parser.print_help = lambda file=None: print_rich_help(parser)

    args = parser.parse_args(argv)

    if args.command is None:
        print_rich_help(parser)
        sys.exit(0)

    config = _resolve_config(args)
    exit_code = _run(args, config)
    sys.exit(exit_code)
