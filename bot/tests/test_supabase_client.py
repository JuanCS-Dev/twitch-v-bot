import unittest
from unittest.mock import MagicMock, patch

import bot.supabase_client as sc


class TestSupabaseClient(unittest.TestCase):
    @patch("bot.supabase_client.persistence")
    def test_is_enabled(self, mock_persistence):
        mock_persistence.is_enabled = True
        self.assertTrue(sc.is_enabled())

        mock_persistence.is_enabled = False
        self.assertFalse(sc.is_enabled())

    @patch("bot.supabase_client.persistence")
    def test_log_message_proxy(self, mock_persistence):
        sc.log_message("user", "msg", "ch", "src")
        mock_persistence.log_message_sync.assert_called_with("user", "msg", "ch", "src")

    @patch("bot.supabase_client.persistence")
    def test_log_reply_proxy(self, mock_persistence):
        sc.log_reply("prompt", "reply", "user", "model", True, 100)
        mock_persistence.log_reply_sync.assert_called_with(
            "prompt", "reply", "user", "model", True, 100
        )

    @patch("bot.supabase_client.persistence")
    def test_log_event_proxy(self, mock_persistence):
        mock_persistence.is_enabled = True
        mock_persistence._client = MagicMock()

        sc.log_event("cat", "detail", {"meta": "data"})

        mock_persistence._client.table.assert_called_with("observability_events")
        mock_persistence._client.table().insert.assert_called()


if __name__ == "__main__":
    unittest.main()
