import asyncio
import unittest
import time
from unittest.mock import MagicMock, patch

from bot.clip_jobs_runtime import ClipJobsRuntime
from bot.clip_jobs_store import SupabaseJobStore
from bot.twitch_clips_api import TwitchClipRateLimitError

class TestClipJobsFix(unittest.TestCase):
    def setUp(self):
        # Desabilita o init real do Firestore para os testes de store
        with patch("bot.clip_jobs_store.os.environ.get", return_value=None):
            self.store = SupabaseJobStore()
        
        # Setup do runtime com mocks
        self.runtime = ClipJobsRuntime()
        self.runtime.bind_token_provider(self._fake_token)

    async def _fake_token(self):
        return "fake_token"

    def test_store_load_active_jobs_queries_ready_incomplete(self):
        """Valida que o store faz a query psycopg2 extraindo os jobs"""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        # Documentos simulados
        job_active = {"job_id": "j_active", "status": "queued"}
        job_ready = {"job_id": "j_ready_inc", "status": "ready", "download_url": None}
        mock_cur.fetchall.return_value = [job_active, job_ready]
        
        with patch.object(self.store, "_get_connection", return_value=mock_conn):
            jobs = self.store.load_active_jobs()
            
            self.assertEqual(len(jobs), 2)
            self.assertEqual(jobs[0]["job_id"], "j_active")
            self.assertEqual(jobs[1]["job_id"], "j_ready_inc")
            self.assertEqual(mock_cur.execute.call_count, 1)

    def test_runtime_download_fetch_cooldown(self):
        """Valida que o runtime respeita o cooldown de download_poll."""
        job = {
            "job_id": "job_cooldown",
            "action_id": "act_cooldown",
            "broadcaster_id": "999",
            "status": "ready",
            "twitch_clip_id": "ClipX",
            "download_url": None,
            "next_download_poll_at": time.time() + 100.0 # No futuro
        }
        self.runtime._jobs["act_cooldown"] = job
        
        with patch("bot.clip_jobs_runtime.get_clip_download_url") as mock_dl:
            asyncio.run(self.runtime._handle_download_fetch(job))
            # Nao deve ser chamado devido ao cooldown
            mock_dl.assert_not_called()

    def test_runtime_download_fetch_rate_limit_reset(self):
        """Valida que o runtime respeita o reset_at do erro de rate limit."""
        now = time.time()
        job = {
            "job_id": "job_rl",
            "action_id": "act_rl",
            "broadcaster_id": "999",
            "status": "ready",
            "twitch_clip_id": "ClipX",
            "download_url": None,
            "next_download_poll_at": 0 # Pode tentar
        }
        self.runtime._jobs["act_rl"] = job
        
        future_reset = now + 300.0
        error = TwitchClipRateLimitError("Limit", reset_at=future_reset)
        
        with patch("bot.clip_jobs_runtime.get_clip_download_url", side_effect=error):
            asyncio.run(self.runtime._handle_download_fetch(job))
            
            # Deve ter atualizado o next_download_poll_at para o future_reset
            self.assertEqual(job["next_download_poll_at"], future_reset)

if __name__ == "__main__":
    unittest.main()
