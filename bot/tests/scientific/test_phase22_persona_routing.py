"""Scientific test suite for Phase 22: Persona Studio & Nebius Model Routing.

Tests validate behavioral contracts, NOT implementation details:
1. PersonaProfileRepository round-trip and validation
2. _select_model routing with per-channel overrides
3. _build_identity_instruction with expanded persona fields
4. PersistenceLayer facade shares cache with repository
5. ContextManager.apply_persona_profile propagation
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. PersonaProfileRepository: Memory Round-Trip & Validation
# ---------------------------------------------------------------------------
class TestPersonaProfileRepositoryRoundTrip:
    """Prove the repository normalizes, stores, and retrieves persona profiles correctly."""

    def _make_repo(self):
        from bot.persistence_persona_profile_repository import PersonaProfileRepository

        cache: dict = {}
        return PersonaProfileRepository(enabled=False, client=None, cache=cache)

    def test_save_and_load_full_profile(self):
        repo = self._make_repo()
        saved = repo.save_sync(
            "test_channel",
            base_identity={
                "name": "Byte Coach",
                "pronouns": "ele/dele",
                "lore": "Digital coaching entity",
            },
            tonality_engine={
                "tone": "tatico e direto",
                "emote_vocab": ["PogChamp", "LUL"],
                "sentence_style": "short_punchy",
            },
            behavioral_constraints={
                "banned_topics": ["politics", "religion"],
                "cta_triggers": ["follow", "subscribe"],
            },
            model_routing={
                "chat": "deepseek-r1",
                "coaching": None,
                "search": "qwen-72b",
                "reasoning": None,
            },
        )

        assert saved["has_profile"] is True
        assert saved["base_identity"]["name"] == "Byte Coach"
        assert saved["base_identity"]["pronouns"] == "ele/dele"
        assert saved["tonality_engine"]["sentence_style"] == "short_punchy"
        assert saved["behavioral_constraints"]["banned_topics"] == ["politics", "religion"]
        assert saved["model_routing"]["chat"] == "deepseek-r1"
        assert saved["model_routing"]["coaching"] is None

        loaded = repo.load_sync("test_channel")
        assert loaded["has_profile"] is True
        assert loaded["base_identity"]["name"] == "Byte Coach"
        assert loaded["tonality_engine"]["emote_vocab"] == ["PogChamp", "LUL"]
        assert loaded["model_routing"]["search"] == "qwen-72b"

    def test_empty_profile_has_profile_false(self):
        repo = self._make_repo()
        saved = repo.save_sync(
            "empty_channel",
            base_identity={},
            tonality_engine={},
            behavioral_constraints={},
            model_routing={},
        )
        assert saved["has_profile"] is False

    def test_load_before_save_returns_default(self):
        repo = self._make_repo()
        loaded = repo.load_sync("nonexistent")
        assert loaded["has_profile"] is False
        assert loaded["base_identity"] == {"name": "", "pronouns": "", "lore": ""}
        assert loaded["channel_id"] == "nonexistent"

    def test_name_length_validation(self):
        repo = self._make_repo()
        with pytest.raises(ValueError, match="tamanho"):
            repo.save_sync(
                "test_channel",
                base_identity={"name": "A" * 200},
            )

    def test_invalid_sentence_style_rejected(self):
        repo = self._make_repo()
        with pytest.raises(ValueError, match="invalido"):
            repo.save_sync(
                "test_channel",
                tonality_engine={"sentence_style": "invalid_style"},
            )

    def test_banned_topics_dedup_and_limit(self):
        repo = self._make_repo()
        saved = repo.save_sync(
            "test_channel",
            behavioral_constraints={"banned_topics": ["dup", "DUP", "unique"]},
        )
        assert saved["behavioral_constraints"]["banned_topics"] == ["dup", "unique"]


# ---------------------------------------------------------------------------
# 2. _select_model: Per-Channel Model Routing
# ---------------------------------------------------------------------------
class TestSelectModelRouting:
    """Prove model selection respects per-channel overrides when context has routing."""

    @patch("bot.runtime_config.NEBIUS_MODEL_DEFAULT", "global-default")
    @patch("bot.runtime_config.NEBIUS_MODEL_SEARCH", "global-search")
    @patch("bot.runtime_config.NEBIUS_MODEL_REASONING", "global-reasoning")
    def test_no_routing_uses_global_defaults(self):
        from bot.logic_inference import _select_model

        assert _select_model(False, False) == "global-default"
        assert _select_model(True, False) == "global-search"
        assert _select_model(False, True) == "global-reasoning"

    @patch("bot.runtime_config.NEBIUS_MODEL_DEFAULT", "global-default")
    @patch("bot.runtime_config.NEBIUS_MODEL_SEARCH", "global-search")
    @patch("bot.runtime_config.NEBIUS_MODEL_REASONING", "global-reasoning")
    def test_routing_overrides_global(self):
        from bot.logic_inference import _select_model

        ctx = SimpleNamespace(
            channel_model_routing={
                "chat": "custom-chat",
                "search": "custom-search",
                "reasoning": "custom-reasoning",
            }
        )
        assert _select_model(False, False, context=ctx) == "custom-chat"
        assert _select_model(True, False, context=ctx) == "custom-search"
        assert _select_model(False, True, context=ctx) == "custom-reasoning"

    @patch("bot.runtime_config.NEBIUS_MODEL_DEFAULT", "global-default")
    @patch("bot.runtime_config.NEBIUS_MODEL_SEARCH", "global-search")
    def test_partial_routing_falls_back_to_global(self):
        from bot.logic_inference import _select_model

        ctx = SimpleNamespace(
            channel_model_routing={
                "chat": "custom-chat",
                "search": None,
            }
        )
        assert _select_model(False, False, context=ctx) == "custom-chat"
        assert _select_model(True, False, context=ctx) == "global-search"

    @patch("bot.runtime_config.NEBIUS_MODEL_DEFAULT", "global-default")
    def test_empty_routing_dict_falls_back(self):
        from bot.logic_inference import _select_model

        ctx = SimpleNamespace(channel_model_routing={})
        assert _select_model(False, False, context=ctx) == "global-default"


# ---------------------------------------------------------------------------
# 3. _build_identity_instruction: Expanded Persona Fields
# ---------------------------------------------------------------------------
class TestBuildIdentityInstructionExpanded:
    """Prove system prompt includes sentence_style, banned_topics, and cta_triggers."""

    def test_includes_sentence_style(self):
        from bot.logic_inference import _build_identity_instruction

        ctx = SimpleNamespace(
            persona_name="Byte",
            persona_tone="tatico",
            persona_lore="",
            persona_emote_vocab=[],
            persona_sentence_style="short_punchy",
            persona_banned_topics=[],
            persona_cta_triggers=[],
        )
        result = _build_identity_instruction(ctx)
        assert "curto e direto" in result

    def test_includes_banned_topics(self):
        from bot.logic_inference import _build_identity_instruction

        ctx = SimpleNamespace(
            persona_name="Byte",
            persona_tone="",
            persona_lore="",
            persona_emote_vocab=[],
            persona_sentence_style="",
            persona_banned_topics=["politics", "religion"],
            persona_cta_triggers=[],
        )
        result = _build_identity_instruction(ctx)
        assert "NUNCA aborde" in result
        assert "politics" in result
        assert "religion" in result

    def test_includes_cta_triggers(self):
        from bot.logic_inference import _build_identity_instruction

        ctx = SimpleNamespace(
            persona_name="Byte",
            persona_tone="",
            persona_lore="",
            persona_emote_vocab=[],
            persona_sentence_style="",
            persona_banned_topics=[],
            persona_cta_triggers=["follow", "subscribe"],
        )
        result = _build_identity_instruction(ctx)
        assert "Gatilhos de CTA" in result
        assert "follow" in result

    def test_empty_fields_produce_no_noise(self):
        from bot.logic_inference import _build_identity_instruction

        ctx = SimpleNamespace(
            persona_name="Byte",
            persona_tone="",
            persona_lore="",
            persona_emote_vocab=[],
            persona_sentence_style="",
            persona_banned_topics=[],
            persona_cta_triggers=[],
        )
        result = _build_identity_instruction(ctx)
        assert "NUNCA aborde" not in result
        assert "Gatilhos de CTA" not in result
        assert "Estilo de frase" not in result

    def test_backward_compat_without_new_attrs(self):
        """Context objects without new fields should NOT break."""
        from bot.logic_inference import _build_identity_instruction

        ctx = SimpleNamespace(
            persona_name="Byte",
            persona_tone="energetico",
            persona_lore="",
            persona_emote_vocab=["PogChamp"],
        )
        result = _build_identity_instruction(ctx)
        assert "Byte" in result
        assert "energetico" in result


# ---------------------------------------------------------------------------
# 4. PersistenceLayer Facade: Cache Sharing
# ---------------------------------------------------------------------------
class TestPersistenceLayerFacade:
    """Prove the facade shares cache between save and load."""

    @patch.dict("os.environ", {"SUPABASE_URL": "", "SUPABASE_KEY": ""})
    def test_facade_save_load_shares_cache(self):
        from bot.persistence_layer import PersistenceLayer

        pl = PersistenceLayer()
        pl.save_persona_profile_sync(
            "canal_a",
            base_identity={"name": "Coach"},
            tonality_engine={"tone": "motivador"},
        )
        loaded = pl.load_persona_profile_sync("canal_a")
        assert loaded["has_profile"] is True
        assert loaded["base_identity"]["name"] == "Coach"
        assert loaded["tonality_engine"]["tone"] == "motivador"
        assert loaded["source"] == "memory"


# ---------------------------------------------------------------------------
# 5. ContextManager.apply_persona_profile
# ---------------------------------------------------------------------------
class TestContextManagerApplyPersonaProfile:
    """Prove apply_persona_profile propagates to StreamContext."""

    def test_apply_persona_profile_propagates(self):
        from bot.logic_context import ContextManager

        cm = ContextManager()
        cm.get("test_ch")

        cm.apply_persona_profile(
            "test_ch",
            base_identity={"name": "Test Persona", "lore": "Test lore"},
            tonality_engine={"tone": "fun", "emote_vocab": ["Kappa"], "sentence_style": "balanced"},
            behavioral_constraints={"banned_topics": ["spoilers"], "cta_triggers": ["sub"]},
            model_routing={"chat": "test-model", "search": None},
        )

        ctx = cm.get("test_ch")
        assert ctx.persona_name == "Test Persona"
        assert ctx.persona_lore == "Test lore"
        assert ctx.persona_tone == "fun"
        assert ctx.persona_emote_vocab == ["Kappa"]
        assert ctx.persona_sentence_style == "balanced"
        assert ctx.persona_banned_topics == ["spoilers"]
        assert ctx.persona_cta_triggers == ["sub"]
        assert ctx.channel_model_routing["chat"] == "test-model"
        assert ctx.channel_model_routing.get("search") is None

    def test_apply_to_nonexistent_channel_is_noop(self):
        from bot.logic_context import ContextManager

        cm = ContextManager()
        cm.apply_persona_profile(
            "ghost_channel",
            base_identity={"name": "Ghost"},
        )
        # Should not crash
