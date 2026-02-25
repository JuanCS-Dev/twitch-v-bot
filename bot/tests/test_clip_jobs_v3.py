import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.clip_jobs_runtime import ClipJobsRuntime
from bot.twitch_clips_api import (
    TwitchClipAuthError,
    TwitchClipNotFoundError,
    TwitchClipRateLimitError,
)


@pytest.fixture
def runtime():
    rt = ClipJobsRuntime()
    rt._jobs.clear()  # clear loaded from store
    rt._token_provider = AsyncMock(return_value="token123")
    return rt


class TestClipJobsRuntimeV3:
    def test_start_stop(self, runtime):
        loop = MagicMock()
        mock_task = MagicMock()
        loop.create_task.return_value = mock_task
        runtime.start(loop)
        assert runtime._running is True
        loop.create_task.assert_called_once()

        runtime.start(loop)  # double start should be no-op
        assert loop.create_task.call_count == 1

        runtime.stop()
        assert runtime._running is False
        mock_task.cancel.assert_called_once()

    def test_get_jobs(self, runtime):
        runtime._jobs["1"] = {"created_at": "2026-01-01T00:00:00Z", "id": "1"}
        runtime._jobs["2"] = {"created_at": "2026-02-01T00:00:00Z", "id": "2"}
        jobs = runtime.get_jobs()
        assert jobs[0]["id"] == "2"  # Descending sort

    @pytest.mark.asyncio
    async def test_sync_from_queue(self, runtime):
        item = {
            "kind": "clip_candidate",
            "id": "action1",
            "payload": {"broadcaster_id": "123", "mode": "live", "suggested_title": "test"},
        }
        with patch(
            "bot.clip_jobs_runtime.control_plane.list_actions", return_value={"items": [item]}
        ):
            with patch("bot.clip_jobs_runtime.job_store.save_job"):
                await runtime._sync_from_queue()
                assert "action1" in runtime._jobs
                assert runtime._jobs["action1"]["status"] == "queued"

    @pytest.mark.asyncio
    async def test_handle_queued_live(self, runtime):
        job = {
            "action_id": "act1",
            "broadcaster_id": "123",
            "mode": "live",
            "title": "t",
            "status": "queued",
        }
        runtime._jobs["act1"] = job
        with patch("bot.clip_jobs_runtime.create_clip_live", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {"id": "clip1", "edit_url": "url1"}
            with patch("bot.clip_jobs_runtime.job_store.save_job"):
                await runtime._handle_queued(job)
                assert runtime._jobs["act1"]["status"] == "polling"
                assert runtime._jobs["act1"]["twitch_clip_id"] == "clip1"

    @pytest.mark.asyncio
    async def test_handle_queued_vod(self, runtime):
        job = {
            "action_id": "act1",
            "broadcaster_id": "123",
            "mode": "vod",
            "vod_id": "v1",
            "vod_offset": 10,
            "status": "queued",
        }
        runtime._jobs["act1"] = job
        with patch(
            "bot.clip_jobs_runtime.create_clip_from_vod", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = {"id": "clip1"}
            with patch("bot.clip_jobs_runtime.job_store.save_job"):
                await runtime._handle_queued(job)
                assert runtime._jobs["act1"]["status"] == "polling"

    @pytest.mark.asyncio
    async def test_handle_queued_errors(self, runtime):
        job = {"action_id": "act1", "broadcaster_id": "123", "mode": "live", "status": "queued"}
        runtime._jobs["act1"] = job
        with patch(
            "bot.clip_jobs_runtime.create_clip_live", side_effect=TwitchClipAuthError("err")
        ):
            with patch("bot.clip_jobs_runtime.job_store.save_job"):
                await runtime._handle_queued(job)
                assert runtime._jobs["act1"]["status"] == "failed"

        # Missing ID
        job2 = {"action_id": "act2", "broadcaster_id": "123", "mode": "live", "status": "queued"}
        runtime._jobs["act2"] = job2
        with patch(
            "bot.clip_jobs_runtime.create_clip_live", new_callable=AsyncMock, return_value={}
        ):
            with patch("bot.clip_jobs_runtime.job_store.save_job"):
                await runtime._handle_queued(job2)
                assert runtime._jobs["act2"]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_handle_polling_success(self, runtime):
        job = {
            "action_id": "act1",
            "status": "polling",
            "twitch_clip_id": "clip1",
            "next_poll_at": 0.0,
            "poll_until": time.time() + 100,
        }
        runtime._jobs["act1"] = job
        with patch("bot.clip_jobs_runtime.get_clip", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"url": "http://clip"}
            with patch("bot.clip_jobs_runtime.job_store.save_job"):
                await runtime._handle_polling(job)
                assert runtime._jobs["act1"]["status"] == "ready"
                assert runtime._jobs["act1"]["clip_url"] == "http://clip"

    @pytest.mark.asyncio
    async def test_handle_polling_timeout(self, runtime):
        job = {
            "action_id": "act1",
            "status": "polling",
            "twitch_clip_id": "clip1",
            "next_poll_at": 0.0,
            "poll_until": time.time() - 100,  # expired
        }
        runtime._jobs["act1"] = job
        with patch("bot.clip_jobs_runtime.job_store.save_job"):
            await runtime._handle_polling(job)
            assert runtime._jobs["act1"]["status"] == "failed"
            assert runtime._jobs["act1"]["error"] == "poll_timeout"

    @pytest.mark.asyncio
    async def test_process_loop_cancellation(self, runtime):
        runtime._running = True
        with patch(
            "bot.clip_jobs_runtime.ClipJobsRuntime._sync_from_queue",
            side_effect=asyncio.CancelledError(),
        ):
            await runtime._process_loop()
            # Should exit cleanly
