import unittest
import json
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
import bot.twitch_tokens as tokens


class TestTwitchTokenManager(unittest.IsolatedAsyncioTestCase):
    def test_init_and_properties(self):
        tm = tokens.TwitchTokenManager(
            access_token="oauth:token123",
            refresh_token="refresh123",
            client_id="cid",
            client_secret="cs",
        )
        self.assertEqual(tm.access_token, "token123")
        self.assertEqual(tm.refresh_token, "refresh123")
        self.assertTrue(tm.can_refresh)

    def test_init_without_refresh(self):
        tm = tokens.TwitchTokenManager(access_token="token123")
        self.assertFalse(tm.can_refresh)

    def test_init_strips_oauth_prefix(self):
        tm = tokens.TwitchTokenManager(access_token="oauth:token123")
        self.assertEqual(tm.access_token, "token123")

    def test_init_whitespace_handling(self):
        tm = tokens.TwitchTokenManager(access_token="  token123  ", client_id="  cid  ")
        self.assertEqual(tm.access_token, "token123")
        self.assertEqual(tm.client_id, "cid")

    def test_expiration_logic(self):
        tm = tokens.TwitchTokenManager(access_token="t")
        tm._set_expiration(3600)
        self.assertFalse(tm._is_expiring_soon())

    def test_set_expiration_none(self):
        tm = tokens.TwitchTokenManager(access_token="t")
        tm._set_expiration(None)
        self.assertIsNone(tm.expires_at_monotonic)

    def test_set_expiration_invalid_type(self):
        tm = tokens.TwitchTokenManager(access_token="t")
        tm._set_expiration("invalid")
        self.assertIsNone(tm.expires_at_monotonic)

    def test_set_expiration_negative(self):
        tm = tokens.TwitchTokenManager(access_token="t")
        tm._set_expiration(-100)
        self.assertIsNotNone(tm.expires_at_monotonic)

    def test_is_expiring_soon_none(self):
        tm = tokens.TwitchTokenManager(access_token="t")
        tm.expires_at_monotonic = None
        self.assertFalse(tm._is_expiring_soon())

    def test_is_expiring_soon_true(self):
        tm = tokens.TwitchTokenManager(access_token="t", refresh_margin_seconds=300)
        tm.expires_at_monotonic = time.monotonic() + 100
        self.assertTrue(tm._is_expiring_soon())

    @patch("bot.twitch_tokens.urlopen")
    def test_validate_token_sync_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"client_id": "abc", "expires_in": 3600}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        tm = tokens.TwitchTokenManager(access_token="t", urlopen_fn=mock_urlopen)
        result = tm._validate_token_sync()
        self.assertEqual(result["client_id"], "abc")

    @patch("bot.twitch_tokens.urlopen")
    def test_validate_token_sync_400(self, mock_urlopen):
        mock_urlopen.side_effect = tokens.HTTPError("u", 400, "Bad Request", {}, None)
        tm = tokens.TwitchTokenManager(access_token="t", urlopen_fn=mock_urlopen)
        result = tm._validate_token_sync()
        self.assertIsNone(result)

    @patch("bot.twitch_tokens.urlopen")
    def test_validate_token_sync_401(self, mock_urlopen):
        mock_urlopen.side_effect = tokens.HTTPError("u", 401, "Unauthorized", {}, None)
        tm = tokens.TwitchTokenManager(access_token="t", urlopen_fn=mock_urlopen)
        result = tm._validate_token_sync()
        self.assertIsNone(result)

    @patch("bot.twitch_tokens.urlopen")
    def test_validate_token_sync_other_error(self, mock_urlopen):
        mock_urlopen.side_effect = tokens.HTTPError("u", 500, "Error", {}, None)
        tm = tokens.TwitchTokenManager(access_token="t", urlopen_fn=mock_urlopen)
        with self.assertRaises(tokens.TwitchAuthError):
            tm._validate_token_sync()

    @patch("bot.twitch_tokens.urlopen")
    def test_validate_token_sync_url_error(self, mock_urlopen):
        mock_urlopen.side_effect = tokens.URLError("Connection refused")
        tm = tokens.TwitchTokenManager(access_token="t", urlopen_fn=mock_urlopen)
        with self.assertRaises(tokens.TwitchAuthError):
            tm._validate_token_sync()

    @patch("bot.twitch_tokens.urlopen")
    def test_validate_token_sync_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError()
        tm = tokens.TwitchTokenManager(access_token="t", urlopen_fn=mock_urlopen)
        with self.assertRaises(tokens.TwitchAuthError):
            tm._validate_token_sync()

    @patch("bot.twitch_tokens.urlopen")
    def test_validate_token_sync_invalid_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"not json"
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        tm = tokens.TwitchTokenManager(access_token="t", urlopen_fn=mock_urlopen)
        with self.assertRaises(tokens.TwitchAuthError):
            tm._validate_token_sync()

    @patch("bot.twitch_tokens.urlopen")
    def test_validate_token_sync_non_dict(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'["array"]'
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        tm = tokens.TwitchTokenManager(access_token="t", urlopen_fn=mock_urlopen)
        result = tm._validate_token_sync()
        self.assertIsNone(result)

    @patch("bot.twitch_tokens.urlopen")
    def test_refresh_token_sync_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = (
            b'{"access_token": "new_t", "refresh_token": "new_r", "expires_in": 3600}'
        )
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        tm = tokens.TwitchTokenManager(
            access_token="t",
            refresh_token="r",
            client_id="cid",
            client_secret="cs",
            urlopen_fn=mock_urlopen,
        )
        result = tm._refresh_token_sync()
        self.assertEqual(result["access_token"], "new_t")

    @patch("bot.twitch_tokens.urlopen")
    def test_refresh_token_sync_http_error(self, mock_urlopen):
        mock_error = tokens.HTTPError("u", 400, "Bad Request", {}, None)
        mock_error.read = MagicMock(return_value=b'{"error": "invalid_grant"}')
        mock_urlopen.side_effect = mock_error
        tm = tokens.TwitchTokenManager(
            access_token="t",
            refresh_token="r",
            client_id="cid",
            client_secret="cs",
            urlopen_fn=mock_urlopen,
        )
        with self.assertRaises(tokens.TwitchAuthError):
            tm._refresh_token_sync()

    @patch("bot.twitch_tokens.urlopen")
    def test_refresh_token_sync_non_200(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        tm = tokens.TwitchTokenManager(
            access_token="t",
            refresh_token="r",
            client_id="cid",
            client_secret="cs",
            urlopen_fn=mock_urlopen,
        )
        with self.assertRaises(tokens.TwitchAuthError):
            tm._refresh_token_sync()

    @patch("bot.twitch_tokens.urlopen")
    def test_refresh_token_sync_invalid_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"not json"
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        tm = tokens.TwitchTokenManager(
            access_token="t",
            refresh_token="r",
            client_id="cid",
            client_secret="cs",
            urlopen_fn=mock_urlopen,
        )
        with self.assertRaises(tokens.TwitchAuthError):
            tm._refresh_token_sync()

    @patch("bot.twitch_tokens.urlopen")
    def test_refresh_token_sync_no_access_token(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"refresh_token": "new_r"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        tm = tokens.TwitchTokenManager(
            access_token="t",
            refresh_token="r",
            client_id="cid",
            client_secret="cs",
            urlopen_fn=mock_urlopen,
        )
        with self.assertRaises(tokens.TwitchAuthError):
            tm._refresh_token_sync()

    @patch("bot.twitch_tokens.urlopen")
    async def test_force_refresh_direct(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"access_token": "new_t", "expires_in": 3600}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        tm = tokens.TwitchTokenManager(
            access_token="t",
            refresh_token="r",
            client_id="cid",
            client_secret="cs",
            urlopen_fn=mock_urlopen,
        )
        with patch.object(tm, "_refresh_token_sync") as mock_sync:
            mock_sync.return_value = {"access_token": "new_t", "expires_in": 3600}
            new_t = await tm.force_refresh("reason")
            self.assertEqual(new_t, "new_t")

    async def test_force_refresh_no_credentials(self):
        tm = tokens.TwitchTokenManager(access_token="t")
        with self.assertRaises(tokens.TwitchAuthError):
            await tm.force_refresh("reason")

    @patch("bot.twitch_tokens.urlopen")
    async def test_force_refresh_with_rotation(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = (
            b'{"access_token": "new_t", "refresh_token": "new_r", "expires_in": 3600}'
        )
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        mock_logger = MagicMock()
        tm = tokens.TwitchTokenManager(
            access_token="t",
            refresh_token="r",
            client_id="cid",
            client_secret="cs",
            logger=mock_logger,
            urlopen_fn=mock_urlopen,
        )
        with patch.object(tm, "_refresh_token_sync") as mock_sync:
            mock_sync.return_value = {
                "access_token": "new_t",
                "refresh_token": "new_r",
                "expires_in": 3600,
            }
            await tm.force_refresh("reason")
            self.assertEqual(tm.refresh_token, "new_r")
            mock_logger.info.assert_called()

    @patch("bot.twitch_tokens.urlopen")
    async def test_force_refresh_observability(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"access_token": "new_t", "expires_in": 3600}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        mock_obs = MagicMock()
        tm = tokens.TwitchTokenManager(
            access_token="t",
            refresh_token="r",
            client_id="cid",
            client_secret="cs",
            observability=mock_obs,
            urlopen_fn=mock_urlopen,
        )
        with patch.object(tm, "_refresh_token_sync") as mock_sync:
            mock_sync.return_value = {"access_token": "new_t", "expires_in": 3600}
            await tm.force_refresh("reason")
            mock_obs.record_token_refresh.assert_called_once_with(reason="reason")

    async def test_ensure_token_simple(self):
        tm = tokens.TwitchTokenManager(access_token="t")
        tm.validated_once = True
        tm.expires_at_monotonic = time.monotonic() + 1000

        token = await tm.ensure_token_for_connection()
        self.assertEqual(token, "t")

    async def test_ensure_token_no_access_token(self):
        tm = tokens.TwitchTokenManager(access_token="")
        with self.assertRaises(tokens.TwitchAuthError):
            await tm.ensure_token_for_connection()

    @patch.object(tokens.TwitchTokenManager, "_validate_token_sync")
    @patch.object(tokens.TwitchTokenManager, "force_refresh")
    async def test_ensure_token_refresh_can_refresh_no_expiry(
        self, mock_refresh, mock_validate
    ):
        tm = tokens.TwitchTokenManager(
            access_token="t", refresh_token="r", client_id="c", client_secret="s"
        )
        tm.expires_at_monotonic = None
        mock_validate.return_value = None

        await tm.ensure_token_for_connection()
        mock_refresh.assert_called_once()

    @patch.object(tokens.TwitchTokenManager, "_validate_token_sync")
    @patch.object(tokens.TwitchTokenManager, "force_refresh")
    async def test_ensure_token_refresh_can_refresh_expiring_soon(
        self, mock_refresh, mock_validate
    ):
        tm = tokens.TwitchTokenManager(
            access_token="t",
            refresh_token="r",
            client_id="c",
            client_secret="s",
            refresh_margin_seconds=300,
        )
        tm.expires_at_monotonic = time.monotonic() + 100
        tm.validated_once = True

        await tm.ensure_token_for_connection()
        mock_refresh.assert_called_once()

    @patch.object(tokens.TwitchTokenManager, "_validate_token_sync")
    async def test_ensure_token_no_refresh_not_validated(self, mock_validate):
        tm = tokens.TwitchTokenManager(access_token="t")
        mock_validate.return_value = None

        with self.assertRaises(tokens.TwitchAuthError):
            await tm.ensure_token_for_connection()

    @patch.object(tokens.TwitchTokenManager, "_validate_token_sync")
    async def test_ensure_token_no_refresh_validated(self, mock_validate):
        tm = tokens.TwitchTokenManager(access_token="t")
        mock_validate.return_value = {"expires_in": 3600}

        token = await tm.ensure_token_for_connection()
        self.assertEqual(token, "t")
        self.assertTrue(tm.validated_once)

    @patch("bot.twitch_tokens.TwitchTokenManager.validate_now")
    async def test_validate_clips_auth(self, mock_val):
        tm = tokens.TwitchTokenManager(access_token="t")
        mock_val.return_value = {"scopes": ["clips:edit"]}
        valid, scope = await tm.validate_clips_auth()
        self.assertTrue(valid)
        self.assertTrue(scope)

    @patch("bot.twitch_tokens.TwitchTokenManager.validate_now")
    async def test_validate_clips_auth_no_validation(self, mock_val):
        tm = tokens.TwitchTokenManager(access_token="t")
        mock_val.return_value = None
        valid, scope = await tm.validate_clips_auth()
        self.assertFalse(valid)
        self.assertFalse(scope)

    @patch("bot.twitch_tokens.TwitchTokenManager.validate_now")
    async def test_validate_clips_auth_scopes_string(self, mock_val):
        tm = tokens.TwitchTokenManager(access_token="t")
        mock_val.return_value = {"scopes": "clips:edit other:scope"}
        valid, scope = await tm.validate_clips_auth()
        self.assertTrue(valid)
        self.assertTrue(scope)

    @patch("bot.twitch_tokens.TwitchTokenManager.validate_now")
    async def test_validate_clips_auth_missing_scope(self, mock_val):
        tm = tokens.TwitchTokenManager(access_token="t")
        mock_val.return_value = {"scopes": ["other:scope"]}
        valid, scope = await tm.validate_clips_auth()
        self.assertTrue(valid)
        self.assertFalse(scope)

    @patch("bot.twitch_tokens.TwitchTokenManager.validate_now")
    async def test_validate_clips_auth_observability(self, mock_val):
        mock_obs = MagicMock()
        tm = tokens.TwitchTokenManager(access_token="t", observability=mock_obs)
        mock_val.return_value = {"scopes": ["clips:edit"]}

        await tm.validate_clips_auth()
        mock_obs.update_clips_auth_status.assert_called_once_with(
            token_valid=True, scope_ok=True
        )

    def test_is_irc_auth_failure_line(self):
        self.assertTrue(tokens.is_irc_auth_failure_line("Login authentication failed"))
        self.assertTrue(tokens.is_irc_auth_failure_line("improperly formatted auth"))
        self.assertFalse(tokens.is_irc_auth_failure_line("Welcome"))
        self.assertFalse(tokens.is_irc_auth_failure_line(""))
