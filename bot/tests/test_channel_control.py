import base64
import unittest
from unittest.mock import MagicMock, patch

from bot import channel_control


class TestChannelControl(unittest.TestCase):
    def test_extract_admin_token(self):
        """Should extract token from various header formats."""
        # Direct header
        self.assertEqual(channel_control.extract_admin_token({"X-Byte-Admin-Token": "t1"}), "t1")

        # Bearer token
        self.assertEqual(channel_control.extract_admin_token({"Authorization": "Bearer t2"}), "t2")

        # Basic auth (password part)
        auth_val = base64.b64encode(b"admin:t3").decode()
        self.assertEqual(
            channel_control.extract_admin_token({"Authorization": f"Basic {auth_val}"}), "t3"
        )

        # Basic auth (single value)
        auth_val = base64.b64encode(b"t4").decode()
        self.assertEqual(
            channel_control.extract_admin_token({"Authorization": f"Basic {auth_val}"}), "t4"
        )

        # Empty/Invalid
        self.assertEqual(channel_control.extract_admin_token({}), "")
        self.assertEqual(channel_control.extract_admin_token({"Authorization": "Invalid"}), "")
        self.assertEqual(channel_control.extract_admin_token({"Authorization": "Basic !!!"}), "")

    def test_is_dashboard_admin_authorized(self):
        """Should compare tokens using constant time comparison."""
        headers = {"X-Byte-Admin-Token": "secret"}
        self.assertTrue(channel_control.is_dashboard_admin_authorized(headers, "secret"))
        self.assertFalse(channel_control.is_dashboard_admin_authorized(headers, "wrong"))
        self.assertFalse(channel_control.is_dashboard_admin_authorized({}, "secret"))
        self.assertFalse(channel_control.is_dashboard_admin_authorized(headers, ""))

    def test_parse_terminal_command(self):
        """Should parse human-friendly commands."""
        self.assertEqual(channel_control.parse_terminal_command("list"), ("list", ""))
        self.assertEqual(channel_control.parse_terminal_command("join mychan"), ("join", "mychan"))
        self.assertEqual(channel_control.parse_terminal_command("entrar canal"), ("join", "canal"))
        self.assertEqual(
            channel_control.parse_terminal_command("part oldchan"), ("part", "oldchan")
        )
        self.assertEqual(channel_control.parse_terminal_command("sair tchau"), ("part", "tchau"))

        with self.assertRaises(ValueError):
            channel_control.parse_terminal_command("")
        with self.assertRaises(ValueError):
            channel_control.parse_terminal_command("unknown command")

    def test_irc_channel_control_bridge_execute_no_bind(self):
        """Should fail if bot is not bound."""
        bridge = channel_control.IrcChannelControlBridge()
        result = bridge.execute(action="list")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "runtime_unavailable")

    @patch.object(channel_control.IrcChannelControlBridge, "_submit")
    def test_irc_channel_control_bridge_execute_list(self, mock_submit):
        """Should return channel list from bot."""
        bridge = channel_control.IrcChannelControlBridge()

        def submit_side_effect(coroutine):
            coroutine.close()
            return ["chan1", "chan2"]

        mock_submit.side_effect = submit_side_effect

        result = bridge.execute(action="list")
        self.assertTrue(result["ok"])
        self.assertIn("chan1", result["channels"])
        self.assertIn("chan2", result["channels"])

    def test_irc_channel_control_bridge_invalid_action(self):
        """Should reject unsupported actions."""
        bridge = channel_control.IrcChannelControlBridge()
        result = bridge.execute(action="hack")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid_action")

    def test_irc_channel_control_bridge_missing_channel(self):
        """Should require channel for join/part."""
        bridge = channel_control.IrcChannelControlBridge()
        # Bind just to pass the runtime check
        bridge.bind(loop=MagicMock(is_closed=False, is_running=True), bot=MagicMock())

        result = bridge.execute(action="join", channel_login="")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "missing_channel")

    @patch.object(channel_control.IrcChannelControlBridge, "_submit")
    def test_irc_channel_control_bridge_timeout(self, mock_submit):
        """Should handle future timeout."""
        bridge = channel_control.IrcChannelControlBridge(timeout_seconds=0.1)

        def submit_side_effect(coroutine):
            coroutine.close()
            raise TimeoutError("timeout")

        mock_submit.side_effect = submit_side_effect

        result = bridge.execute(action="list")
        self.assertFalse(result["ok"])
        self.assertIn(result["error"], ["timeout", "runtime_error"])
