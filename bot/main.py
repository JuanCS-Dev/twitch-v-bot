import threading

from bot.bootstrap_runtime import (
    run_eventsub_mode,
    run_irc_mode,
)
from bot.dashboard_server import run_server
from bot.observability import observability
from bot.runtime_config import (
    TWITCH_CHAT_MODE,
    logger,
)


def main() -> None:
    import asyncio

    from bot.heartbeat import start_heartbeat
    from bot.logic import context_manager

    # Injeta o loop principal para persistência cross-thread (Dashboard)
    try:
        loop = asyncio.get_event_loop()
        context_manager.set_main_loop(loop)
    except RuntimeError:
        pass

    start_heartbeat()
    threading.Thread(target=run_server, daemon=True).start()
    try:
        if TWITCH_CHAT_MODE == "irc":
            run_irc_mode()
        else:
            run_eventsub_mode()
    except Exception as error:
        logger.critical("Fatal Byte Error: %s", error)
        observability.record_error(category="fatal", details=str(error))


if __name__ == "__main__":
    main()
