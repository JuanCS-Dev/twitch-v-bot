import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.persistence_layer import PersistenceLayer


class TestPersistenceLogicDeepAudit(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Setup de ambiente para habilitar a camada
        self.env_patcher = patch.dict(
            os.environ, {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"}
        )
        self.env_patcher.start()

        # Mock do cliente Supabase
        self.mock_client = MagicMock()
        with patch("bot.persistence_layer.create_client", return_value=self.mock_client):
            self.persistence = PersistenceLayer()

    def tearDown(self):
        self.env_patcher.stop()

    async def test_telemetry_fire_and_forget_resilience(self):
        """Valida que erros na telemetria (log_message) não propagam exceção."""
        # Configura o mock para explodir ao tentar inserir
        self.mock_client.table.return_value.insert.side_effect = Exception("DB Timeout")

        # Não deve levantar exceção (Contrato de Resiliência)
        try:
            self.persistence.log_message_sync("user", "oi", "canal", "source")
            self.persistence.log_reply_sync("prompt", "reply", "user")
        except Exception as e:
            self.fail(f"A telemetria levantou exceção: {e}. Deveria ser silenciosa e resiliente.")

        print("\n[SCIENTIFIC] Telemetry Resilience: OK")

    async def test_history_chronological_integrity(self):
        """Valida que o histórico é reconstruído na ordem correta (Oldest to Newest)."""
        # Dados do banco vêm em ordem decrescente (mais recente primeiro) por causa do .order("ts", desc=True)
        raw_db_data = [
            {"author": "user", "message": "msg 3 (mais recente)"},
            {"author": "user", "message": "msg 2"},
            {"author": "user", "message": "msg 1 (mais antiga)"},
        ]

        # Mock encadeado complexo para o histórico
        self.mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=raw_db_data
        )

        history = await self.persistence.load_recent_history("canal_test", limit=3)

        # A lista final deve estar em ordem cronológica para o Contexto
        self.assertEqual(len(history), 3)
        self.assertIn("msg 1", history[0])
        self.assertIn("msg 3", history[2])

        print("[SCIENTIFIC] History Chronological Integrity: OK")

    async def test_data_safety_truncation(self) -> None:
        """Valida que mensagens gigantes são truncadas antes do banco para evitar 400 Bad Request."""
        huge_msg = "X" * 5000

        # Monitoramos o payload enviado ao insert
        mock_insert = self.mock_client.table.return_value.insert
        mock_insert.return_value.execute.return_value = MagicMock()

        self.persistence.log_message_sync("user", huge_msg)

        sent_payload = mock_insert.call_args[0][0]
        self.assertLessEqual(len(sent_payload["message"]), 2000)
        self.assertTrue(sent_payload["message"].startswith("XXXX"))

        print("[SCIENTIFIC] Data Safety Truncation: OK")


if __name__ == "__main__":
    unittest.main()
