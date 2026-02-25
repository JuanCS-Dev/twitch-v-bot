import unittest
from unittest.mock import patch, MagicMock
import os
import importlib
import bot.supabase_client as supabase_client

class TestSupabaseClient(unittest.TestCase):
    def setUp(self):
        # Reset the singleton state before each test
        supabase_client._client = None
        supabase_client._enabled = False
        # Clear env vars
        if "SUPABASE_URL" in os.environ: del os.environ["SUPABASE_URL"]
        if "SUPABASE_KEY" in os.environ: del os.environ["SUPABASE_KEY"]

    def test_get_client_not_configured(self):
        """Should stay disabled if env vars are missing."""
        client = supabase_client._get_client()
        self.assertFalse(client)
        self.assertFalse(supabase_client.is_enabled())

    @patch("supabase.create_client")
    def test_get_client_success(self, mock_create):
        """Should enable client when env vars are present."""
        os.environ["SUPABASE_URL"] = "https://xyz.supabase.co"
        os.environ["SUPABASE_KEY"] = "fake-key"
        
        mock_instance = MagicMock()
        mock_create.return_value = mock_instance
        
        client = supabase_client._get_client()
        self.assertEqual(client, mock_instance)
        self.assertTrue(supabase_client.is_enabled())
        mock_create.assert_called_once_with("https://xyz.supabase.co", "fake-key")

    @patch("supabase.create_client")
    def test_get_client_failure(self, mock_create):
        """Should handle connection errors gracefully."""
        os.environ["SUPABASE_URL"] = "https://xyz.supabase.co"
        os.environ["SUPABASE_KEY"] = "fake-key"
        mock_create.side_effect = Exception("Connection failed")
        
        client = supabase_client._get_client()
        self.assertFalse(client)
        self.assertFalse(supabase_client.is_enabled())

    @patch("bot.supabase_client.is_enabled", return_value=True)
    @patch("bot.supabase_client._get_client")
    def test_log_message_truncation(self, mock_get_client, mock_enabled):
        """Should truncate messages longer than 2000 chars."""
        mock_db = MagicMock()
        mock_get_client.return_value = mock_db
        
        long_message = "A" * 3000
        supabase_client.log_message("user", long_message, "chan")
        
        mock_db.table.assert_called_with("chat_messages")
        insert_data = mock_db.table().insert.call_args[0][0]
        self.assertEqual(len(insert_data["message"]), 2000)
        self.assertEqual(insert_data["author_name"], "user")

    @patch("bot.supabase_client.is_enabled", return_value=True)
    @patch("bot.supabase_client._get_client")
    def test_log_reply_success(self, mock_get_client, mock_enabled):
        """Should log bot replies correctly."""
        mock_db = MagicMock()
        mock_get_client.return_value = mock_db
        
        supabase_client.log_reply("hello", "world", "user", "model-x", True, 100)
        
        mock_db.table.assert_called_with("bot_replies")
        insert_data = mock_db.table().insert.call_args[0][0]
        self.assertEqual(insert_data["prompt"], "hello")
        self.assertEqual(insert_data["reply"], "world")
        self.assertEqual(insert_data["latency_ms"], 100)

    @patch("bot.supabase_client.is_enabled", return_value=True)
    @patch("bot.supabase_client._get_client")
    def test_log_event_with_metadata(self, mock_get_client, mock_enabled):
        """Should log events with optional metadata."""
        mock_db = MagicMock()
        mock_get_client.return_value = mock_db
        
        metadata = {"foo": "bar"}
        supabase_client.log_event("test_cat", "details", metadata)
        
        mock_db.table.assert_called_with("observability_events")
        insert_data = mock_db.table().insert.call_args[0][0]
        self.assertEqual(insert_data["category"], "test_cat")
        self.assertEqual(insert_data["metadata"], metadata)

    @patch("bot.supabase_client.is_enabled", return_value=True)
    @patch("bot.supabase_client._get_client")
    def test_silent_failure_on_execute(self, mock_get_client, mock_enabled):
        """Should not crash if the database execution fails."""
        mock_db = MagicMock()
        mock_db.table().insert().execute.side_effect = Exception("DB Down")
        mock_get_client.return_value = mock_db
        
        # Should not raise exception
        supabase_client.log_message("user", "msg")
        supabase_client.log_reply("p", "r", "u")
        supabase_client.log_event("cat")
