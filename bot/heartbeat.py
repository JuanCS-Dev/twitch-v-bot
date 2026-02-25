"""Self-heartbeat to keep HF Spaces alive.

Pings the bot's own /health endpoint every HEARTBEAT_INTERVAL_SECONDS
to prevent HF Spaces from putting the container to sleep.
"""

import http.client
import logging
import os
import threading
import time

logger = logging.getLogger("ByteBot")

HEARTBEAT_INTERVAL_SECONDS = 180  # 3 minutes


def _heartbeat_loop(stop_event: threading.Event | None = None) -> None:
    """Background loop that pings localhost health endpoint."""
    port = int(os.environ.get("PORT", "7860"))
    while stop_event is None or not stop_event.is_set():
        if stop_event is None:
            time.sleep(HEARTBEAT_INTERVAL_SECONDS)
        else:
            # For tests, don't wait 3 minutes
            if stop_event.wait(0.1):
                break

        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/health")
            resp = conn.getresponse()
            resp.read()
            conn.close()
            logger.debug("Heartbeat OK (%d)", resp.status)
        except Exception:
            logger.debug("Heartbeat ping failed (server may be starting)")


def start_heartbeat() -> tuple[threading.Thread, threading.Event]:
    """Start the heartbeat daemon thread. Returns (thread, stop_event)."""
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_heartbeat_loop,
        args=(stop_event,),
        name="heartbeat",
        daemon=True,
    )
    thread.start()
    logger.info("Heartbeat started (every %ds)", HEARTBEAT_INTERVAL_SECONDS)
    return thread, stop_event
