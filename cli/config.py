# SPDX-License-Identifier: MIT
"""Configuration loader for the Byte Agent CLI.

Resolution order (highest priority first):
1. CLI flags (--url, --token)
2. Environment variables (BYTE_API_URL, BYTE_ADMIN_TOKEN)
3. Config file (~/.byterc)
4. Defaults (http://localhost:7860, empty token)
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

DEFAULT_API_URL: Final[str] = "http://localhost:7860"
DEFAULT_CONFIG_PATH: Final[Path] = Path.home() / ".byterc"
DEFAULT_PROFILE: Final[str] = "default"

_ENV_API_URL: Final[str] = "BYTE_API_URL"
_ENV_ADMIN_TOKEN: Final[str] = "BYTE_ADMIN_TOKEN"
# Fallback: read from the same env var the bot uses
_ENV_DASHBOARD_TOKEN: Final[str] = "BYTE_DASHBOARD_ADMIN_TOKEN"
_ENV_HF_TOKEN: Final[str] = "HF_TOKEN"


@dataclass(frozen=True, slots=True)
class CLIConfig:
    """Immutable configuration for a CLI session."""

    url: str = DEFAULT_API_URL
    token: str = ""
    hf_token: str = ""
    channel: str = "default"
    json_output: bool = False

    def with_overrides(
        self,
        *,
        url: str | None = None,
        token: str | None = None,
        hf_token: str | None = None,
        channel: str | None = None,
        json_output: bool | None = None,
    ) -> CLIConfig:
        """Return a new config with selective overrides (non-None values win)."""
        return CLIConfig(
            url=url if url is not None else self.url,
            token=token if token is not None else self.token,
            hf_token=hf_token if hf_token is not None else self.hf_token,
            channel=channel if channel is not None else self.channel,
            json_output=json_output if json_output is not None else self.json_output,
        )


def _read_config_file(
    path: Path = DEFAULT_CONFIG_PATH,
    profile: str = DEFAULT_PROFILE,
) -> dict[str, str]:
    """Parse an INI-style config file and return the profile section as a dict.

    Returns an empty dict if the file doesn't exist or the profile is missing.
    """
    if not path.is_file():
        return {}

    parser = configparser.ConfigParser()
    try:
        parser.read(str(path), encoding="utf-8")
    except configparser.Error:
        return {}

    if not parser.has_section(profile):
        return {}

    return dict(parser.items(profile))


def _read_env() -> dict[str, str]:
    """Read CLI-relevant environment variables."""
    result: dict[str, str] = {}

    url = os.environ.get(_ENV_API_URL, "").strip()
    if url:
        result["url"] = url

    token = os.environ.get(_ENV_ADMIN_TOKEN, "").strip()
    if not token:
        token = os.environ.get(_ENV_DASHBOARD_TOKEN, "").strip()
    if token:
        result["token"] = token

    hf_token = os.environ.get(_ENV_HF_TOKEN, "").strip()
    if hf_token:
        result["hf_token"] = hf_token

    return result


def load_config(
    *,
    cli_url: str | None = None,
    cli_token: str | None = None,
    cli_channel: str | None = None,
    cli_json: bool = False,
    config_path: Path = DEFAULT_CONFIG_PATH,
    profile: str = DEFAULT_PROFILE,
) -> CLIConfig:
    """Build a CLIConfig by merging file → env → CLI flags (ascending priority)."""
    file_values = _read_config_file(config_path, profile)
    env_values = _read_env()

    # Start from defaults, layer file, then env, then CLI flags
    url = file_values.get("url", DEFAULT_API_URL)
    url = env_values.get("url", url)
    if cli_url:
        url = cli_url

    token = file_values.get("token", "")
    token = env_values.get("token", token)
    if cli_token:
        token = cli_token

    hf_token = file_values.get("hf_token", "")
    hf_token = env_values.get("hf_token", hf_token)
    # cli_hf_token logic added in main.py will be set via with_overrides if needed,
    # but let's just add it to config.py load_config signature to be clean:

    channel = file_values.get("channel", "default")
    if cli_channel:
        channel = cli_channel

    # Normalize URL: strip trailing slash
    url = url.rstrip("/")

    return CLIConfig(
        url=url,
        token=token,
        hf_token=hf_token,
        channel=channel.strip().lower() or "default",
        json_output=cli_json,
    )
