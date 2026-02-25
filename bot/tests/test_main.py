import unittest
from unittest.mock import MagicMock, patch

from bot.main import main


class TestMain(unittest.TestCase):
    @patch("bot.heartbeat.start_heartbeat")
    @patch("threading.Thread")
    @patch("bot.main.TWITCH_CHAT_MODE", "irc")
    @patch("bot.main.run_irc_mode")
    def test_main_irc_mode(self, mock_run_irc, mock_thread, mock_heartbeat):
        main()
        mock_heartbeat.assert_called_once()
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()
        mock_run_irc.assert_called_once()

    @patch("bot.heartbeat.start_heartbeat")
    @patch("threading.Thread")
    @patch("bot.main.TWITCH_CHAT_MODE", "eventsub")
    @patch("bot.main.run_eventsub_mode")
    def test_main_eventsub_mode(self, mock_run_eventsub, mock_thread, mock_heartbeat):
        main()
        mock_run_eventsub.assert_called_once()

    @patch("bot.heartbeat.start_heartbeat")
    @patch("threading.Thread")
    @patch("bot.main.run_irc_mode", side_effect=ValueError("Test fatal error"))
    @patch("bot.main.TWITCH_CHAT_MODE", "irc")
    @patch("bot.main.observability.record_error")
    @patch("bot.main.logger.critical")
    def test_main_exception_handling(
        self, mock_logger, mock_record, mock_run_irc, mock_thread, mock_heartbeat
    ):
        main()
        mock_logger.assert_called_once()
        mock_record.assert_called_once_with(category="fatal", details="Test fatal error")
