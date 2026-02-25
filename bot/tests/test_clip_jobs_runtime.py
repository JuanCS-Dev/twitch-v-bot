import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import bot.clip_jobs_runtime as clip_runtime

class TestClipJobsRuntime(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.runtime = clip_runtime.ClipJobsRuntime()

    @patch("bot.clip_jobs_runtime.get_clip", new_callable=AsyncMock)
    async def test_handle_polling_ready(self, mock_get):
        mock_get.return_value = {"url": "https://twitch.tv/clip1"}
        self.runtime._jobs["a1"] = {
            "action_id": "a1", "status": "polling", "twitch_clip_id": "t1", 
            "next_poll_at": 0, "poll_until": 9999999999, "job_id": "j1"
        }
        self.runtime.bind_token_provider(AsyncMock(return_value="token"))
        await self.runtime._handle_polling(self.runtime._jobs["a1"])
        self.assertEqual(self.runtime._jobs["a1"]["status"], "ready")

    @patch("bot.clip_jobs_runtime.get_clip_download_url", new_callable=AsyncMock)
    async def test_handle_download_fetch(self, mock_get_dl):
        mock_get_dl.return_value = "https://dl.url"
        self.runtime._jobs["a1"] = {
            "action_id": "a1", "status": "ready", "twitch_clip_id": "t1", 
            "broadcaster_id": "b1", "job_id": "j1"
        }
        self.runtime.bind_token_provider(AsyncMock(return_value="token"))
        await self.runtime._handle_download_fetch(self.runtime._jobs["a1"])
        self.assertEqual(self.runtime._jobs["a1"]["download_url"], "https://dl.url")

    async def test_handle_polling_timeout(self):
        # Test polling timeout logic
        job = {
            "action_id": "a1", "status": "polling", "twitch_clip_id": "t1", 
            "next_poll_at": 0, "poll_until": 0, "job_id": "j1" # Already expired
        }
        self.runtime._jobs["a1"] = job
        await self.runtime._handle_polling(job)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"], "poll_timeout")
