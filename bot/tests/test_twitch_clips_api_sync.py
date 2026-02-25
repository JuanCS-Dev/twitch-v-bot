import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
import bot.twitch_clips_api as clips_api

class TestTwitchClipsApiSyncFixed(unittest.TestCase):
    @patch("bot.twitch_clips_api.urlopen")
    def test_create_clip_sync_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 202
        mock_resp.read.return_value = b'{"data": [{"id": "SyncClip"}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        
        result = clips_api._create_clip_sync("b", "t", "c", title="test", duration=45)
        self.assertEqual(result["id"], "SyncClip")

    def test_handle_http_error_auth(self):
        err = HTTPError("u", 401, "Auth", {}, None)
        with self.assertRaises(clips_api.TwitchClipAuthError):
            clips_api._handle_http_error(err)

    def test_handle_http_error_forbidden(self):
        err = HTTPError("u", 403, "Forbidden", {}, None)
        with self.assertRaises(clips_api.TwitchClipAuthError):
            clips_api._handle_http_error(err)

    def test_handle_http_error_not_found(self):
        err = HTTPError("u", 404, "Not Found", {}, None)
        with self.assertRaises(clips_api.TwitchClipNotFoundError):
            clips_api._handle_http_error(err)

    def test_handle_http_error_generic(self):
        err = HTTPError("u", 500, "Internal", {}, None)
        with self.assertRaises(clips_api.TwitchClipError):
            clips_api._handle_http_error(err)

    @patch("bot.twitch_clips_api.urlopen")
    def test_get_clip_sync_not_found(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"data": []}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        
        result = clips_api._get_clip_sync("1", "t", "c")
        self.assertIsNone(result)

    @patch("bot.twitch_clips_api.urlopen")
    def test_get_clip_download_url_sync_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"data": [{"landscape_download_url": "https://dl"}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        
        result = clips_api._get_clip_download_url_sync("1", "t", "c", "b", "e")
        self.assertEqual(result, "https://dl")
