import unittest
from unittest.mock import MagicMock, patch

from bot.clip_jobs_store import SupabaseJobStore


class TestClipJobsStoreV2(unittest.TestCase):
    def test_get_connection_invalid_url_scheme(self):
        with patch.dict("os.environ", {"SUPABASE_DB_URL": "not-postgres://abc"}):
            store = SupabaseJobStore()
            # Should fall through to the else branch or catch exception
            with patch("bot.clip_jobs_store.psycopg2.connect", side_effect=Exception("boom")):
                conn = store._get_connection()
                self.assertIsNone(conn)

    def test_ensure_table_exception(self):
        store = SupabaseJobStore()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value.execute.side_effect = Exception(
            "db error"
        )
        # Should not crash, just log
        store._ensure_table(mock_conn)
        self.assertFalse(store._initialized)

    def test_save_job_exception(self):
        store = SupabaseJobStore()
        mock_conn = MagicMock()
        store._get_connection = MagicMock(return_value=mock_conn)
        mock_conn.cursor.return_value.__enter__.return_value.execute.side_effect = Exception(
            "save error"
        )

        store.save_job({"job_id": "1"})
        mock_conn.close.assert_called_once()

    def test_load_active_jobs_exception(self):
        store = SupabaseJobStore()
        mock_conn = MagicMock()
        store._get_connection = MagicMock(return_value=mock_conn)
        mock_conn.cursor.return_value.__enter__.return_value.execute.side_effect = Exception(
            "load error"
        )

        res = store.load_active_jobs()
        self.assertEqual(res, [])
        mock_conn.close.assert_called_once()

    def test_get_job_exception(self):
        store = SupabaseJobStore()
        mock_conn = MagicMock()
        store._get_connection = MagicMock(return_value=mock_conn)
        mock_conn.cursor.return_value.__enter__.return_value.execute.side_effect = Exception(
            "get error"
        )

        res = store.get_job("1")
        self.assertIsNone(res)
        mock_conn.close.assert_called_once()
