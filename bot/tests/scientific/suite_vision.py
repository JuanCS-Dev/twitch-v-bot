from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from bot.tests.scientific_shared import ScientificTestCase


class ScientificVisionTestsMixin:
    """Testes cientificos para VisionRuntime (Fase 6)."""

    def test_vision_ingest_empty_frame(self: ScientificTestCase) -> None:
        from bot.vision_runtime import VisionRuntime

        rt = VisionRuntime()
        result = rt.ingest_frame(b"")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "empty_frame")

    def test_vision_ingest_oversized_frame(self: ScientificTestCase) -> None:
        from bot.vision_runtime import VisionRuntime

        rt = VisionRuntime()
        huge = b"\x00" * (20 * 1024 * 1024 + 1)
        result = rt.ingest_frame(huge)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "frame_too_large")

    def test_vision_ingest_unsupported_mime(self: ScientificTestCase) -> None:
        from bot.vision_runtime import VisionRuntime

        rt = VisionRuntime()
        result = rt.ingest_frame(b"\xff\xd8\xff", mime_type="image/gif")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "unsupported_mime_type")

    def test_vision_rate_limit(self: ScientificTestCase) -> None:
        from bot.vision_runtime import VisionRuntime

        rt = VisionRuntime()
        # Simulate a recent ingest
        rt._last_ingest_at = 999999999999.0
        result = rt.ingest_frame(b"\xff\xd8\xff")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "rate_limited")
        self.assertIn("retry_after_seconds", result)

    def test_vision_clip_detection_keywords(self: ScientificTestCase) -> None:
        from bot.vision_runtime import _detect_clip_trigger

        self.assertTrue(_detect_clip_trigger("O jogador fez um pentakill incrivel!"))
        self.assertTrue(_detect_clip_trigger("Morte epica do boss no ultimo segundo"))
        self.assertTrue(_detect_clip_trigger("Vitoria confirmada apos 40 minutos"))
        self.assertFalse(_detect_clip_trigger("CENA_NORMAL"))
        self.assertFalse(_detect_clip_trigger("Tela de loading do jogo"))

    def test_vision_clip_detection_case_insensitive(self: ScientificTestCase) -> None:
        from bot.vision_runtime import _detect_clip_trigger

        self.assertTrue(_detect_clip_trigger("PENTAKILL no meio do teamfight"))
        self.assertTrue(_detect_clip_trigger("VICTORY ROYALE"))

    @patch("bot.vision_runtime.client")
    @patch("bot.vision_runtime.observability")
    def test_vision_ingest_success_normal_scene(
        self: ScientificTestCase, mock_obs: MagicMock, mock_client: MagicMock
    ) -> None:
        from bot.vision_runtime import VisionRuntime

        mock_response = SimpleNamespace(text="CENA_NORMAL")
        mock_client.models.generate_content.return_value = mock_response

        rt = VisionRuntime()
        result = rt.ingest_frame(b"\xff\xd8\xff\xe0", mime_type="image/jpeg")
        self.assertTrue(result["ok"])
        self.assertFalse(result["clip_trigger"])
        self.assertEqual(result["analysis"], "CENA_NORMAL")
        mock_obs.record_vision_frame.assert_called_once()

    @patch("bot.vision_runtime.control_plane")
    @patch("bot.vision_runtime.client")
    @patch("bot.vision_runtime.observability")
    def test_vision_ingest_clip_trigger(
        self: ScientificTestCase,
        mock_obs: MagicMock,
        mock_client: MagicMock,
        mock_cp: MagicMock,
    ) -> None:
        from bot.vision_runtime import VisionRuntime

        mock_response = SimpleNamespace(text="Pentakill incrivel do mid laner!")
        mock_client.models.generate_content.return_value = mock_response
        mock_cp.get_config.return_value = {
            "clip_pipeline_enabled": True,
            "clip_mode_default": "live",
        }

        rt = VisionRuntime()
        result = rt.ingest_frame(b"\xff\xd8\xff\xe0", mime_type="image/jpeg")
        self.assertTrue(result["ok"])
        self.assertTrue(result["clip_trigger"])
        mock_cp.enqueue_action.assert_called_once()
        call_kwargs = mock_cp.enqueue_action.call_args[1]
        self.assertEqual(call_kwargs["kind"], "clip_candidate")
        self.assertEqual(call_kwargs["created_by"], "vision")

    @patch("bot.vision_runtime.control_plane")
    @patch("bot.vision_runtime.client")
    @patch("bot.vision_runtime.observability")
    def test_vision_clip_not_enqueued_when_pipeline_disabled(
        self: ScientificTestCase,
        mock_obs: MagicMock,
        mock_client: MagicMock,
        mock_cp: MagicMock,
    ) -> None:
        from bot.vision_runtime import VisionRuntime

        mock_response = SimpleNamespace(text="Pentakill!")
        mock_client.models.generate_content.return_value = mock_response
        mock_cp.get_config.return_value = {"clip_pipeline_enabled": False}

        rt = VisionRuntime()
        result = rt.ingest_frame(b"\xff\xd8\xff\xe0", mime_type="image/jpeg")
        self.assertTrue(result["ok"])
        self.assertTrue(result["clip_trigger"])
        mock_cp.enqueue_action.assert_not_called()

    @patch("bot.vision_runtime.client")
    @patch("bot.vision_runtime.observability")
    def test_vision_inference_error_handled(
        self: ScientificTestCase, mock_obs: MagicMock, mock_client: MagicMock
    ) -> None:
        from bot.vision_runtime import VisionRuntime

        mock_client.models.generate_content.side_effect = RuntimeError("API down")

        rt = VisionRuntime()
        result = rt.ingest_frame(b"\xff\xd8\xff\xe0", mime_type="image/jpeg")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "inference_error")
        mock_obs.record_error.assert_called_once()

    def test_vision_get_status_initial(self: ScientificTestCase) -> None:
        from bot.vision_runtime import VisionRuntime

        rt = VisionRuntime()
        status = rt.get_status()
        self.assertEqual(status["frame_count"], 0)
        self.assertEqual(status["last_analysis"], "")
