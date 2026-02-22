import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

from bot.clip_jobs_runtime import ClipJobsRuntime
from bot.twitch_clips_api import create_clip_from_vod, get_clip_download_url, TwitchClipRateLimitError

class TestTwitchClipsApiVod(unittest.TestCase):
    def _mock_urlopen(self, status, json_data):
        mock_response = MagicMock()
        mock_response.status = status
        mock_response.read.return_value = json.dumps(json_data).encode("utf-8")
        
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = mock_response
        mock_ctx.__exit__.return_value = None
        return mock_ctx

    def test_create_clip_from_vod_success(self):
        mock_ctx = self._mock_urlopen(202, {
            "data": [{"id": "ClipVod123", "edit_url": "http://edit"}]
        })
        
        with patch("bot.twitch_clips_api.urlopen", return_value=mock_ctx):
            result = asyncio.run(create_clip_from_vod(
                broadcaster_id="123",
                vod_id="999",
                vod_offset=100,
                duration=30,
                token="token",
                client_id="client",
            ))
            self.assertEqual(result["id"], "ClipVod123")

    def test_create_clip_from_vod_validation(self):
        with self.assertRaises(ValueError):
            asyncio.run(create_clip_from_vod(
                broadcaster_id="123",
                vod_id="999",
                vod_offset=10, # Less than duration
                duration=30,
                token="token",
                client_id="client",
            ))

    def test_get_download_url_success(self):
        mock_ctx = self._mock_urlopen(200, {
            "data": [{"id": "Clip1", "download_url": "http://dl.mp4"}]
        })
        
        with patch("bot.twitch_clips_api.urlopen", return_value=mock_ctx):
            url = asyncio.run(get_clip_download_url(
                clip_id="Clip1",
                broadcaster_id="123",
                token="token",
                client_id="client",
            ))
            self.assertEqual(url, "http://dl.mp4")

    def test_get_download_url_rate_limited(self):
        mock_response = MagicMock()
        mock_response.status = 429 # HTTPError handled inside
        
        # Simulate HTTPError 429
        from urllib.error import HTTPError
        error = HTTPError("url", 429, "Too Many Requests", {"Ratelimit-Reset": "1234567890"}, None)
        
        with patch("bot.twitch_clips_api.urlopen", side_effect=error):
            with self.assertRaises(TwitchClipRateLimitError):
                asyncio.run(get_clip_download_url(
                    clip_id="Clip1",
                    broadcaster_id="123",
                    token="token",
                    client_id="client",
                ))

class TestClipJobsRuntimeVod(unittest.TestCase):
    def setUp(self):
        self.runtime = ClipJobsRuntime()
        self.runtime.bind_token_provider(self._fake_token)

    async def _fake_token(self):
        return "fake_token"

    def test_handle_queued_vod_success(self):
        job = {
            "job_id": "job_vod",
            "action_id": "act_vod",
            "broadcaster_id": "999",
            "mode": "vod",
            "status": "queued",
            "vod_id": "v123",
            "vod_offset": 100,
            "duration": 30,
        }
        self.runtime._jobs["act_vod"] = job
        
        with patch("bot.clip_jobs_runtime.create_clip_from_vod") as mock_create:
            mock_create.return_value = {"id": "ClipV", "edit_url": "http://edit"}
            
            asyncio.run(self.runtime._handle_queued(job))
            
            self.assertEqual(job["status"], "polling")
            self.assertEqual(job["twitch_clip_id"], "ClipV")
            mock_create.assert_called_once()

    def test_handle_queued_vod_missing_params(self):
        job = {
            "job_id": "job_vod_bad",
            "action_id": "act_vod_bad",
            "broadcaster_id": "999",
            "mode": "vod",
            "status": "queued",
            # Missing vod_id
        }
        self.runtime._jobs["act_vod_bad"] = job
        
        asyncio.run(self.runtime._handle_queued(job))
        
        self.assertEqual(job["status"], "failed")
        self.assertIn("Dados de VOD ausentes", str(job["error"]))

    def test_fetch_download_url(self):
        job = {
            "job_id": "job_ready",
            "action_id": "act_ready",
            "broadcaster_id": "999",
            "status": "ready",
            "twitch_clip_id": "ClipX",
            "download_url": None,
        }
        self.runtime._jobs["act_ready"] = job
        
        with patch("bot.clip_jobs_runtime.get_clip_download_url") as mock_dl:
            mock_dl.return_value = "http://dl.mp4"
            
            asyncio.run(self.runtime._handle_download_fetch(job))
            
            self.assertEqual(job["download_url"], "http://dl.mp4")
