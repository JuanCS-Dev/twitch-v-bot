import unittest
import json
import asyncio
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError
import bot.twitch_clips_api as clips_api


class TestTwitchClipsApi(unittest.IsolatedAsyncioTestCase):
    def test_parse_response_success(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"data": [{"id": "123"}]}'
        result = clips_api._parse_response(mock_resp)
        self.assertEqual(result["data"][0]["id"], "123")

    def test_parse_response_empty(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        result = clips_api._parse_response(mock_resp)
        self.assertEqual(result, {})

    def test_parse_response_invalid_json(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        with self.assertRaises(clips_api.TwitchClipError):
            clips_api._parse_response(mock_resp)

    def test_handle_http_error_401(self):
        with self.assertRaises(clips_api.TwitchClipAuthError):
            clips_api._handle_http_error(HTTPError("u", 401, "Unauthorized", {}, None))

    def test_handle_http_error_403(self):
        with self.assertRaises(clips_api.TwitchClipAuthError):
            clips_api._handle_http_error(HTTPError("u", 403, "Forbidden", {}, None))

    def test_handle_http_error_429_no_header(self):
        with self.assertRaises(clips_api.TwitchClipRateLimitError) as ctx:
            clips_api._handle_http_error(HTTPError("u", 429, "Limit", {}, None))
        self.assertIsNotNone(ctx.exception.reset_at)

    def test_handle_http_error_generic_with_body(self):
        mock_error = HTTPError("u", 500, "Error", {}, None)
        mock_error.read = MagicMock(return_value=b'{"error": "server error"}')
        with self.assertRaises(clips_api.TwitchClipError) as ctx:
            clips_api._handle_http_error(mock_error)
        self.assertIn("500", str(ctx.exception))

    def test_handle_http_error_read_exception(self):
        mock_error = HTTPError("u", 500, "Error", {}, None)
        mock_error.read = MagicMock(side_effect=Exception("read failed"))
        with self.assertRaises(clips_api.TwitchClipError):
            clips_api._handle_http_error(mock_error)

    def test_handle_http_error_codes(self):
        with self.assertRaises(clips_api.TwitchClipNotFoundError):
            clips_api._handle_http_error(HTTPError("u", 404, "Not Found", {}, None))

        with self.assertRaises(clips_api.TwitchClipRateLimitError):
            clips_api._handle_http_error(
                HTTPError("u", 429, "Limit", {"Ratelimit-Reset": "123"}, None)
            )

    def test_create_clip_sync_success(self):
        with patch("bot.twitch_clips_api.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 202
            mock_resp.read.return_value = (
                b'{"data": [{"id": "clip123", "edit_url": "https://edit.url"}]}'
            )
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = clips_api._create_clip_sync(
                "broadcaster123", "token", "clientid", "My Clip", 30.0
            )
            self.assertEqual(result["id"], "clip123")

    def test_create_clip_sync_invalid_status(self):
        with patch("bot.twitch_clips_api.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            with self.assertRaises(clips_api.TwitchClipError):
                clips_api._create_clip_sync("broadcaster123", "token", "clientid")

    def test_create_clip_sync_no_data(self):
        with patch("bot.twitch_clips_api.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 202
            mock_resp.read.return_value = b'{"data": []}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            with self.assertRaises(clips_api.TwitchClipError):
                clips_api._create_clip_sync("broadcaster123", "token", "clientid")

    def test_create_clip_sync_http_error(self):
        with patch("bot.twitch_clips_api.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = HTTPError("u", 500, "Error", {}, None)

            with self.assertRaises(clips_api.TwitchClipError):
                clips_api._create_clip_sync("broadcaster123", "token", "clientid")

    def test_create_clip_sync_url_error(self):
        with patch("bot.twitch_clips_api.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("Connection refused")

            with self.assertRaises(clips_api.TwitchClipError):
                clips_api._create_clip_sync("broadcaster123", "token", "clientid")

    def test_get_clip_sync_success(self):
        with patch("bot.twitch_clips_api.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"data": [{"id": "clip123"}]}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = clips_api._get_clip_sync("clip123", "token", "clientid")
            self.assertEqual(result["id"], "clip123")

    def test_get_clip_sync_not_found_returns_none(self):
        with patch("bot.twitch_clips_api.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"data": []}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = clips_api._get_clip_sync("clip123", "token", "clientid")
            self.assertIsNone(result)

    def test_get_clip_sync_404_raises(self):
        with patch("bot.twitch_clips_api.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = HTTPError("u", 404, "Not Found", {}, None)

            result = clips_api._get_clip_sync("clip123", "token", "clientid")
            self.assertIsNone(result)

    def test_get_clip_sync_other_http_error(self):
        with patch("bot.twitch_clips_api.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = HTTPError("u", 500, "Error", {}, None)

            with self.assertRaises(clips_api.TwitchClipError):
                clips_api._get_clip_sync("clip123", "token", "clientid")

    async def test_create_clip_live(self):
        with patch("bot.twitch_clips_api._create_clip_sync") as mock_sync:
            mock_sync.return_value = {"id": "clip123", "edit_url": "url"}
            result = await clips_api.create_clip_live(
                broadcaster_id="b",
                token="t",
                client_id="c",
                title="Test",
                duration=30.0,
            )
            self.assertEqual(result["id"], "clip123")
            mock_sync.assert_called_once()

    async def test_create_clip_from_vod(self):
        with patch("bot.twitch_clips_api._create_clip_from_vod_sync") as mock_sync:
            mock_sync.return_value = {"id": "clip123"}
            result = await clips_api.create_clip_from_vod(
                broadcaster_id="b",
                editor_id="e",
                vod_id="v",
                vod_offset=60,
                duration=30,
                token="t",
                client_id="c",
            )
            self.assertEqual(result["id"], "clip123")

    def test_create_clip_from_vod_sync_validation(self):
        with self.assertRaises(ValueError):
            clips_api._create_clip_from_vod_sync(
                broadcaster_id="b",
                editor_id="",
                vod_id="v",
                vod_offset=10,
                duration=30,
                token="t",
                client_id="c",
                title="",
            )

    def test_create_clip_from_vod_sync_offset_less_than_duration(self):
        with self.assertRaises(ValueError):
            clips_api._create_clip_from_vod_sync(
                broadcaster_id="b",
                editor_id="e",
                vod_id="v",
                vod_offset=10,
                duration=30,
                token="t",
                client_id="c",
                title="",
            )

    def test_create_clip_from_vod_sync_success(self):
        with patch("bot.twitch_clips_api.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 202
            mock_resp.read.return_value = b'{"data": [{"id": "clip123"}]}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = clips_api._create_clip_from_vod_sync(
                broadcaster_id="b",
                editor_id="e",
                vod_id="v",
                vod_offset=60,
                duration=30,
                token="t",
                client_id="c",
                title="My Clip",
            )
            self.assertEqual(result["id"], "clip123")

    @patch("bot.twitch_clips_api.urlopen")
    async def test_get_clip_download_url_429(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "u", 429, "Limit", {"Ratelimit-Reset": "123"}, None
        )

        with self.assertRaises(clips_api.TwitchClipRateLimitError):
            await clips_api.get_clip_download_url(
                clip_id="1", token="t", client_id="c", broadcaster_id="b", editor_id="e"
            )

    @patch("bot.twitch_clips_api.urlopen")
    async def test_get_clip_download_url_429_no_header(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError("u", 429, "Limit", {}, None)

        with self.assertRaises(clips_api.TwitchClipRateLimitError) as ctx:
            await clips_api.get_clip_download_url(
                clip_id="1", token="t", client_id="c", broadcaster_id="b", editor_id="e"
            )
        self.assertIsNotNone(ctx.exception.reset_at)

    @patch("bot.twitch_clips_api.urlopen")
    async def test_get_clip_download_url_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = (
            b'{"data": [{"landscape_download_url": "https://dl.url"}]}'
        )
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = await clips_api.get_clip_download_url(
            clip_id="1", token="t", client_id="c", broadcaster_id="b", editor_id="e"
        )
        self.assertEqual(result, "https://dl.url")

    @patch("bot.twitch_clips_api.urlopen")
    async def test_get_clip_download_url_empty_data(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"data": []}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = await clips_api.get_clip_download_url(
            clip_id="1", token="t", client_id="c", broadcaster_id="b", editor_id="e"
        )
        self.assertIsNone(result)

    @patch("bot.twitch_clips_api.urlopen")
    async def test_get_clip_download_url_404(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError("u", 404, "Not Found", {}, None)

        result = await clips_api.get_clip_download_url(
            clip_id="1", token="t", client_id="c", broadcaster_id="b", editor_id="e"
        )
        self.assertIsNone(result)

    @patch("bot.twitch_clips_api.urlopen")
    async def test_get_clip_download_url_other_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError("u", 500, "Error", {}, None)

        with self.assertRaises(clips_api.TwitchClipError):
            await clips_api.get_clip_download_url(
                clip_id="1", token="t", client_id="c", broadcaster_id="b", editor_id="e"
            )

    def test_url_error_handling(self):
        with patch("bot.twitch_clips_api.urlopen", side_effect=URLError("DNS fail")):
            with self.assertRaises(clips_api.TwitchClipError):
                asyncio.run(clips_api.get_clip(clip_id="1", token="t", client_id="c"))
