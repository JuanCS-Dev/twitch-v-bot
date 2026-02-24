from bot.tests.scientific_shared import (
    DummyHTTPResponse,
    ScientificTestCase,
    TwitchTokenManager,
    build_irc_token_manager,
    is_irc_auth_failure_line,
    is_irc_notice_delivery_block,
    patch,
    resolve_irc_channel_logins,
    time,
)


class ScientificTokenAndBootstrapTestsMixin(ScientificTestCase):
    @patch("bot.twitch_tokens.urlopen")
    def test_token_manager_force_refresh_rotates_tokens(self, mock_urlopen):
        mock_urlopen.return_value = DummyHTTPResponse(
            {
                "access_token": "novo_access_token",
                "refresh_token": "novo_refresh_token",
                "expires_in": 3600,
            }
        )
        manager = TwitchTokenManager(
            access_token="old",
            refresh_token="old-refresh",
            client_id="cid",
            client_secret="secret",
        )

        new_access_token = self.loop.run_until_complete(manager.force_refresh("teste"))

        self.assertEqual(new_access_token, "novo_access_token")
        self.assertEqual(manager.access_token, "novo_access_token")
        self.assertEqual(manager.refresh_token, "novo_refresh_token")
        self.assertTrue(
            manager.expires_at_monotonic
            and manager.expires_at_monotonic > time.monotonic()
        )

    def test_irc_auth_failure_detector(self):
        self.assertTrue(
            is_irc_auth_failure_line(
                ":tmi.twitch.tv NOTICE * :Login authentication failed"
            )
        )
        self.assertTrue(
            is_irc_auth_failure_line(":tmi.twitch.tv NOTICE * :Improperly formatted auth")
        )
        self.assertFalse(
            is_irc_auth_failure_line(":tmi.twitch.tv 001 byte_agent :Welcome, GLHF!")
        )

    def test_irc_notice_delivery_block_detector(self):
        self.assertTrue(is_irc_notice_delivery_block("msg_requires_verified_phone_number", ""))
        self.assertTrue(
            is_irc_notice_delivery_block(
                "", "Your phone number must be verified to chat in this channel."
            )
        )
        self.assertFalse(is_irc_notice_delivery_block("", "Welcome, GLHF!"))

    def test_resolve_irc_channel_logins_prefers_multi_channel_env(self):
        with (
            patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGINS_RAW", "canal_a,canal_b"),
            patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGIN", "canal_c"),
        ):
            channels = resolve_irc_channel_logins()
        self.assertEqual(channels, ["canal_a", "canal_b"])

    @patch("bot.bootstrap_runtime.get_secret")
    def test_build_irc_token_manager_with_secret_manager(self, mock_get_secret):
        mock_get_secret.return_value = "secret_from_sm"
        with (
            patch("bot.bootstrap_runtime.TWITCH_USER_TOKEN", "access_token"),
            patch("bot.bootstrap_runtime.TWITCH_REFRESH_TOKEN", "refresh_token"),
            patch("bot.bootstrap_runtime.CLIENT_ID", "client_id"),
            patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_INLINE", ""),
            patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_NAME", "twitch-client-secret"),
            patch("bot.bootstrap_runtime.TWITCH_TOKEN_REFRESH_MARGIN_SECONDS", 300),
        ):
            manager = build_irc_token_manager()

        self.assertTrue(manager.can_refresh)
        self.assertEqual(manager.client_secret, "secret_from_sm")
        self.assertEqual(manager.client_id, "client_id")


