import asyncio
from typing import Any

from bot.irc_connection import IrcConnectionMixin
from bot.irc_handlers import IrcLineHandlersMixin
from bot.irc_management import IrcChannelManagementMixin
from bot.irc_state import IrcChannelStateMixin
from bot.observability import observability
from bot.runtime_config import (
    OWNER_ID,
    TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS,
    TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS,
    logger,
)
from bot.status_runtime import normalize_channel_login
from bot.twitch_tokens import TwitchTokenManager, TwitchTokenManagerSettings


class IrcByteBot(
    IrcChannelManagementMixin,
    IrcChannelStateMixin,
    IrcLineHandlersMixin,
    IrcConnectionMixin,
):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        use_tls: bool,
        bot_login: str,
        channel_login: str | None = None,
        channel_logins: list[str] | None = None,
        user_token: str = "",
        token_manager: TwitchTokenManager | None = None,
    ) -> None:
        provided_channels = list(channel_logins or [])
        if channel_login:
            provided_channels.append(channel_login)

        resolved_channels: list[str] = []
        seen_channels: set[str] = set()
        for candidate in provided_channels:
            normalized = normalize_channel_login(candidate)
            if not normalized or normalized in seen_channels:
                continue
            seen_channels.add(normalized)
            resolved_channels.append(normalized)
        if not resolved_channels:
            raise RuntimeError("Defina ao menos 1 canal valido para o modo IRC.")

        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.bot_login = bot_login.lower()
        self.owner_id = OWNER_ID
        self.channel_logins = resolved_channels
        self.joined_channels = set(resolved_channels)
        self.primary_channel_login = resolved_channels[0]
        self.token_manager = token_manager or TwitchTokenManager(
            access_token=user_token,
            settings=TwitchTokenManagerSettings(
                validate_timeout_seconds=TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS,
                refresh_timeout_seconds=TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS,
            ),
            observability=observability,
            logger=logger,
        )
        self.reader: asyncio.StreamReader | None = None
        self.writer: Any = None
        self._line_reader_running = False
        self._line_reader_task: asyncio.Task[Any] | None = None
        self._pending_join_events: dict[str, asyncio.Event] = {}
        self._pending_part_events: dict[str, asyncio.Event] = {}
