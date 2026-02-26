from bot.tests.scientific_shared import (
    AsyncMock,
    DummyIrcWriter,
    IrcByteBot,
    MagicMock,
    ScientificTestCase,
    auto_update_scene_from_message,
    context_manager,
    patch,
)


class ScientificSceneAndIrcTestsMixin(ScientificTestCase):
    def test_auto_scene_update_for_trusted_link(self):
        with (
            patch("bot.scene_runtime.OWNER_ID", "123"),
            patch(
                "bot.scene_runtime.resolve_scene_metadata", new_callable=AsyncMock
            ) as mock_metadata,
        ):
            mock_metadata.return_value = {"title": "Review sem spoiler"}
            msg = MagicMock()
            msg.text = "Olha esse video https://youtube.com/watch?v=abc123"
            msg.author.id = "123"
            msg.author.is_mod = False
            msg.author.name = "owner"
            updates = self.loop.run_until_complete(
                auto_update_scene_from_message(msg, channel_id="default")
            )

            self.assertIn("youtube", updates)
            self.assertEqual(
                context_manager.get("default").live_observability["youtube"],
                'Video do YouTube: "Review sem spoiler" (compartilhado por owner)',
            )

    def test_auto_scene_blocks_sensitive_content(self):
        with patch("bot.scene_runtime.OWNER_ID", "123"):
            msg = MagicMock()
            msg.text = "video nude https://youtube.com/watch?v=abc123"
            msg.author.id = "123"
            msg.author.is_mod = False
            msg.author.name = "owner"
            updates = self.loop.run_until_complete(
                auto_update_scene_from_message(msg, channel_id="default")
            )

            self.assertEqual(updates, [])
            self.assertEqual(context_manager.get("default").live_observability["youtube"], "")

    def test_auto_scene_update_for_x_link(self):
        with (
            patch("bot.scene_runtime.OWNER_ID", "123"),
            patch(
                "bot.scene_runtime.resolve_scene_metadata", new_callable=AsyncMock
            ) as mock_metadata,
        ):
            mock_metadata.return_value = {"author_name": "CinemaCentral"}
            msg = MagicMock()
            msg.text = "Olha esse post https://x.com/user/status/12345"
            msg.author.id = "123"
            msg.author.is_mod = False
            msg.author.name = "owner"
            updates = self.loop.run_until_complete(
                auto_update_scene_from_message(msg, channel_id="default")
            )

            self.assertIn("x", updates)
            self.assertEqual(
                context_manager.get("default").live_observability["x"],
                "Post do X de CinemaCentral (compartilhado por owner)",
            )

    def test_auto_scene_blocks_sensitive_metadata(self):
        with (
            patch("bot.scene_runtime.OWNER_ID", "123"),
            patch(
                "bot.scene_runtime.resolve_scene_metadata", new_callable=AsyncMock
            ) as mock_metadata,
        ):
            mock_metadata.return_value = {"title": "analise nsfw de trailer"}
            msg = MagicMock()
            msg.text = "Olha esse video https://youtube.com/watch?v=abc123"
            msg.author.id = "123"
            msg.author.is_mod = False
            msg.author.name = "owner"
            updates = self.loop.run_until_complete(
                auto_update_scene_from_message(msg, channel_id="default")
            )

            self.assertEqual(updates, [])
            self.assertEqual(context_manager.get("default").live_observability["youtube"], "")

    def test_auto_scene_requires_metadata(self):
        with (
            patch("bot.scene_runtime.OWNER_ID", "123"),
            patch("bot.scene_runtime.AUTO_SCENE_REQUIRE_METADATA", True),
            patch(
                "bot.scene_runtime.resolve_scene_metadata", new_callable=AsyncMock
            ) as mock_metadata,
        ):
            mock_metadata.return_value = None
            msg = MagicMock()
            msg.text = "Olha esse video https://youtube.com/watch?v=abc123"
            msg.author.id = "123"
            msg.author.is_mod = False
            msg.author.name = "owner"
            updates = self.loop.run_until_complete(
                auto_update_scene_from_message(msg, channel_id="default")
            )

            self.assertEqual(updates, [])
            self.assertEqual(context_manager.get("default").live_observability["youtube"], "")

    def test_auto_scene_ignores_untrusted_user(self):
        with patch("bot.scene_runtime.OWNER_ID", "123"):
            msg = MagicMock()
            msg.text = "Olha https://youtube.com/watch?v=abc123"
            msg.author.id = "999"
            msg.author.is_mod = False
            msg.author.is_moderator = False
            msg.author.name = "viewer"
            updates = self.loop.run_until_complete(
                auto_update_scene_from_message(msg, channel_id="default")
            )

            self.assertEqual(updates, [])
            self.assertEqual(context_manager.get("default").live_observability["youtube"], "")

    @patch("bot.irc_handlers.auto_update_scene_from_message", new_callable=AsyncMock)
    @patch("bot.irc_handlers.handle_byte_prompt_text", new_callable=AsyncMock)
    def test_irc_replies_to_the_source_channel(self, mock_handle_prompt, mock_auto_scene):
        mock_auto_scene.return_value = []

        async def fake_handle(
            prompt, author_name, reply_fn, status_line_factory=None, channel_id=None
        ):
            await reply_fn("ok no canal certo")

        mock_handle_prompt.side_effect = fake_handle
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

        line = (
            "@display-name=Alice;user-id=33;mod=0 :alice!alice@alice PRIVMSG #canal_b :byte status"
        )
        self.loop.run_until_complete(bot._handle_privmsg(line))

        payload = "".join(writer.lines)
        self.assertIn("PRIVMSG #canal_b :ok no canal certo\r\n", payload)
        self.assertNotIn("PRIVMSG #canal_a :ok no canal certo\r\n", payload)

    @patch("bot.irc_handlers.auto_update_scene_from_message", new_callable=AsyncMock)
    def test_irc_owner_can_manage_channels_without_redeploy(self, mock_auto_scene):
        mock_auto_scene.return_value = []
        with patch("bot.irc_runtime.OWNER_ID", "42"):
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

            non_owner_join = "@display-name=User;user-id=99;mod=0 :user!user@user PRIVMSG #canal_a :byte join canal_b"
            self.loop.run_until_complete(bot._handle_privmsg(non_owner_join))
            self.assertNotIn("canal_b", bot.channel_logins)

            owner_join = "@display-name=Juan;user-id=42;mod=0 :juan!juan@juan PRIVMSG #canal_a :byte join canal_b"
            self.loop.run_until_complete(bot._handle_privmsg(owner_join))
            self.assertNotIn("canal_b", bot.channel_logins)

            join_confirmation_line = ":byte_agent!byte_agent@byte_agent.tmi.twitch.tv JOIN #canal_b"
            self.loop.run_until_complete(bot._handle_membership_event(join_confirmation_line))
            self.assertIn("canal_b", bot.channel_logins)

            owner_list = (
                "@display-name=Juan;user-id=42;mod=0 :juan!juan@juan PRIVMSG #canal_a :byte canais"
            )
            self.loop.run_until_complete(bot._handle_privmsg(owner_list))

            owner_part = "@display-name=Juan;user-id=42;mod=0 :juan!juan@juan PRIVMSG #canal_a :byte part canal_b"
            self.loop.run_until_complete(bot._handle_privmsg(owner_part))
            self.assertIn("canal_b", bot.channel_logins)

            part_confirmation_line = ":byte_agent!byte_agent@byte_agent.tmi.twitch.tv PART #canal_b"
            self.loop.run_until_complete(bot._handle_membership_event(part_confirmation_line))
            self.assertEqual(bot.channel_logins, ["canal_a"])

            payload = "".join(writer.lines)
            self.assertIn("Somente o owner pode gerenciar canais do Byte.", payload)
            self.assertIn("JOIN #canal_b\r\n", payload)
            self.assertIn("Canais ativos: #canal_a, #canal_b.", payload)
            self.assertIn("PART #canal_b\r\n", payload)
