import asyncio

from bot.tests.scientific_shared import (
    AsyncMock,
    DummyIrcWriter,
    IrcByteBot,
    ScientificTestCase,
    patch,
)


class ScientificIrcControlTestsMixin(ScientificTestCase):
    def test_irc_admin_join_sends_command_and_updates_optimistically(self):
        bot = IrcByteBot(
            host="irc.chat.twitch.tv",
            port=6697,
            use_tls=True,
            bot_login="byte_agent",
            channel_logins=["canal_a"],
            user_token="token",
        )
        writer = DummyIrcWriter()
        bot.writer = writer
        bot.reader = asyncio.StreamReader()
        bot._line_reader_running = True

        success, message, channels = self.loop.run_until_complete(
            bot.admin_join_channel("canal_b")
        )

        self.assertTrue(success)
        self.assertEqual(message, "Joined #canal_b.")
        self.assertIn("canal_b", channels)
        
        # Verify it went to the writer
        self.loop.run_until_complete(asyncio.sleep(0.01))
        self.assertTrue(any("JOIN #canal_b" in line for line in writer.lines))

    def test_irc_admin_part_sends_command_and_updates_optimistically(self):
        bot = IrcByteBot(
            host="irc.chat.twitch.tv",
            port=6697,
            use_tls=True,
            bot_login="byte_agent",
            channel_logins=["canal_a", "canal_b"],
            user_token="token",
        )
        writer = DummyIrcWriter()
        bot.writer = writer
        bot.reader = asyncio.StreamReader()
        bot._line_reader_running = True

        success, message, channels = self.loop.run_until_complete(
            bot.admin_part_channel("canal_b")
        )

        self.assertTrue(success)
        self.assertEqual(message, "Left #canal_b.")
        self.assertNotIn("canal_b", channels)
        
        # Verify it went to the writer
        self.loop.run_until_complete(asyncio.sleep(0.01))
        self.assertTrue(any("PART #canal_b" in line for line in writer.lines))

    @patch("bot.irc_handlers.auto_update_scene_from_message", new_callable=AsyncMock)
    def test_irc_part_source_channel_reports_failure_when_part_fails(self, mock_auto_scene):
        mock_auto_scene.return_value = []
        with patch("bot.irc_runtime.OWNER_ID", "42"):
            bot = IrcByteBot(
                host="irc.chat.twitch.tv",
                port=6697,
                use_tls=True,
                bot_login="byte_agent",
                channel_logins=["canal_a", "canal_b"],
                user_token="token",
            )
            writer = DummyIrcWriter()
            bot.writer = writer
            bot._part_channel = AsyncMock(return_value=False)

            owner_part_source = (
                "@display-name=Juan;user-id=42;mod=0 :juan!juan@juan "
                "PRIVMSG #canal_a :byte part canal_a"
            )
            self.loop.run_until_complete(bot._handle_privmsg(owner_part_source))

            bot._part_channel.assert_awaited_once_with("canal_a")
            payload = "".join(writer.lines)
            self.assertIn("Solicitacao recebida: tentando sair de #canal_a.", payload)
            self.assertIn("Nao consegui sair de #canal_a.", payload)

    @patch("bot.irc_handlers.observability.record_error")
    def test_irc_notice_blocked_delivery_records_observability_error(self, mock_record_error):
        bot = IrcByteBot(
            host="irc.chat.twitch.tv",
            port=6697,
            use_tls=True,
            bot_login="byte_agent",
            channel_logins=["canal_a"],
            user_token="token",
        )
        line = (
            "@msg-id=msg_requires_verified_phone_number :tmi.twitch.tv NOTICE "
            "#canal_a :Your phone number must be verified to chat in this channel."
        )

        self.loop.run_until_complete(bot._handle_notice_line(line))

        mock_record_error.assert_called_once_with(
            category="irc_notice",
            details=(
                "#canal_a msg_requires_verified_phone_number: "
                "Your phone number must be verified to chat in this channel."
            ),
        )
