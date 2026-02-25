import asyncio
import os

from bot.autonomy_runtime import autonomy_runtime
from bot.clip_jobs_runtime import clip_jobs
from bot.eventsub_runtime import ByteBot
from bot.irc_runtime import IrcByteBot
from bot.observability import observability
from bot.runtime_config import (
    CLIENT_ID,
    TWITCH_BOT_LOGIN,
    TWITCH_CHANNEL_LOGIN,
    TWITCH_CHANNEL_LOGINS_RAW,
    TWITCH_CLIENT_SECRET_INLINE,
    TWITCH_CLIENT_SECRET_NAME,
    TWITCH_IRC_HOST,
    TWITCH_IRC_PORT,
    TWITCH_IRC_TLS,
    TWITCH_REFRESH_TOKEN,
    TWITCH_TOKEN_REFRESH_MARGIN_SECONDS,
    TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS,
    TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS,
    TWITCH_USER_TOKEN,
    irc_channel_control,
    logger,
)
from bot.status_runtime import parse_channel_logins
from bot.twitch_tokens import TwitchTokenManager, TwitchTokenManagerSettings


def get_secret(secret_name: str = "twitch-client-secret") -> str:
    # Ler do ENV usando o nome do secret
    env_key = secret_name.upper().replace("-", "_")
    val = os.environ.get(env_key)
    if val:
        return val
    raise RuntimeError(f"Secret {env_key} not in env.")


def require_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"Variavel obrigatoria ausente: {name}")
    return value


def resolve_irc_channel_logins() -> list[str]:
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
    except Exception as error:
        logger.warning(
            "Nao foi possivel ler segredo '%s' para refresh automatico: %s",
            secret_name,
            error,
        )
        return ""


def build_irc_token_manager() -> TwitchTokenManager:
    user_token = TWITCH_USER_TOKEN or require_env("TWITCH_USER_TOKEN")
    refresh_token = TWITCH_REFRESH_TOKEN.strip()
    settings = TwitchTokenManagerSettings(
        validate_timeout_seconds=TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS,
        refresh_timeout_seconds=TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS,
    )
    if not refresh_token:
        return TwitchTokenManager(
            access_token=user_token,
            settings=settings,
            observability=observability,
            logger=logger,
        )

    client_id = CLIENT_ID or require_env("TWITCH_CLIENT_ID")
    client_secret = resolve_client_secret_for_irc_refresh()
    if not client_secret:
        logger.warning(
            "TWITCH_REFRESH_TOKEN definido, mas TWITCH_CLIENT_SECRET nao encontrado. "
            "Refresh automatico do token nao funcionara. Configure TWITCH_CLIENT_SECRET na Host."
        )

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
    token_manager = build_irc_token_manager()
    channel_logins = resolve_irc_channel_logins()
    bot = IrcByteBot(
        host=TWITCH_IRC_HOST,
        port=TWITCH_IRC_PORT,
        use_tls=TWITCH_IRC_TLS,
        bot_login=TWITCH_BOT_LOGIN or require_env("TWITCH_BOT_LOGIN"),
        channel_logins=channel_logins,
        token_manager=token_manager,
    )

    async def run_with_channel_control() -> None:
        running_loop = asyncio.get_running_loop()
        irc_channel_control.bind(loop=running_loop, bot=bot)

        async def _check_clips_auth() -> None:
            # Avoid circular import
            from bot.control_plane import control_plane

            try:
                token_valid, has_clips_edit = await token_manager.validate_clips_auth()

                config = control_plane.get_config()
                if config.get("clip_pipeline_enabled") and not has_clips_edit:
                    logger.warning(
                        "Pipeline de clips habilitado mas scope 'clips:edit' ausente no token."
                    )

            except Exception as error:
                logger.error("Erro ao validar auth de clips: %s", error)
                observability.record_error(category="clips_auth", details=str(error))

        async def verify_clips_auth_loop() -> None:
            # Initial check
            await asyncio.sleep(5)  # Wait for boot
            while True:
                await _check_clips_auth()
                await asyncio.sleep(3600)

        async def send_autonomy_chat(text: str) -> None:
            await bot.send_reply(text)

        autonomy_runtime.bind(
            loop=running_loop,
            mode="irc",
            auto_chat_dispatcher=send_autonomy_chat,
        )

        # Clip Jobs Runtime
        clip_jobs.bind_token_provider(token_manager.ensure_token_for_connection)
        clip_jobs.start(running_loop)

        # Start background task
        asyncio.create_task(verify_clips_auth_loop())

        try:
            await bot.run_forever()
        finally:
            clip_jobs.stop()
            autonomy_runtime.unbind()
            irc_channel_control.unbind()

    asyncio.run(run_with_channel_control())


def run_eventsub_mode() -> None:
    require_env("TWITCH_CLIENT_ID")
    require_env("TWITCH_BOT_ID")
    require_env("TWITCH_CHANNEL_ID")
    bot = ByteBot(client_secret=get_secret())
    try:
        bot.run()
    finally:
        autonomy_runtime.unbind()
