import asyncio
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from bot.persistence_layer import persistence
from bot.persistence_utils import utc_iso_now

logger = logging.getLogger("byte.webhooks")


class OutboundWebhookEngine:
    def __init__(self, max_retries: int = 3, initial_backoff: float = 1.0):
        self._max_retries = max_retries
        self._initial_backoff = initial_backoff

    def _sign_payload(self, payload_bytes: bytes, secret: str) -> str:
        if not secret:
            return ""
        signature = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        return f"sha256={signature}"

    def _sync_post_with_retry(
        self, url: str, payload_bytes: bytes, headers: dict[str, str]
    ) -> tuple[bool, int, int]:
        """Executa a requisição síncrona com retentativas (idealmente chamado em thread)."""
        retries = 0
        backoff = self._initial_backoff
        status_code = 0
        success = False
        start_time = time.time()

        while retries <= self._max_retries:
            try:
                req = urllib.request.Request(
                    url, data=payload_bytes, headers=headers, method="POST"
                )
                with urllib.request.urlopen(req, timeout=5.0) as response:
                    status_code = response.getcode()
                    if 200 <= status_code < 300:
                        success = True
                        break
            except urllib.error.HTTPError as e:
                status_code = e.code
            except Exception as e:
                logger.debug("Webhook post exception to %s: %s", url, e)
                status_code = 0

            retries += 1
            if retries <= self._max_retries:
                time.sleep(backoff)
                backoff *= 2.0

        latency_ms = int((time.time() - start_time) * 1000)
        return success, status_code, latency_ms

    async def _dispatch_single(
        self, channel_id: str, event_type: str, webhook: dict[str, Any], payload: dict[str, Any]
    ) -> None:
        if not webhook.get("is_active"):
            return

        event_types = webhook.get("event_types") or []
        if event_types and event_type not in event_types:
            return

        url = webhook.get("url")
        if not url:
            return

        payload_bytes = json.dumps(payload).encode("utf-8")
        secret = webhook.get("secret") or ""
        signature = self._sign_payload(payload_bytes, secret)

        headers = {"Content-Type": "application/json", "User-Agent": "Byte-Webhook-Engine/1.0"}
        if signature:
            headers["X-Byte-Signature"] = signature

        # Call the synchronous blocking HTTP request inside a separate thread
        success, status_code, latency_ms = await asyncio.to_thread(
            self._sync_post_with_retry, url, payload_bytes, headers
        )

        delivery_log = {
            "event_type": event_type,
            "status_code": status_code,
            "success": success,
            "latency_ms": latency_ms,
            "timestamp": utc_iso_now(),
        }

        # Fire and forget observability persistence
        try:
            await persistence.save_webhook_delivery(
                webhook_id=webhook["id"], channel_id=channel_id, delivery=delivery_log
            )
        except Exception as e:
            logger.error("Erro ao salvar log de webhook: %s", e)

    async def emit_event(self, channel_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """
        Emite um evento para todos os webhooks registrados e ativos de um canal.
        Os envios ocorrem em background (tasks independentes).
        """
        try:
            webhooks = await persistence.load_webhooks(channel_id)
            if not webhooks:
                return

            tasks = []
            for wh in webhooks:
                tasks.append(
                    asyncio.create_task(self._dispatch_single(channel_id, event_type, wh, payload))
                )

            if tasks:
                # Não bloqueia o caller além de lançar as tasks
                # As tasks vão se resolver com seus retries internamente
                for task in tasks:
                    # Garantir que exceptions não caiam no void silently
                    task.add_done_callback(
                        lambda t: (
                            logger.error(f"Webhook task failed: {t.exception()}")
                            if t.exception()
                            else None
                        )
                    )

        except Exception as e:
            logger.error("Erro no engine de webhook ao emitir evento: %s", e)


webhook_engine = OutboundWebhookEngine()
