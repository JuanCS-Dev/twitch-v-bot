import asyncio
import unittest
from unittest.mock import AsyncMock, PropertyMock, patch

from bot.logic_context import ContextManager
from bot.persistence_layer import persistence


class TestLogicContext(unittest.IsolatedAsyncioTestCase):
    async def test_apply_channel_config_updates_existing_context(self):
        manager = ContextManager()
        ctx = manager.get("canal_a")

        manager.apply_channel_config("canal_a", temperature=0.44, top_p=0.81)

        self.assertEqual(ctx.inference_temperature, 0.44)
        self.assertEqual(ctx.inference_top_p, 0.81)

    async def test_apply_channel_config_ignores_missing_context(self):
        manager = ContextManager()

        manager.apply_channel_config("canal_inexistente", temperature=0.5, top_p=0.9)

        self.assertNotIn("canal_inexistente", manager._contexts)

    async def test_apply_agent_notes_updates_existing_context(self):
        manager = ContextManager()
        ctx = manager.get("canal_a")

        manager.apply_agent_notes("canal_a", notes="Sem spoiler pesado.")

        self.assertEqual(ctx.agent_notes, "Sem spoiler pesado.")

    async def test_apply_agent_notes_ignores_missing_context(self):
        manager = ContextManager()

        manager.apply_agent_notes("canal_inexistente", notes="x")

        self.assertNotIn("canal_inexistente", manager._contexts)

    async def test_lazy_load_restores_channel_generation_config(self):
        manager = ContextManager()

        with (
            patch.object(
                type(persistence), "is_enabled", new_callable=PropertyMock, return_value=True
            ),
            patch.object(persistence, "load_channel_state", new_callable=AsyncMock) as mock_state,
            patch.object(
                persistence, "load_recent_history", new_callable=AsyncMock
            ) as mock_history,
            patch.object(
                persistence, "load_channel_config", new_callable=AsyncMock
            ) as mock_channel_config,
            patch.object(
                persistence, "load_agent_notes", new_callable=AsyncMock
            ) as mock_agent_notes,
        ):
            mock_state.return_value = None
            mock_history.return_value = []
            mock_channel_config.return_value = {"temperature": 0.31, "top_p": 0.67}
            mock_agent_notes.return_value = {"notes": "Priorize o contexto do host."}

            ctx = manager.get("canal_lazy")
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        self.assertEqual(ctx.inference_temperature, 0.31)
        self.assertEqual(ctx.inference_top_p, 0.67)
        self.assertEqual(ctx.agent_notes, "Priorize o contexto do host.")
