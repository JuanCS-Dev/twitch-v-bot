import os
import asyncio
from typing import Any, cast

import twitchio  # pyright: ignore[reportMissingImports]
from twitchio import eventsub  # pyright: ignore[reportMissingImports]
from twitchio.ext import commands  # pyright: ignore[reportMissingImports]

from bot.access_control import is_owner
from bot.autonomy_runtime import autonomy_runtime
from bot.logic import BOT_BRAND, OBSERVABILITY_TYPES, agent_inference, context
from bot.observability import observability
from bot.prompt_runtime import format_chat_reply, handle_byte_prompt_text
from bot.runtime_config import (
    BOT_ID,
    CHANNEL_ID,
    CLIENT_ID,
    ENABLE_LIVE_CONTEXT_LEARNING,
    OWNER_ID,
    client,
    logger,
)
from bot.scene_runtime import auto_update_scene_from_message
from bot.status_runtime import build_status_line
from bot import byte_semantics


def _require_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"Variavel obrigatoria ausente: {name}")
    return value


def get_ctx_message_text(ctx: commands.Context) -> str:
    message = getattr(ctx, "message", None)
    return str(getattr(message, "text", "") or "")


def get_ctx_author(ctx: commands.Context) -> Any:
    message = getattr(ctx, "message", None)
    return getattr(message, "author", None)


parse_byte_prompt = byte_semantics.parse_byte_prompt


class AgentComponent(commands.Component):
    def __init__(self, bot: "ByteBot") -> None:
        self.bot = bot

    async def component_check(self, ctx: commands.Context) -> bool:
        return True

    @commands.command(name="ask")
    async def ask(self, ctx: commands.Context) -> None:
        query = get_ctx_message_text(ctx).removeprefix("!ask").strip()
        if not query:
            return
        author_name = str(getattr(get_ctx_author(ctx), "name", "viewer") or "viewer")
        ans = await agent_inference(
            query,
            author_name,
            client,
            context,
            enable_live_context=ENABLE_LIVE_CONTEXT_LEARNING,
        )
        await ctx.reply(format_chat_reply(ans))

    @commands.command(name="vibe")
    async def vibe(self, ctx: commands.Context) -> None:
        author_id = str(getattr(get_ctx_author(ctx), "id", "") or "")
        if is_owner(author_id, OWNER_ID):
            new_vibe = get_ctx_message_text(ctx).removeprefix("!vibe").strip()
            context.stream_vibe = new_vibe or "Conversa"
            context.last_event = "Vibe atualizada"
            await ctx.reply(f"Vibe atualizada para: {context.stream_vibe}")

    @commands.command(name="style")
    async def style(self, ctx: commands.Context) -> None:
        style_text = get_ctx_message_text(ctx).removeprefix("!style").strip()
        author_id = str(getattr(get_ctx_author(ctx), "id", "") or "")
        if not is_owner(author_id, OWNER_ID):
            await ctx.reply("Somente o dono do canal pode ajustar o estilo.")
            return
        if not style_text:
            await ctx.reply(format_chat_reply(f"Estilo atual: {context.style_profile}"))
            return

        context.style_profile = style_text
        context.last_event = "Estilo de conversa atualizado"
        await ctx.reply("Estilo de conversa atualizado.")

    @commands.command(name="scene")
    async def scene(self, ctx: commands.Context) -> None:
        payload = get_ctx_message_text(ctx).removeprefix("!scene").strip()
        if not payload:
            observability_text = context.format_observability()
            await ctx.reply(
                format_chat_reply(f"Observabilidade da live: {observability_text}")
            )
            return

        author_id = str(getattr(get_ctx_author(ctx), "id", "") or "")
        if not is_owner(author_id, OWNER_ID):
            await ctx.reply("Somente o dono do canal pode atualizar a observabilidade.")
            return

        tokens = payload.split(maxsplit=1)
        action_or_type = tokens[0].lower()
        if action_or_type == "clear":
            if len(tokens) < 2:
                await ctx.reply(
                    f"Uso: !scene clear <tipo>. Tipos: {context.list_supported_content_types()}"
                )
                return
            content_type = tokens[1].strip().lower()
            if not context.clear_content(content_type):
                await ctx.reply(
                    f"Tipo invalido. Tipos: {context.list_supported_content_types()}"
                )
                return
            label = OBSERVABILITY_TYPES.get(content_type, content_type)
            await ctx.reply(f"Contexto removido: {label}.")
            return

        if len(tokens) < 2:
            await ctx.reply(
                f"Uso: !scene <tipo> <descricao>. Tipos: {context.list_supported_content_types()}"
            )
            return

        content_type = action_or_type
        description = tokens[1].strip()
        if not context.update_content(content_type, description):
            await ctx.reply(
                f"Tipo invalido ou descricao vazia. Tipos: {context.list_supported_content_types()}"
            )
            return

        label = OBSERVABILITY_TYPES.get(content_type, content_type)
        await ctx.reply(format_chat_reply(f"Contexto atualizado: {label} -> {description}"))

    @commands.command(name="status")
    async def status(self, ctx: commands.Context) -> None:
        await ctx.reply(format_chat_reply(self.bot.build_status_line()))


class ByteBot(commands.Bot):
    def __init__(self, client_secret: str) -> None:
        resolved_client_id = CLIENT_ID or _require_env("TWITCH_CLIENT_ID")
        resolved_bot_id = BOT_ID or _require_env("TWITCH_BOT_ID")
        super().__init__(
            client_id=resolved_client_id,
            client_secret=client_secret,
            bot_id=resolved_bot_id,
            owner_id=OWNER_ID or "",
            prefix="!",
        )

    async def setup_hook(self) -> None:
        autonomy_runtime.bind(
            loop=asyncio.get_running_loop(),
            mode="eventsub",
            auto_chat_dispatcher=None,
        )
        await self.add_component(AgentComponent(self))
        if not CHANNEL_ID:
            raise RuntimeError("TWITCH_CHANNEL_ID e obrigatorio no modo eventsub.")
        payload = eventsub.ChatMessageSubscription(
            broadcaster_user_id=str(CHANNEL_ID),
            user_id=str(self.bot_id),
        )
        await self.subscribe_websocket(payload=payload, as_bot=True)

    async def close(self) -> None:
        autonomy_runtime.unbind()
        await super().close()

    async def event_ready(self) -> None:
        logger.info("%s pronto no chat. Bot ID: %s", BOT_BRAND, self.bot_id)

    def build_status_line(self) -> str:
        return build_status_line()

    async def handle_byte_prompt(self, message: Any, prompt: str) -> None:
        author = getattr(message, "author", None)
        author_name = str(getattr(author, "name", "viewer") or "viewer")
        reply_fn = getattr(message, "reply", None)
        if callable(reply_fn):
            await handle_byte_prompt_text(
                prompt,
                author_name,
                reply_fn,
                status_line_factory=self.build_status_line,
            )

    async def event_message(self, payload: twitchio.ChatMessage) -> None:
        message = cast(Any, payload)
        if message.echo:
            return

        raw_text = message.text or ""
        author = getattr(message, "author", None)
        author_name = str(getattr(author, "name", "viewer") or "viewer")
        byte_prompt = parse_byte_prompt(raw_text)
        if raw_text and (not raw_text.startswith("!") or byte_prompt is not None):
            if ENABLE_LIVE_CONTEXT_LEARNING:
                context.remember_user_message(author_name, raw_text)
            observability.record_chat_message(
                author_name=author_name, source="eventsub", text=raw_text
            )

        updates: list[str] = []
        if ENABLE_LIVE_CONTEXT_LEARNING:
            updates = await auto_update_scene_from_message(message)
        if updates:
            labels = ", ".join(
                OBSERVABILITY_TYPES.get(content_type, content_type)
                for content_type in updates
            )
            logger.info("Observabilidade automatica atualizada: %s", labels)
            observability.record_auto_scene_update(update_types=updates)

        if byte_prompt is not None:
            observability.record_byte_trigger(
                prompt=byte_prompt, source="eventsub", author_name=author_name
            )
            await self.handle_byte_prompt(message, byte_prompt)
            return

        await cast(Any, self).handle_commands(message)
