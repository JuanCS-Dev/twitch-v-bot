import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot import autonomy_runtime


class TestAutonomyRuntime(unittest.IsolatedAsyncioTestCase):
    async def test_bind_unbind(self):
        runtime = autonomy_runtime.AutonomyRuntime()
        loop = asyncio.get_running_loop()

        with patch.object(runtime, "_ensure_loop_task") as mock_ensure:
            runtime.bind(loop=loop, mode="irc")
            self.assertEqual(runtime._mode, "irc")
            # bind calls call_soon_threadsafe which calls _ensure_loop_task
            # Since we are in the same loop, it might not run immediately,
            # but we check if it was scheduled.

        runtime.unbind()
        self.assertIsNone(runtime._loop)
        self.assertIsNone(runtime._loop_task)

    @patch("bot.autonomy_runtime.control_plane")
    @patch("bot.autonomy_runtime.process_autonomy_goal", new_callable=AsyncMock)
    async def test_run_tick(self, mock_process, mock_cp):
        runtime = autonomy_runtime.AutonomyRuntime()
        mock_cp.consume_due_goals.return_value = ["goal1"]
        mock_process.return_value = {"status": "success"}

        result = await runtime._run_tick(force=True, reason="test")

        self.assertTrue(result["ok"])
        self.assertEqual(result["due_goals"], 1)
        mock_cp.register_tick.assert_called_with(reason="test")
        mock_process.assert_called_once_with("goal1", None)

    @patch("bot.autonomy_runtime.control_plane")
    @patch("bot.autonomy_runtime.asyncio.sleep", new_callable=AsyncMock)
    async def test_heartbeat_loop(self, mock_sleep, mock_cp):
        runtime = autonomy_runtime.AutonomyRuntime()
        loop = asyncio.get_running_loop()
        runtime.bind(loop=loop, mode="test")

        # Mock _run_tick to stop the loop after one call
        with patch.object(runtime, "_run_tick", new_callable=AsyncMock) as mock_tick:
            # We want to break the while True loop after one iteration
            # We can do this by unbinding inside the tick
            def side_effect(*args, **kwargs):
                runtime.unbind()
                return {"ok": True}

            mock_tick.side_effect = side_effect

            await runtime._heartbeat_loop()

            mock_tick.assert_called_once()
            mock_cp.set_loop_running.assert_called()

    @patch("bot.autonomy_runtime.asyncio.run_coroutine_threadsafe")
    def test_run_manual_tick_threadsafe(self, mock_run):
        runtime = autonomy_runtime.AutonomyRuntime()
        loop = MagicMock()
        loop.is_closed.return_value = False
        loop.is_running.return_value = True
        runtime._loop = loop

        mock_future = MagicMock()
        mock_future.result.return_value = {"ok": True}
        mock_run.return_value = mock_future

        result = runtime.run_manual_tick(force=True)
        self.assertTrue(result["ok"])
        mock_run.assert_called_once()
