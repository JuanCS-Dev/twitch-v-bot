import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import dateutil.parser

from bot.persistence_utils import utc_iso_now

logger = logging.getLogger("byte.revenue_attribution")


def _parse_iso_to_timestamp(iso_str: str) -> float:
    try:
        dt = dateutil.parser.isoparse(iso_str)
        return dt.timestamp()
    except Exception:
        return 0.0


class RevenueAttributionEngine:
    def __init__(self, persistence_layer: Any) -> None:
        self._persistence_layer = persistence_layer
        # Janela de atribuição em segundos (ex: 5 minutos = 300 segundos)
        self._attribution_window_seconds = 300

    def process_conversion(
        self,
        channel_id: str,
        event_type: str,
        viewer_id: str,
        viewer_login: str,
        revenue_value: float,
        currency: str = "USD",
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """
        Processa um evento de conversão e tenta atribuí-lo a uma ação recente do agente.
        """
        now_str = timestamp or utc_iso_now()
        now_ts = _parse_iso_to_timestamp(now_str)

        conversion_event = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "viewer_id": viewer_id,
            "viewer_login": viewer_login,
            "revenue_value": revenue_value,
            "currency": currency,
            "timestamp": now_str,
            "attributed_action_id": "",
            "attributed_action_type": "",
            "attribution_window_seconds": 0,
        }

        # Busca histórico recente do bot no canal para tentar correlacionar
        recent_history = self._persistence_layer.load_observability_channel_history_sync(
            channel_id, limit=20
        )

        # Lógica determinística: procura ações do bot recentes (ex: clip_generated, coaching_prompt, message)
        attributed = False
        for snapshot in recent_history:
            # Observability snapshot base
            snap_time = snapshot.get("timestamp") or ""
            snap_ts = _parse_iso_to_timestamp(snap_time)

            if now_ts - snap_ts > self._attribution_window_seconds or now_ts < snap_ts:
                continue  # Fora da janela

            state = snapshot.get("state") or {}
            last_action = state.get("last_action") or ""

            if last_action:
                conversion_event["attributed_action_id"] = str(uuid.uuid4())[
                    :8
                ]  # Simulando ID de ação
                conversion_event["attributed_action_type"] = last_action
                conversion_event["attribution_window_seconds"] = int(now_ts - snap_ts)
                attributed = True
                break

        # Se não achou na história de observabilidade, podemos também olhar recent_history de mensagens
        if not attributed:
            chat_history = self._persistence_layer.load_recent_history_sync(channel_id, limit=10)
            # chat_history tem o formato "Author: Message" ou similar.
            # É apenas texto, mas se o bot falou algo na janela (a gente pode assumir que a última msg do bot "foi" a ação)
            # Simplificando para a Fase 17: se não houver snapshot claro, fica sem atribuição ou atrelado a "organic".

        # Salva o evento persistente
        saved = self._persistence_layer.save_revenue_conversion_sync(channel_id, conversion_event)
        return saved
