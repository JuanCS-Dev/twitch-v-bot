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
    from bot.heartbeat import start_heartbeat

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
