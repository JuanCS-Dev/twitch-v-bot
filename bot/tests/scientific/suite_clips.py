import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

from bot.autonomy_logic import process_autonomy_goal
from bot.clip_jobs_runtime import ClipJobsRuntime
from bot.control_plane import RISK_CLIP_CANDIDATE
from bot.twitch_clips_api import create_clip_live, get_clip


class TestTwitchClipsAPI(unittest.TestCase):
    def _mock_urlopen(self, status, json_data):
        mock_response = MagicMock()
        mock_response.status = status
        mock_response.read.return_value = json.dumps(json_data).encode("utf-8")
        
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = mock_response
        mock_ctx.__exit__.return_value = None
        return mock_ctx

    def test_create_clip_live_success(self):
        mock_ctx = self._mock_urlopen(202, {
            "data": [{"id": "Clip123", "edit_url": "http://edit"}]
        })
        
        with patch("bot.twitch_clips_api.urlopen", return_value=mock_ctx):
            result = asyncio.run(create_clip_live(
                broadcaster_id="123",
                token="token",
                client_id="client",
            ))
            self.assertEqual(result["id"], "Clip123")

    def test_get_clip_found(self):
        mock_ctx = self._mock_urlopen(200, {
            "data": [{"id": "Clip123", "url": "http://clip"}]
        })
        
        with patch("bot.twitch_clips_api.urlopen", return_value=mock_ctx):
            result = asyncio.run(get_clip(
                clip_id="Clip123",
                token="token",
                client_id="client",
            ))
            self.assertIsNotNone(result)
            self.assertEqual(result["id"], "Clip123")

    def test_get_clip_processing(self):
        mock_ctx = self._mock_urlopen(200, {
            "data": []
        })
        
        with patch("bot.twitch_clips_api.urlopen", return_value=mock_ctx):
            result = asyncio.run(get_clip(
                clip_id="Clip123",
                token="token",
                client_id="client",
            ))
            self.assertIsNone(result)


class TestClipJobsRuntime(unittest.TestCase):
    def setUp(self):
        self.runtime = ClipJobsRuntime()
        self.runtime.bind_token_provider(self._fake_token)

    async def _fake_token(self):
        return "fake_token"

    def test_sync_from_queue(self):
        # Mock control_plane.list_actions
        mock_item = {
            "id": "act_123",
            "kind": "clip_candidate",
            "status": "approved",
            "payload": {
                "broadcaster_id": "999",
                "suggested_title": "Test Clip",
                "mode": "live",
            }
        }
        with patch("bot.control_plane.control_plane.list_actions", return_value={"items": [mock_item]}):
            asyncio.run(self.runtime._sync_from_queue())
            
        jobs = self.runtime.get_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["action_id"], "act_123")
        self.assertEqual(jobs[0]["status"], "queued")

    def test_handle_queued_success(self):
        job = {
            "job_id": "job_1",
            "action_id": "act_1",
            "broadcaster_id": "999",
            "mode": "live",
            "status": "queued",
        }
        self.runtime._jobs["act_1"] = job
        
        with patch("bot.clip_jobs_runtime.create_clip_live") as mock_create:
            mock_create.return_value = {"id": "ClipX", "edit_url": "http://edit"}
            
            asyncio.run(self.runtime._handle_queued(job))
            
            self.assertEqual(job["status"], "polling")
            self.assertEqual(job["twitch_clip_id"], "ClipX")

    def test_handle_polling_success(self):
        job = {
            "job_id": "job_1",
            "action_id": "act_1",
            "twitch_clip_id": "ClipX",
            "status": "polling",
            "poll_until": 9999999999.0,
            "next_poll_at": 0.0,
        }
        self.runtime._jobs["act_1"] = job
        
        with patch("bot.clip_jobs_runtime.get_clip") as mock_get:
            mock_get.return_value = {"id": "ClipX", "url": "http://final"}
            
            asyncio.run(self.runtime._handle_polling(job))
            
            self.assertEqual(job["status"], "ready")
            self.assertEqual(job["clip_url"], "http://final")


class TestAutonomyLogic(unittest.TestCase):
    def test_process_autonomy_goal_clip_candidate(self):
        goal = {
            "id": "goal_clip",
            "risk": RISK_CLIP_CANDIDATE,
            "name": "Detect Clip",
        }
        
        # Mock generate_goal_text
        with patch("bot.autonomy_logic.generate_goal_text", return_value="Um momento incrivel aconteceu"), \
             patch("bot.control_plane.control_plane.get_config", return_value={"clip_pipeline_enabled": True}), \
             patch("bot.control_plane.control_plane.enqueue_action") as mock_enqueue:
            
            mock_enqueue.return_value = {"id": "act_new"}
            
            result = asyncio.run(process_autonomy_goal(goal, None))
            
            self.assertEqual(result["outcome"], "queued")
            mock_enqueue.assert_called_once()
            _, kwargs = mock_enqueue.call_args
            self.assertEqual(kwargs["kind"], "clip_candidate")
            self.assertEqual(kwargs["payload"]["suggested_title"], "Um momento incrivel aconteceu")

    def test_process_autonomy_goal_clip_disabled(self):
        goal = {
            "id": "goal_clip",
            "risk": RISK_CLIP_CANDIDATE,
        }
        
        with patch("bot.autonomy_logic.generate_goal_text", return_value="Clip this"), \
             patch("bot.control_plane.control_plane.get_config", return_value={"clip_pipeline_enabled": False}):
            
            result = asyncio.run(process_autonomy_goal(goal, None))
            self.assertEqual(result["outcome"], "disabled")
