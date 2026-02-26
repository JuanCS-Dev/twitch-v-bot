import asyncio
from typing import TYPE_CHECKING, Any

from bot import byte_semantics
from bot.irc_protocol import (
    IRC_JOIN_PATTERN,
    IRC_NOTICE_PATTERN,
    IRC_PART_PATTERN,
    IRC_PRIVMSG_PATTERN,
    IrcAuthor,
    IrcMessageAdapter,
    is_irc_notice_delivery_block,
    parse_irc_tags,
)
from bot.logic import OBSERVABILITY_TYPES, context_manager
from bot.observability import observability
from bot.prompt_runtime import handle_byte_prompt_text
from bot.runtime_config import ENABLE_LIVE_CONTEXT_LEARNING, logger
from bot.scene_runtime import auto_update_scene_from_message
from bot.sentiment_engine import sentiment_engine
from bot.status_runtime import normalize_channel_login
from bot.twitch_tokens import TwitchAuthError

parse_byte_prompt = byte_semantics.parse_byte_prompt


class IrcLineHandlersMixin:
    bot_login: str
    joined_channels: set[str]

    if TYPE_CHECKING:
        _pending_join_events: dict[str, asyncio.Event]
        _pending_part_events: dict[str, asyncio.Event]
        token_manager: Any

        def _mark_channel_joined(self, channel_login: str) -> bool: ...
        def _mark_channel_parted(self, channel_login: str) -> bool: ...
        def _signal_pending_channel_action(
            self, pending_map: dict[str, asyncio.Event], channel_login: str
        ) -> None: ...
        async def _handle_channel_management_prompt(
            self, prompt: str, author: Any, source_channel: str
        ) -> bool: ...
        async def send_reply(self, text: str, channel_login: str | None = None) -> None: ...
        def build_status_line(self) -> str: ...

    async def _handle_membership_event(self, line: str) -> None:
        join_match = IRC_JOIN_PATTERN.match(line)
        if join_match:
            author_login = (join_match.group("author") or "").strip().lower()
            target_channel = normalize_channel_login(join_match.group("channel") or "")
            if author_login == self.bot_login and target_channel:
                changed = self._mark_channel_joined(target_channel)
                self._signal_pending_channel_action(self._pending_join_events, target_channel)
                if changed:
                    logger.info("Byte entrou no canal IRC #%s", target_channel)
            return

        part_match = IRC_PART_PATTERN.match(line)
        if not part_match:
            return
        author_login = (part_match.group("author") or "").strip().lower()
        target_channel = normalize_channel_login(part_match.group("channel") or "")
        if author_login == self.bot_login and target_channel:
            changed = self._mark_channel_parted(target_channel)
            self._signal_pending_channel_action(self._pending_part_events, target_channel)
            if changed:
                logger.info("Byte saiu do canal IRC #%s", target_channel)

    async def _handle_notice_line(self, line: str) -> None:
        notice_match = IRC_NOTICE_PATTERN.match(line)
        if not notice_match:
            return

        tags = parse_irc_tags(notice_match.group("tags") or "")
        msg_id = (tags.get("msg-id") or "").strip().lower()
        target = (notice_match.group("target") or "").strip()
        message = (notice_match.group("message") or "").strip()
        if target.startswith("#"):
            target_channel = normalize_channel_login(target[1:])
            target_label = f"#{target_channel}" if target_channel else target
        else:
            target_label = target or "*"

        if msg_id:
            logger.warning(
                "IRC NOTICE target=%s msg_id=%s message=%s",
                target_label,
                msg_id,
                message,
            )
        else:
            logger.warning("IRC NOTICE target=%s message=%s", target_label, message)

        if is_irc_notice_delivery_block(msg_id, message):
            observability.record_error(
                category="irc_notice",
                details=f"{target_label} {msg_id or 'notice'}: {message}",
            )

    async def _handle_privmsg(self, line: str) -> None:
        match = IRC_PRIVMSG_PATTERN.match(line)
        if not match:
            return

        channel = match.group("channel").lstrip("#").lower()
        if channel not in self.joined_channels:
            return

        author_login = (match.group("author") or "").strip().lower()
        if not author_login or author_login == self.bot_login:
            return

        text = (match.group("message") or "").strip()
        if not text:
            return

        tags = parse_irc_tags(match.group("tags") or "")
        author = IrcAuthor(author_login, tags)
        message = IrcMessageAdapter(text, author)
        byte_prompt = parse_byte_prompt(text)

        # Recupera contexto isolado por canal (Async Lazy Load)
        ctx = await context_manager.get(channel)

        if not text.startswith("!") or byte_prompt is not None:
            if ENABLE_LIVE_CONTEXT_LEARNING:
                ctx.remember_user_message(author.name, text)

                # Persistência de Histórico (Fase 3)
                from bot.persistence_layer import persistence

                asyncio.create_task(persistence.append_history(channel, author.name, text))

            observability.record_chat_message(author_name=author.name, source="irc", text=text)
            sentiment_engine.ingest_message(channel, text)

        updates: list[str] = []
        if ENABLE_LIVE_CONTEXT_LEARNING:
            # A função auto_update_scene_from_message em scene_runtime.py
            # já foi atualizada para usar o canal específico.
            updates = await auto_update_scene_from_message(message, channel_id=channel)
            ctx.stream_vibe = sentiment_engine.get_vibe(channel)
        if updates:
            labels = ", ".join(
                OBSERVABILITY_TYPES.get(content_type, content_type) for content_type in updates
            )
            logger.info("Observabilidade automatica atualizada: %s", labels)
            observability.record_auto_scene_update(update_types=updates)

        if byte_prompt is None:
            return
        observability.record_byte_trigger(prompt=byte_prompt, source="irc", author_name=author.name)
        management_handled = await self._handle_channel_management_prompt(
            byte_prompt, author, channel
        )
        if management_handled:
            return

        async def reply_in_source_channel(text: str) -> None:
            await self.send_reply(text, channel_login=channel)

        await handle_byte_prompt_text(
            byte_prompt,
            author.name,
            reply_in_source_channel,
            status_line_factory=self.build_status_line,
            channel_id=channel,
        )

    async def _recover_authentication(self, auth_error: Exception) -> bool:
        logger.warning("Falha de autenticacao IRC: %s", auth_error)
        observability.record_auth_failure(details=str(auth_error))
        try:
            await self.token_manager.force_refresh("falha de autenticacao IRC")
            logger.info("Reconectando com token renovado automaticamente.")
            return True
        except Exception as refresh_error:
            logger.error("Refresh automatico falhou: %s", refresh_error)
            observability.record_error(category="irc_refresh", details=str(refresh_error))
            return False

    def _raise_auth_error(self, line: str) -> None:
        raise TwitchAuthError(line)
