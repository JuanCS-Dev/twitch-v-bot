import asyncio
import unittest
from unittest.mock import AsyncMock, PropertyMock, patch

from bot.logic_context import ContextManager
from bot.persistence_layer import persistence


class TestLogicContext(unittest.IsolatedAsyncioTestCase):
    async def test_apply_channel_config_updates_existing_context(self):
        manager = ContextManager()
        ctx = manager.get("canal_a")

        manager.apply_channel_config(
            "canal_a",
            temperature=0.44,
            top_p=0.81,
            agent_paused=True,
        )

        self.assertEqual(ctx.inference_temperature, 0.44)
        self.assertEqual(ctx.inference_top_p, 0.81)
        self.assertTrue(ctx.channel_paused)
        self.assertTrue(ctx.channel_config_loaded)

    async def test_apply_channel_config_ignores_missing_context(self):
        manager = ContextManager()

        manager.apply_channel_config(
            "canal_inexistente",
            temperature=0.5,
            top_p=0.9,
            agent_paused=True,
        )

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

    async def test_apply_channel_identity_updates_existing_context(self):
        manager = ContextManager()
        ctx = manager.get("canal_a")

        manager.apply_channel_identity(
            "canal_a",
            persona_name="Byte Coach",
            tone="analitico e objetivo",
            emote_vocab=["PogChamp", " Kappa ", "", "PogChamp"],
            lore="Contexto de lore persistente.",
        )

        self.assertEqual(ctx.persona_name, "Byte Coach")
        self.assertEqual(ctx.persona_tone, "analitico e objetivo")
        self.assertEqual(ctx.persona_emote_vocab, ["PogChamp", "Kappa", "PogChamp"])
        self.assertEqual(ctx.persona_lore, "Contexto de lore persistente.")

    async def test_apply_channel_identity_ignores_missing_context(self):
        manager = ContextManager()

        manager.apply_channel_identity(
            "canal_inexistente",
            persona_name="Byte Coach",
            tone="analitico",
            emote_vocab=["LUL"],
            lore="Lore.",
        )

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
            patch.object(
                persistence, "load_channel_identity", new_callable=AsyncMock
            ) as mock_channel_identity,
        ):
            mock_state.return_value = None
            mock_history.return_value = []
            mock_channel_config.return_value = {
                "temperature": 0.31,
                "top_p": 0.67,
                "agent_paused": True,
            }
            mock_agent_notes.return_value = {"notes": "Priorize o contexto do host."}
            mock_channel_identity.return_value = {
                "persona_name": "Byte Coach",
                "tone": "analitico",
                "emote_vocab": ["PogChamp", "LUL"],
                "lore": "Lore ativo.",
            }

            ctx = manager.get("canal_lazy")
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        self.assertEqual(ctx.inference_temperature, 0.31)
        self.assertEqual(ctx.inference_top_p, 0.67)
        self.assertEqual(ctx.agent_notes, "Priorize o contexto do host.")
        self.assertEqual(ctx.persona_name, "Byte Coach")
        self.assertEqual(ctx.persona_tone, "analitico")
        self.assertEqual(ctx.persona_emote_vocab, ["PogChamp", "LUL"])
        self.assertEqual(ctx.persona_lore, "Lore ativo.")
        self.assertTrue(ctx.channel_paused)
        self.assertTrue(ctx.channel_config_loaded)

    async def test_ensure_channel_config_loaded_restores_sync_config(self):
        manager = ContextManager()

        with (
            patch.object(manager, "_trigger_lazy_load"),
            patch.object(
                type(persistence), "is_enabled", new_callable=PropertyMock, return_value=True
            ),
            patch.object(
                persistence,
                "load_channel_config_sync",
                return_value={"temperature": 0.29, "top_p": 0.71, "agent_paused": True},
            ) as mock_load_config,
            patch.object(
                persistence,
                "load_channel_identity_sync",
                return_value={
                    "persona_name": "Byte Coach",
                    "tone": "analitico",
                    "emote_vocab": ["PogChamp"],
                    "lore": "Lore ativo.",
                },
            ) as mock_load_identity,
        ):
            ctx = manager.ensure_channel_config_loaded("canal_sync")

        self.assertEqual(ctx.inference_temperature, 0.29)
        self.assertEqual(ctx.inference_top_p, 0.71)
        self.assertTrue(ctx.channel_paused)
        self.assertEqual(ctx.persona_name, "Byte Coach")
        self.assertEqual(ctx.persona_tone, "analitico")
        self.assertEqual(ctx.persona_emote_vocab, ["PogChamp"])
        self.assertEqual(ctx.persona_lore, "Lore ativo.")
        self.assertTrue(ctx.channel_config_loaded)
        mock_load_config.assert_called_once_with("canal_sync")
        mock_load_identity.assert_called_once_with("canal_sync")

    async def test_ensure_channel_config_loaded_skips_when_already_loaded(self):
        manager = ContextManager()
        with patch.object(
            type(persistence), "is_enabled", new_callable=PropertyMock, return_value=False
        ):
            ctx = manager.get("canal_sync")
        manager.apply_channel_config(
            "canal_sync",
            temperature=0.22,
            top_p=0.55,
            agent_paused=True,
        )

        with (
            patch.object(
                type(persistence), "is_enabled", new_callable=PropertyMock, return_value=True
            ),
            patch.object(persistence, "load_channel_config_sync") as mock_load_config,
            patch.object(persistence, "load_channel_identity_sync") as mock_load_identity,
        ):
            ensured = manager.ensure_channel_config_loaded("canal_sync")

        self.assertIs(ensured, ctx)
        self.assertEqual(ensured.inference_temperature, 0.22)
        self.assertEqual(ensured.inference_top_p, 0.55)
        self.assertTrue(ensured.channel_paused)
        mock_load_config.assert_not_called()
        mock_load_identity.assert_not_called()
