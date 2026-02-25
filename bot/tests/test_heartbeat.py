import unittest
from unittest.mock import patch, MagicMock
import os
import threading
import time
import bot.heartbeat as heartbeat

class TestHeartbeat(unittest.TestCase):
    def test_heartbeat_loop_stops(self):
        """Should terminate when stop_event is set."""
        stop_event = threading.Event()
        stop_event.set()
        
        with patch("http.client.HTTPConnection") as mock_conn:
            heartbeat._heartbeat_loop(stop_event)
            # Should exit immediately without calling connection
            mock_conn.assert_not_called()

    @patch("http.client.HTTPConnection")
    def test_heartbeat_loop_execution(self, mock_conn_class):
        """Should attempt connection and log status."""
        stop_event = threading.Event()
        
        # Mock connection and response
        mock_conn = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_conn.getresponse.return_value = mock_resp
        mock_conn_class.return_value = mock_conn
        
        # Run one iteration and stop
        def side_effect(*args, **kwargs):
            stop_event.set()
            return MagicMock()

        # We'll use a thread to run it and then set the event
        t = threading.Thread(target=heartbeat._heartbeat_loop, args=(stop_event,))
        t.start()
        time.sleep(0.2)
        stop_event.set()
        t.join(timeout=1)
        
        self.assertTrue(mock_conn_class.called)

    @patch("http.client.HTTPConnection")
    def test_heartbeat_handles_failure(self, mock_conn_class):
        """Should not crash if connection fails."""
        mock_conn_class.side_effect = Exception("Network down")
        stop_event = threading.Event()
        
        # Run and stop
        t = threading.Thread(target=heartbeat._heartbeat_loop, args=(stop_event,))
        t.start()
        time.sleep(0.2)
        stop_event.set()
        t.join(timeout=1)
        
        self.assertTrue(mock_conn_class.called)

    def test_start_heartbeat(self):
        """Should return thread and event."""
        with patch("threading.Thread") as mock_thread_class:
            mock_thread = MagicMock()
            mock_thread_class.return_value = mock_thread
            
            thread, stop_event = heartbeat.start_heartbeat()
            
            self.assertEqual(thread, mock_thread)
            self.assertIsInstance(stop_event, threading.Event)
            mock_thread.start.assert_called_once()
            
            # Cleanup for the mock
            stop_event.set()
