import unittest
from unittest.mock import patch, MagicMock
import bot.clip_jobs_store as clip_store

class TestClipJobsStore(unittest.TestCase):
    def setUp(self):
        # Reset initialized state and set a dummy URL
        clip_store.job_store._initialized = False
        clip_store.job_store._db_url = "postgres://fake"

    @patch("psycopg2.connect")
    def test_get_connection_success(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # Invalidate initialized to force ensure_table
        clip_store.job_store._initialized = False
        conn = clip_store.job_store._get_connection()
        self.assertEqual(conn, mock_conn)
        mock_connect.assert_called()

    @patch("bot.clip_jobs_store.SupabaseJobStore._get_connection")
    def test_save_job(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        
        job = {"job_id": "123", "status": "queued", "extra": "data"}
        clip_store.job_store.save_job(job)
        
        mock_conn.cursor().__enter__().execute.assert_called()
        mock_conn.commit.assert_called()
        mock_conn.close.assert_called()

    @patch("bot.clip_jobs_store.SupabaseJobStore._get_connection")
    def test_load_active_jobs(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_cursor = mock_conn.cursor().__enter__()
        
        mock_cursor.fetchall.return_value = [
            {"job_id": "1", "status": "queued", "metadata": {"foo": "bar"}}
        ]
        
        jobs = clip_store.job_store.load_active_jobs()
        self.assertEqual(len(jobs), 1)
        # Note: metadata is merged back in load_active_jobs
        self.assertEqual(jobs[0]["foo"], "bar")

    def test_offline_mode(self):
        # Temporarily clear URL
        old_url = clip_store.job_store._db_url
        clip_store.job_store._db_url = None
        try:
            self.assertIsNone(clip_store.job_store._get_connection())
            # Should not crash
            clip_store.job_store.save_job({"id": 1})
            self.assertEqual(clip_store.job_store.load_active_jobs(), [])
        finally:
            clip_store.job_store._db_url = old_url
