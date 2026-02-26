"""
Suite E2E Macaco Mode — Testes adversariais anti-macaco.

Filosofia: o usuario é um macaco com um teclado. Ele vai enviar:
- Strings enormes, vazias, com unicode exotico, null bytes, XSS, SQL injection
- Payloads malformados, tipos errados, valores fora de range
- Requests concorrentes, burst, duplicados
- Emotes inexistentes, comandos invalidos, encoding quebrado
"""

import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

from bot.tests.scientific_shared import ScientificTestCase


class ScientificMacacoModeTestsMixin(ScientificTestCase):
    """Testes adversariais anti-macaco para todo o sistema."""

    # ---------------------------------------------------------------
    # SENTIMENT ENGINE — Macaco inputs
    # ---------------------------------------------------------------

    def test_macaco_sentiment_null_bytes(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        score = engine.ingest_message("default", "PogChamp\x00\x00\x00 haha")
        self.assertIsInstance(score, float)

    def test_macaco_sentiment_unicode_bomb(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        bomb = "🏴󠁧󠁢󠁳󠁣󠁴󠁿" * 100 + "👨‍👩‍👧‍👦" * 50
        score = engine.ingest_message("default", bomb)
        self.assertIsInstance(score, float)

    def test_macaco_sentiment_xss_attempt(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        xss = '<script>alert("XSS")</script>PogChamp<img src=x onerror=alert(1)>'
        score = engine.ingest_message("default", xss)
        self.assertIsInstance(score, float)
        # XSS strings are not emotes, should not crash

    def test_macaco_sentiment_sql_injection(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        sqli = "'; DROP TABLE users; -- PogChamp"
        score = engine.ingest_message("default", sqli)
        self.assertIsInstance(score, float)

    def test_macaco_sentiment_enormous_message(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        huge = "A" * 100_000
        score = engine.ingest_message("default", huge)
        self.assertEqual(score, 0.0)  # No emotes/keywords in gibberish

    def test_macaco_sentiment_only_whitespace(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        score = engine.ingest_message("default", "   \t\n\r\n   ")
        self.assertEqual(score, 0.0)

    def test_macaco_sentiment_rtl_and_mixed_bidi(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        bidi = "\u202ePogChamp\u202c مرحبا PogChamp \u200f"
        score = engine.ingest_message("default", bidi)
        self.assertIsInstance(score, float)

    def test_macaco_sentiment_concurrent_flood(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        errors = []

        def flood():
            try:
                for _ in range(500):
                    engine.ingest_message("default", "LUL KEKW PogChamp")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=flood) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [])
        scores = engine.get_scores("default", window_seconds=300)
        self.assertGreater(scores["count"], 0)

    # ---------------------------------------------------------------
    # HUD RUNTIME — Macaco inputs
    # ---------------------------------------------------------------

    def test_macaco_hud_push_null_bytes(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        result = rt.push_message("Alert\x00streamer\x00now")
        self.assertTrue(result["ok"])
        self.assertIn("\x00", result["entry"]["text"])  # Should not crash

    def test_macaco_hud_push_xss(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        result = rt.push_message('<script>alert("hud")</script>')
        self.assertTrue(result["ok"])
        # Text is stored raw — XSS escaping is frontend responsibility

    def test_macaco_hud_push_enormous_text(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        huge = "X" * 10_000
        result = rt.push_message(huge)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["entry"]["text"]), 300)  # Truncated

    def test_macaco_hud_source_injection(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        result = rt.push_message("test", source='"; DROP TABLE hud; --')
        self.assertTrue(result["ok"])
        self.assertEqual(result["entry"]["source"], '"; drop table hud; --')

    def test_macaco_hud_get_messages_negative_since(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        rt.push_message("test msg")
        messages = rt.get_messages(since=-999999.0)
        self.assertEqual(len(messages), 1)  # Should not crash

    def test_macaco_hud_get_messages_future_since(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        rt.push_message("test msg")
        future = time.time() + 999999
        messages = rt.get_messages(since=future)
        self.assertEqual(len(messages), 0)

    def test_macaco_hud_concurrent_push_get(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        errors = []

        def pusher():
            try:
                for i in range(200):
                    rt.push_message(f"concurrent msg {i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(200):
                    rt.get_messages(since=0.0)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=pusher),
            threading.Thread(target=pusher),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        self.assertEqual(errors, [])

    # ---------------------------------------------------------------
    # VISION RUNTIME — Macaco inputs
    # ---------------------------------------------------------------

    def test_macaco_vision_random_bytes(self) -> None:
        from bot.vision_runtime import VisionRuntime

        rt = VisionRuntime()
        # Not a valid image, but should not crash the runtime
        result = rt.ingest_frame(b"\xde\xad\xbe\xef" * 100, mime_type="image/jpeg")
        # Should either succeed (LLM handles it) or fail gracefully
        self.assertIn("ok", result)

    def test_macaco_vision_zero_byte_after_rate_limit(self) -> None:
        from bot.vision_runtime import VisionRuntime

        rt = VisionRuntime()
        result = rt.ingest_frame(b"", mime_type="image/jpeg")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "empty_frame")

    def test_macaco_vision_wrong_mime_type(self) -> None:
        from bot.vision_runtime import VisionRuntime

        rt = VisionRuntime()
        result = rt.ingest_frame(b"\xff\xd8\xff\xe0", mime_type="application/json")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "unsupported_mime_type")

    def test_macaco_vision_mime_type_xss(self) -> None:
        from bot.vision_runtime import VisionRuntime

        rt = VisionRuntime()
        result = rt.ingest_frame(b"\xff\xd8", mime_type="<script>alert(1)</script>")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "unsupported_mime_type")

    def test_macaco_vision_exactly_max_size(self) -> None:
        from bot.vision_constants import VISION_MAX_FRAME_BYTES
        from bot.vision_runtime import VisionRuntime

        rt = VisionRuntime()
        # Exactly at the limit — should NOT be rejected
        frame = b"\xff\xd8" + b"\x00" * (VISION_MAX_FRAME_BYTES - 2)
        # But it will try to call the LLM, which we mock out
        result = rt.ingest_frame(frame, mime_type="image/jpeg")
        # Should not be "frame_too_large"
        self.assertNotEqual(result.get("reason"), "frame_too_large")

    def test_macaco_vision_one_over_max_size(self) -> None:
        from bot.vision_constants import VISION_MAX_FRAME_BYTES
        from bot.vision_runtime import VisionRuntime

        rt = VisionRuntime()
        frame = b"\x00" * (VISION_MAX_FRAME_BYTES + 1)
        result = rt.ingest_frame(frame, mime_type="image/jpeg")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "frame_too_large")

    # ---------------------------------------------------------------
    # RECAP ENGINE — Macaco inputs
    # ---------------------------------------------------------------

    def test_macaco_recap_pattern_xss(self) -> None:
        from bot.recap_engine import is_recap_prompt

        # "resumo" is inside the XSS string — pattern correctly detects keyword
        # XSS sanitization is the frontend's job, not the NLP trigger
        self.assertTrue(is_recap_prompt("<script>resumo</script>"))
        # But pure tags without keyword should NOT match
        self.assertFalse(is_recap_prompt("<script>alert(1)</script>"))

    def test_macaco_recap_pattern_empty(self) -> None:
        from bot.recap_engine import is_recap_prompt

        self.assertFalse(is_recap_prompt(""))
        self.assertFalse(is_recap_prompt("   "))

    def test_macaco_recap_pattern_unicode_lookalike(self) -> None:
        from bot.recap_engine import is_recap_prompt

        # Cyrillic "а" looks like Latin "a" — should NOT match
        self.assertFalse(is_recap_prompt("rеsumo"))  # Cyrillic "е"

    def test_macaco_recap_pattern_repeated(self) -> None:
        from bot.recap_engine import is_recap_prompt

        # Repeated valid trigger — still valid
        self.assertTrue(is_recap_prompt("resumo resumo resumo"))

    def test_macaco_recap_pattern_enormous(self) -> None:
        from bot.recap_engine import is_recap_prompt

        huge = "x" * 50_000 + " resumo " + "y" * 50_000
        # Should not hang or crash — regex on 100K string
        result = is_recap_prompt(huge)
        self.assertTrue(result)  # "resumo" is in there

    # ---------------------------------------------------------------
    # CLIP JOBS RUNTIME — Macaco inputs
    # ---------------------------------------------------------------

    def test_macaco_clips_sync_empty_queue(self) -> None:
        from bot.clip_jobs_runtime import ClipJobsRuntime

        rt = ClipJobsRuntime()
        with patch("bot.control_plane.control_plane.list_actions", return_value={"items": []}):
            self.loop.run_until_complete(rt._sync_from_queue())
        self.assertEqual(rt.get_jobs(), [])

    def test_macaco_clips_sync_malformed_payload(self) -> None:
        from bot.clip_jobs_runtime import ClipJobsRuntime

        rt = ClipJobsRuntime()
        bad_item = {
            "id": "act_bad",
            "kind": "clip_candidate",
            "status": "approved",
            "payload": None,  # Macaco sent None payload
        }
        with patch(
            "bot.control_plane.control_plane.list_actions", return_value={"items": [bad_item]}
        ):
            # Should not crash
            self.loop.run_until_complete(rt._sync_from_queue())

    def test_macaco_clips_duplicate_action_id(self) -> None:
        from bot.clip_jobs_runtime import ClipJobsRuntime

        rt = ClipJobsRuntime()
        item = {
            "id": "act_dup",
            "kind": "clip_candidate",
            "status": "approved",
            "payload": {"broadcaster_id": "999", "mode": "live"},
        }
        with patch(
            "bot.control_plane.control_plane.list_actions", return_value={"items": [item, item]}
        ):
            self.loop.run_until_complete(rt._sync_from_queue())
        # Should deduplicate
        jobs = rt.get_jobs()
        self.assertEqual(len(jobs), 1)

    # ---------------------------------------------------------------
    # DASHBOARD ROUTES — Macaco HTTP inputs
    # ---------------------------------------------------------------

    def test_macaco_hud_api_invalid_since(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        # Simulate parsing "not_a_number" as since
        try:
            since = float("not_a_number")
        except ValueError:
            since = 0.0
        messages = rt.get_messages(since=since)
        self.assertIsInstance(messages, list)

    def test_macaco_hud_api_infinity_since(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        rt.push_message("test")
        messages = rt.get_messages(since=float("inf"))
        self.assertEqual(len(messages), 0)

    def test_macaco_hud_api_nan_since(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        rt.push_message("test")
        # NaN comparisons are always False in Python
        messages = rt.get_messages(since=float("nan"))
        # NaN > cutoff is False, so all messages should be returned
        self.assertIsInstance(messages, list)

    # ---------------------------------------------------------------
    # SENTIMENT — Overflow / boundary
    # ---------------------------------------------------------------

    def test_macaco_sentiment_max_events_overflow(self) -> None:
        from bot.sentiment_constants import SENTIMENT_MAX_EVENTS
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        for i in range(SENTIMENT_MAX_EVENTS + 100):
            engine.ingest_message("default", f"PogChamp {i}")
        # deque with maxlen should auto-evict
        self.assertLessEqual(len(engine._channel_events["default"]), SENTIMENT_MAX_EVENTS)

    def test_macaco_sentiment_vibe_with_only_neutrals(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        for _ in range(20):
            engine.ingest_message("default", "oi tudo bem como vai")
        self.assertEqual(engine.get_vibe("default"), "Chill")

    # ---------------------------------------------------------------
    # CROSS-SYSTEM INTEGRATION — E2E
    # ---------------------------------------------------------------

    @patch("bot.recap_engine.agent_inference")
    def test_e2e_recap_with_sentiment_context(self, mock_inference: AsyncMock) -> None:
        from bot.recap_engine import generate_recap
        from bot.sentiment_engine import sentiment_engine

        # Ingest some messages to build vibe
        for _ in range(5):
            sentiment_engine.ingest_message("default", "HYPERS PogChamp")

        mock_inference.return_value = "Chat ta hyped demais, streamer fazendo plays insanos!"
        result = self.loop.run_until_complete(generate_recap(channel_id="default"))
        self.assertIn("hyped", result.lower())

    @patch("bot.vision_runtime.client")
    @patch("bot.vision_runtime.observability")
    def test_e2e_vision_ingest_and_clip_trigger_with_disabled_pipeline(
        self,
        mock_obs: MagicMock,
        mock_client: MagicMock,
    ) -> None:
        from bot.vision_runtime import VisionRuntime

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "PENTAKILL! Jogador massacre total!"
        mock_client.chat.completions.create.return_value = mock_response

        with patch("bot.vision_runtime.control_plane") as mock_cp:
            mock_cp.get_config.return_value = {"clip_pipeline_enabled": False}
            rt = VisionRuntime()
            result = rt.ingest_frame(b"\xff\xd8\xff\xe0", mime_type="image/jpeg")
            self.assertTrue(result["ok"])
            self.assertTrue(result["clip_trigger"])
            # But NO clip enqueued because pipeline is disabled
            mock_cp.enqueue_action.assert_not_called()

    @patch("bot.autonomy_logic.hud_runtime")
    @patch("bot.autonomy_logic.control_plane")
    @patch("bot.autonomy_logic.observability")
    def test_e2e_suggest_streamer_pushes_to_hud_and_queue(
        self,
        mock_obs: MagicMock,
        mock_cp: MagicMock,
        mock_hud: MagicMock,
    ) -> None:
        from bot.autonomy_logic import _handle_generic_suggestion
        from bot.control_plane_constants import RISK_SUGGEST_STREAMER

        mock_cp.enqueue_action.return_value = {"id": "act_e2e"}
        result = _handle_generic_suggestion(
            goal_id="e2e_goal",
            risk=RISK_SUGGEST_STREAMER,
            goal_name="E2E Test",
            prompt="test prompt",
            text="Sugestão de teste E2E",
        )
        self.assertEqual(result["outcome"], "queued")
        mock_cp.enqueue_action.assert_called_once()
        mock_hud.push_message.assert_called_once_with("Sugestão de teste E2E", source="autonomy")

    def test_e2e_sentiment_score_emote_keyword_combined(self) -> None:
        from bot.sentiment_engine import _score_message

        # PogChamp (+2.0) + "incrivel" (+1.0) + "gg" (+1.0) = +4.0
        score = _score_message("PogChamp gg incrivel demais")
        self.assertAlmostEqual(score, 4.0, places=0)

    def test_e2e_hud_integration_full_cycle(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        # Push
        r1 = rt.push_message("Sugestão 1", source="autonomy")
        self.assertTrue(r1["ok"])
        r2 = rt.push_message("Sugestão 2", source="vision")
        self.assertTrue(r2["ok"])

        # Get all
        msgs = rt.get_messages(since=0.0)
        self.assertEqual(len(msgs), 2)

        # Get recent only
        ts_between = r1["entry"]["ts"]
        recent = rt.get_messages(since=ts_between)
        self.assertGreaterEqual(len(recent), 1)

        # Clear
        rt.clear()
        self.assertEqual(len(rt.get_messages(since=0.0)), 0)

        # Status
        status = rt.get_status()
        self.assertEqual(status["count"], 0)
