import asyncio
import os

from bot.autonomy_runtime import autonomy_runtime
from bot.clip_jobs_runtime import clip_jobs
from bot.eventsub_runtime import ByteBot
from bot.irc_runtime import IrcByteBot
from bot.observability import observability
from bot.persistence_layer import persistence
from bot.runtime_config import (
    TWITCH_BOT_LOGIN,
    TWITCH_CHANNEL_LOGIN,
    TWITCH_CHANNEL_LOGINS_RAW,
    TWITCH_CLIENT_ID,
    TWITCH_CLIENT_SECRET_INLINE,
    TWITCH_CLIENT_SECRET_NAME,
    TWITCH_IRC_HOST,
    TWITCH_IRC_PORT,
    TWITCH_IRC_TLS,
    TWITCH_TOKEN_REFRESH_MARGIN_SECONDS,
    logger,
)
from bot.sentiment_engine import sentiment_engine
from bot.status_runtime import parse_channel_logins
from bot.twitch_tokens import TwitchTokenManager


def get_secret(secret_name: str = "twitch-client-secret") -> str:
    value = os.environ.get("TWITCH_CLIENT_SECRET") or ""
    if not value:
        raise RuntimeError(f"Secret não configurado: {secret_name}")
    return value


def require_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"Variavel obrigatoria ausente: {name}")
    return value


async def resolve_irc_channel_logins() -> list[str]:
    """Resolve a lista de canais para entrar (Supabase com Fallback para ENV)."""
    # Tentativa 1: Supabase (PersistenceLayer)
    db_channels = await persistence.get_active_channels()
    if db_channels:
        return db_channels

    # Tentativa 2: Variáveis de Ambiente (Legado/Fallback)
    explicit_channels = parse_channel_logins(TWITCH_CHANNEL_LOGINS_RAW)
    if explicit_channels:
        return explicit_channels
    fallback_channels = parse_channel_logins(TWITCH_CHANNEL_LOGIN)
    if fallback_channels:
        return fallback_channels

    required_single_channel = require_env("TWITCH_CHANNEL_LOGIN")
    required_channels = parse_channel_logins(required_single_channel)
    if not required_channels:
        raise RuntimeError(
            "TWITCH_CHANNEL_LOGIN invalido. Use login Twitch sem # e com 3-25 caracteres."
        )
    return required_channels


def resolve_client_secret_for_irc_refresh() -> str:
    if TWITCH_CLIENT_SECRET_INLINE:
        return TWITCH_CLIENT_SECRET_INLINE

    secret_name = TWITCH_CLIENT_SECRET_NAME or "twitch-client-secret"
    try:
        return get_secret(secret_name=secret_name)
    except RuntimeError as error:
        logger.warning("Falha ao carregar secret '%s': %s", secret_name, error)
        return ""
    except Exception as error:
        logger.warning("Falha ao carregar secret '%s': %s", secret_name, error)
        return ""


def build_irc_token_manager() -> TwitchTokenManager:
    user_token = require_env("TWITCH_USER_TOKEN")
    refresh_token = os.environ.get("TWITCH_REFRESH_TOKEN")
    client_id = TWITCH_CLIENT_ID or require_env("TWITCH_CLIENT_ID")
    client_secret = resolve_client_secret_for_irc_refresh()

    settings = {"clips_auth_scopes": "chat:read chat:edit clips:edit"}

    return TwitchTokenManager(
        access_token=user_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret or "",
        refresh_margin_seconds=TWITCH_TOKEN_REFRESH_MARGIN_SECONDS,
        settings=settings,
        observability=observability,
        logger=logger,
    )


def run_irc_mode() -> None:
    try:
        from bot.logic import context_manager
        from bot.runtime_config import irc_channel_control

        token_manager = build_irc_token_manager()

        async def run_with_channel_control() -> None:
            # Injeta o loop para persistência cross-thread (Dashboard)
            running_loop = asyncio.get_running_loop()
            context_manager.set_main_loop(running_loop)

            # Sincroniza canais permitidos (Supabase ou ENV)
            channel_logins = await resolve_irc_channel_logins()

            bot = IrcByteBot(
                host=TWITCH_IRC_HOST,
                port=TWITCH_IRC_PORT,
                use_tls=TWITCH_IRC_TLS,
                bot_login=TWITCH_BOT_LOGIN or require_env("TWITCH_BOT_LOGIN"),
                channel_logins=channel_logins,
                token_manager=token_manager,
            )

            irc_channel_control.bind(loop=running_loop, bot=bot)

            async def verify_clips_auth_loop() -> None:
                while True:
                    try:
                        await token_manager.validate_clips_auth()
                    except Exception as e:
                        logger.error("Falha ao validar auth de clips: %s", e)
                    await asyncio.sleep(3600)

            # Start background tasks
            asyncio.create_task(verify_clips_auth_loop())

            # Fase 4: Loop de limpeza de memoria (Context + Sentiment)
            asyncio.create_task(context_manager.start_cleanup_loop())

            try:
                await bot.run_forever()
            finally:
                clip_jobs.stop()
                autonomy_runtime.unbind()
                irc_channel_control.unbind()

        asyncio.run(run_with_channel_control())
    except Exception as error:
        logger.critical("Fatal Byte Error (IRC): %s", error)
        observability.record_error(category="fatal_irc", details=str(error))


def run_eventsub_mode() -> None:
    async def run_async() -> None:
        from bot.logic import context_manager

        context_manager.set_main_loop(asyncio.get_running_loop())

        require_env("TWITCH_CLIENT_ID")
        require_env("TWITCH_BOT_ID")
        require_env("TWITCH_CHANNEL_ID")
        bot = ByteBot(client_secret=get_secret())
        try:
            await bot.run()
        finally:
            autonomy_runtime.unbind()

    try:
        asyncio.run(run_async())
    except Exception as error:
        logger.critical("Fatal Byte Error (EventSub): %s", error)
        observability.record_error(category="fatal_eventsub", details=str(error))
