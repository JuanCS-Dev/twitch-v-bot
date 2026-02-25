import unittest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
import bot.clip_jobs_runtime as clip_runtime

class TestClipJobsRuntimeDetailed(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.runtime = clip_runtime.ClipJobsRuntime()
        # Bind a token provider to avoid early failures
        self.runtime.bind_token_provider(AsyncMock(return_value="token"))

    @patch("bot.clip_jobs_runtime.create_clip_from_vod", new_callable=AsyncMock)
    async def test_handle_queued_vod(self, mock_create):
        mock_create.return_value = {"id": "vod_clip", "edit_url": "url"}
        job = {
            "action_id": "a1", "status": "queued", "broadcaster_id": "b1", 
            "mode": "vod", "vod_id": "v1", "vod_offset": 100, "job_id": "j1"
        }
        self.runtime._jobs["a1"] = job
        await self.runtime._handle_queued(job)
        self.assertEqual(job["status"], "polling")

    async def test_handle_queued_invalid_mode(self):
        job = {
            "action_id": "a1", "status": "queued", "mode": "invalid", 
            "job_id": "j1", "broadcaster_id": "b1"
        }
        self.runtime._jobs["a1"] = job
        await self.runtime._handle_queued(job)
        self.assertEqual(job["status"], "failed")
        self.assertIn("mode_not_supported", job["error"])

    @patch("bot.clip_jobs_runtime.get_clip", new_callable=AsyncMock)
    async def test_handle_polling_ready(self, mock_get):
        mock_get.return_value = {"url": "https://url"}
        job = {
            "action_id": "a1", "status": "polling", "twitch_clip_id": "t1", 
            "next_poll_at": 0, "poll_until": 9999999999, "job_id": "j1"
        }
        self.runtime._jobs["a1"] = job
        await self.runtime._handle_polling(job)
        self.assertEqual(job["status"], "ready")

    @patch("bot.clip_jobs_runtime.get_clip_download_url", new_callable=AsyncMock)
    async def test_handle_download_fetch_rate_limit(self, mock_get_dl):
        from bot.twitch_clips_api import TwitchClipRateLimitError
        mock_get_dl.side_effect = TwitchClipRateLimitError("Limit", reset_at=time.time() + 100)
        job = {
            "action_id": "a1", "status": "ready", "twitch_clip_id": "t1", 
            "broadcaster_id": "b1", "job_id": "j1"
        }
        self.runtime._jobs["a1"] = job
        await self.runtime._handle_download_fetch(job)
        self.assertTrue(job.get("next_download_poll_at", 0) > time.time())
