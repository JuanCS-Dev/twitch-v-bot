# SPDX-License-Identifier: MIT
"""Output formatters for the Byte Agent CLI.

Provides human-readable (tables, key-value, colored) and machine-readable (JSON)
output modes. All output goes through these formatters so the --json flag works
consistently across every command.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timezone
from typing import Any, Final, TextIO

# ---------------------------------------------------------------------------
# ANSI Color Constants
# ---------------------------------------------------------------------------

_SUPPORTS_COLOR: Final[bool] = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_RESET: Final[str] = "\033[0m" if _SUPPORTS_COLOR else ""
_BOLD: Final[str] = "\033[1m" if _SUPPORTS_COLOR else ""
_DIM: Final[str] = "\033[2m" if _SUPPORTS_COLOR else ""
_GREEN: Final[str] = "\033[32m" if _SUPPORTS_COLOR else ""
_RED: Final[str] = "\033[31m" if _SUPPORTS_COLOR else ""
_YELLOW: Final[str] = "\033[33m" if _SUPPORTS_COLOR else ""
_CYAN: Final[str] = "\033[36m" if _SUPPORTS_COLOR else ""
_MAGENTA: Final[str] = "\033[35m" if _SUPPORTS_COLOR else ""


# ---------------------------------------------------------------------------
# Primitive Formatters
# ---------------------------------------------------------------------------


def print_success(message: str, *, file: TextIO = sys.stdout) -> None:
    """Print a success message in green."""
    file.write(f"{_GREEN}✓{_RESET} {message}\n")
    file.flush()


def print_error(message: str, *, file: TextIO = sys.stderr) -> None:
    """Print an error message in red to stderr."""
    file.write(f"{_RED}✗{_RESET} {message}\n")
    file.flush()


def print_warning(message: str, *, file: TextIO = sys.stderr) -> None:
    """Print a warning message in yellow."""
    file.write(f"{_YELLOW}⚠{_RESET} {message}\n")
    file.flush()


def print_info(message: str, *, file: TextIO = sys.stdout) -> None:
    """Print an informational message in cyan."""
    file.write(f"{_CYAN}ℹ{_RESET} {message}\n")
    file.flush()


def print_header(title: str, *, file: TextIO = sys.stdout) -> None:
    """Print a bold section header."""
    file.write(f"\n{_BOLD}{title}{_RESET}\n")
    file.write(f"{_DIM}{'─' * min(len(title) + 4, 60)}{_RESET}\n")
    file.flush()


# ---------------------------------------------------------------------------
# JSON Output
# ---------------------------------------------------------------------------


def print_json(data: Any, *, file: TextIO = sys.stdout) -> None:
    """Pretty-print data as indented JSON."""
    output = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    file.write(output)
    file.write("\n")
    file.flush()


# ---------------------------------------------------------------------------
# Table Output
# ---------------------------------------------------------------------------


def print_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    file: TextIO = sys.stdout,
    max_col_width: int = 50,
) -> None:
    """Print an ASCII table with auto-sized columns.

    Columns are sized to fit the widest value (capped at max_col_width).
    """
    if not headers:
        return

    # Compute column widths
    col_count = len(headers)
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row[:col_count]):
            widths[i] = max(widths[i], len(str(cell)))
    widths = [min(w, max_col_width) for w in widths]

    def _truncate(text: str, width: int) -> str:
        text = str(text)
        if len(text) <= width:
            return text.ljust(width)
        return text[: width - 1] + "…"

    # Header row
    header_line = " │ ".join(_truncate(h, widths[i]) for i, h in enumerate(headers))
    separator = "─┼─".join("─" * w for w in widths)
    file.write(f" {_BOLD}{header_line}{_RESET}\n")
    file.write(f" {_DIM}{separator}{_RESET}\n")

    # Data rows
    if not rows:
        file.write(f" {_DIM}(empty){_RESET}\n")
    else:
        for row in rows:
            padded = [
                _truncate(row[i] if i < len(row) else "", widths[i]) for i in range(col_count)
            ]
            file.write(f" {' │ '.join(padded)}\n")

    file.flush()


# ---------------------------------------------------------------------------
# Key-Value Output
# ---------------------------------------------------------------------------


def print_kv(
    data: dict[str, Any],
    *,
    file: TextIO = sys.stdout,
    label_width: int = 0,
) -> None:
    """Print key-value pairs aligned vertically.

    If label_width is 0, it auto-sizes to the longest key.
    """
    if not data:
        return

    width = label_width or max(len(str(k)) for k in data)
    for key, value in data.items():
        label = f"{_CYAN}{str(key).ljust(width)}{_RESET}"
        formatted_value = _format_value(value)
        file.write(f"  {label}  {formatted_value}\n")
    file.flush()


def _format_value(value: Any) -> str:
    """Format a single value for display with semantic coloring."""
    if value is None:
        return f"{_DIM}—{_RESET}"
    if isinstance(value, bool):
        return f"{_GREEN}yes{_RESET}" if value else f"{_RED}no{_RESET}"
    if isinstance(value, list | tuple):
        if not value:
            return f"{_DIM}(none){_RESET}"
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        if not value:
            return f"{_DIM}{{}}{_RESET}"
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


# ---------------------------------------------------------------------------
# Timestamp Formatter
# ---------------------------------------------------------------------------


def format_timestamp(iso_or_float: str | float | None) -> str:
    """Convert an ISO timestamp or Unix float into a human-readable string.

    Returns "—" for None/empty values.
    """
    if iso_or_float is None:
        return "—"

    if isinstance(iso_or_float, int | float):
        if iso_or_float <= 0:
            return "—"
        try:
            dt = datetime.fromtimestamp(iso_or_float, tz=UTC)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except (OSError, ValueError, OverflowError):
            return str(iso_or_float)

    text = str(iso_or_float).strip()
    if not text:
        return "—"

    # Try to parse ISO format
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S+00:00", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt).replace(tzinfo=UTC)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except ValueError:
            continue

    return text


# ---------------------------------------------------------------------------
# Dispatcher Helper
# ---------------------------------------------------------------------------


def output(
    data: Any,
    *,
    json_mode: bool = False,
    human_fn: Any = None,
) -> None:
    """Universal output dispatcher.

    In JSON mode: prints raw JSON.
    In human mode: calls the provided human_fn callback, or falls back to print_json.
    """
    if json_mode:
        print_json(data)
    elif callable(human_fn):
        human_fn(data)
    else:
        print_json(data)
