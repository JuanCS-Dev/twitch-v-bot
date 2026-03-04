import logging
import os
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
    import sys
    import traceback

    from bot.heartbeat import start_heartbeat
    from bot.logic import context_manager

    # Auditoria de Ambiente (HF Read-Only Check)
    try:
        test_file = "/app/write_test.tmp"
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        logger.info("Environment Audit: Write permissions OK")
    except Exception as e:
        logger.warning("Environment Audit: Write permissions restricted: %s", e)

    # Injeta o loop principal
    try:
        loop = asyncio.get_event_loop()
        context_manager.set_main_loop(loop)
    except RuntimeError:
        pass

    def global_exception_handler(loop, context):
        msg = context.get("message")
        logger.critical("UNHANDLED ASYNC ERROR: %s", msg)
        logger.critical("Context: %s", context)
        # Não mata o processo aqui para tentarmos ver o stack trace no log do HF

    start_heartbeat()
    logger.info("Starting Dashboard Server thread...")
    threading.Thread(target=run_server, daemon=True).start()

    try:
        if TWITCH_CHAT_MODE == "irc":
            logger.info("Entering IRC Mode...")
            run_irc_mode()
        else:
            logger.info("Entering EventSub Mode...")
            run_eventsub_mode()
    except Exception as error:
        logger.critical("FATAL CRASH DETECTED")
        logger.critical(traceback.format_exc())
        observability.record_error(category="fatal", details=str(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
