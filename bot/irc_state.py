import asyncio
from typing import TYPE_CHECKING, Any

from bot.irc_protocol import flatten_chat_text
from bot.logic import context
from bot.observability import observability
from bot.prompt_runtime import format_chat_reply
from bot.runtime_config import TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS, logger
from bot.status_runtime import build_status_line, normalize_channel_login


class IrcChannelStateMixin:
    channel_logins: list[str]
    joined_channels: set[str]
    primary_channel_login: str
    reader: asyncio.StreamReader | None
    _line_reader_running: bool
    _line_reader_task: asyncio.Task[Any] | None
    _pending_join_events: dict[str, asyncio.Event]
    _pending_part_events: dict[str, asyncio.Event]

    if TYPE_CHECKING:
        async def _send_raw(self, line: str) -> None: ...

    def build_status_line(self) -> str:
        return build_status_line(channel_logins=self.channel_logins)

    @property
    def channel_action_timeout_seconds(self) -> float:
        return max(0.1, float(TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS))

    def _prepare_reply_text(self, text: str) -> str:
        return flatten_chat_text(format_chat_reply(text))

    async def send_reply(self, text: str, channel_login: str | None = None) -> None:
        target_channel = normalize_channel_login(
            channel_login or self.primary_channel_login
        )
        if not target_channel:
            target_channel = self.primary_channel_login
        if target_channel not in self.joined_channels:
            target_channel = self.primary_channel_login

        safe_text = self._prepare_reply_text(text)
        if not safe_text:
            return
        await self._send_raw(f"PRIVMSG #{target_channel} :{safe_text}")

    async def _send_tracked_channel_reply(self, channel_login: str, text: str) -> None:
        target_channel = normalize_channel_login(channel_login)
        if not target_channel or target_channel not in self.joined_channels:
            return
        safe_text = self._prepare_reply_text(text)
        if not safe_text:
            return
        context.remember_bot_reply(safe_text)
        observability.record_reply(text=safe_text)
        await self._send_raw(f"PRIVMSG #{target_channel} :{safe_text}")

    def _mark_channel_joined(self, channel_login: str) -> bool:
        target_channel = normalize_channel_login(channel_login)
        if not target_channel:
            return False

        changed = False
        if target_channel not in self.joined_channels:
            self.joined_channels.add(target_channel)
            changed = True
        if target_channel not in self.channel_logins:
            self.channel_logins.append(target_channel)
            changed = True
        if (
            not self.primary_channel_login
            or self.primary_channel_login not in self.joined_channels
        ):
            self.primary_channel_login = self.channel_logins[0]
            changed = True
        return changed

    def _mark_channel_parted(self, channel_login: str) -> bool:
        target_channel = normalize_channel_login(channel_login)
        if not target_channel:
            return False

        changed = False
        if target_channel in self.joined_channels:
            self.joined_channels.remove(target_channel)
            changed = True
        filtered_channels = [
            channel for channel in self.channel_logins if channel != target_channel
        ]
        if len(filtered_channels) != len(self.channel_logins):
            self.channel_logins = filtered_channels
            changed = True
        if not self.channel_logins and self.joined_channels:
            self.channel_logins = sorted(self.joined_channels)
            changed = True
        if self.primary_channel_login == target_channel:
            self.primary_channel_login = self.channel_logins[0] if self.channel_logins else ""
            changed = True
        elif (
            self.primary_channel_login
            and self.primary_channel_login not in self.joined_channels
        ):
            self.primary_channel_login = self.channel_logins[0] if self.channel_logins else ""
            changed = True
        elif not self.primary_channel_login and self.channel_logins:
            self.primary_channel_login = self.channel_logins[0]
            changed = True
        return changed

    def _signal_pending_channel_action(
        self, pending_map: dict[str, asyncio.Event], channel_login: str
    ) -> None:
        event = pending_map.get(channel_login)
        if event is not None and not event.is_set():
            event.set()

    def _can_wait_for_channel_confirmation(self) -> bool:
        if self.reader is None or not self._line_reader_running:
            return False
        current_task = asyncio.current_task()
        if self._line_reader_task is not None and current_task is self._line_reader_task:
            return False
        return True

    async def _wait_for_channel_confirmation(
        self,
        *,
        channel_login: str,
        action: str,
        pending_map: dict[str, asyncio.Event],
    ) -> bool:
        event = pending_map.get(channel_login)
        if event is None:
            return False

        try:
            await asyncio.wait_for(event.wait(), timeout=self.channel_action_timeout_seconds)
            return True
        except TimeoutError:
            logger.warning(
                "Timeout aguardando confirmacao de %s no IRC para #%s.",
                action,
                channel_login,
            )
            observability.record_error(
                category="irc_channel_control",
                details=f"timeout aguardando {action} #{channel_login}",
            )
            return False
        finally:
            current_event = pending_map.get(channel_login)
            if current_event is event:
                pending_map.pop(channel_login, None)

    async def _join_channel(self, channel_login: str) -> bool:
        target_channel = normalize_channel_login(channel_login)
        if not target_channel:
            return False
        if target_channel in self.joined_channels:
            return False

        should_wait_confirmation = self._can_wait_for_channel_confirmation()
        if should_wait_confirmation and target_channel not in self._pending_join_events:
            self._pending_join_events[target_channel] = asyncio.Event()
        await self._send_raw(f"JOIN #{target_channel}")

        if should_wait_confirmation:
            return await self._wait_for_channel_confirmation(
                channel_login=target_channel,
                action="JOIN",
                pending_map=self._pending_join_events,
            )

        logger.info(
            "JOIN enviado para #%s sem espera de confirmacao imediata.",
            target_channel,
        )
        return True

    async def _part_channel(self, channel_login: str) -> bool:
        target_channel = normalize_channel_login(channel_login)
        if not target_channel:
            return False
        if target_channel not in self.joined_channels:
            return False
        if len(self.channel_logins) <= 1:
            return False

        should_wait_confirmation = self._can_wait_for_channel_confirmation()
        if should_wait_confirmation and target_channel not in self._pending_part_events:
            self._pending_part_events[target_channel] = asyncio.Event()
        await self._send_raw(f"PART #{target_channel}")

        if should_wait_confirmation:
            return await self._wait_for_channel_confirmation(
                channel_login=target_channel,
                action="PART",
                pending_map=self._pending_part_events,
            )

        logger.info(
            "PART enviado para #%s sem espera de confirmacao imediata.",
            target_channel,
        )
        return True

    async def admin_list_channels(self) -> list[str]:
        return list(self.channel_logins)

    async def admin_join_channel(self, channel_login: str) -> tuple[bool, str, list[str]]:
        target_channel = normalize_channel_login(channel_login)
        if not target_channel:
            return (
                False,
                "Invalid channel login. Use Twitch login format (no #).",
                list(self.channel_logins),
            )
        if target_channel in self.joined_channels:
            return (
                True,
                f"Already connected to #{target_channel}.",
                list(self.channel_logins),
            )
        if not self._can_wait_for_channel_confirmation():
            return (
                False,
                "IRC runtime unavailable for confirmed channel control. Try again shortly.",
                list(self.channel_logins),
            )
        joined = await self._join_channel(target_channel)
        if not joined:
            return (False, f"Failed to join #{target_channel}.", list(self.channel_logins))
        return (True, f"Joined #{target_channel}.", list(self.channel_logins))

    async def admin_part_channel(self, channel_login: str) -> tuple[bool, str, list[str]]:
        target_channel = normalize_channel_login(channel_login)
        if not target_channel:
            return (
                False,
                "Invalid channel login. Use Twitch login format (no #).",
                list(self.channel_logins),
            )
        if target_channel not in self.joined_channels:
            return (
                False,
                f"Channel not connected: #{target_channel}.",
                list(self.channel_logins),
            )
        if len(self.channel_logins) <= 1:
            return (
                False,
                "Cannot leave the last active channel. Join another one first.",
                list(self.channel_logins),
            )
        if not self._can_wait_for_channel_confirmation():
            return (
                False,
                "IRC runtime unavailable for confirmed channel control. Try again shortly.",
                list(self.channel_logins),
            )
        parted = await self._part_channel(target_channel)
        if not parted:
            return (False, f"Failed to leave #{target_channel}.", list(self.channel_logins))
        return (True, f"Left #{target_channel}.", list(self.channel_logins))
