import logging
import threading
import time
from typing import Any

from google.genai import types  # pyright: ignore[reportMissingImports]

from bot.control_plane import RISK_CLIP_CANDIDATE, control_plane
from bot.control_plane_constants import utc_iso
from bot.logic import context
from bot.observability import observability
from bot.runtime_config import CHANNEL_ID, client
from bot.vision_constants import (
    VISION_CLIP_KEYWORDS,
    VISION_MAX_FRAME_BYTES,
    VISION_MIN_INTERVAL_SECONDS,
    VISION_MODEL_NAME,
    VISION_SCENE_PROMPT,
)

logger = logging.getLogger("byte.vision")


def _detect_clip_trigger(analysis: str) -> bool:
    lower = analysis.lower()
    if "cena_normal" in lower:
        return False
    return any(kw in lower for kw in VISION_CLIP_KEYWORDS)


class VisionRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_ingest_at: float = 0.0
        self._frame_count: int = 0
        self._last_analysis: str = ""

    def ingest_frame(
        self,
        frame_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            elapsed = now - self._last_ingest_at
            if elapsed < VISION_MIN_INTERVAL_SECONDS:
                return {
                    "ok": False,
                    "reason": "rate_limited",
                    "retry_after_seconds": round(VISION_MIN_INTERVAL_SECONDS - elapsed, 1),
                }

        if not frame_bytes:
            return {"ok": False, "reason": "empty_frame"}

        if len(frame_bytes) > VISION_MAX_FRAME_BYTES:
            return {"ok": False, "reason": "frame_too_large", "max_bytes": VISION_MAX_FRAME_BYTES}

        if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
            return {"ok": False, "reason": "unsupported_mime_type", "mime_type": mime_type}

        with self._lock:
            self._last_ingest_at = now
            self._frame_count += 1

        try:
            analysis = self._analyze_frame(frame_bytes, mime_type)
        except Exception as error:
            logger.error("Erro na analise de frame: %s", error)
            observability.record_error(category="vision_inference", details=str(error))
            return {"ok": False, "reason": "inference_error", "error": str(error)}

        with self._lock:
            self._last_analysis = analysis

        is_clip_worthy = _detect_clip_trigger(analysis)

        if is_clip_worthy:
            self._enqueue_visual_clip(analysis, now)

        if "cena_normal" not in analysis.lower():
            context.update_content("game", analysis[:220])

        observability.record_vision_frame(analysis=analysis)

        return {
            "ok": True,
            "analysis": analysis,
            "clip_trigger": is_clip_worthy,
            "frame_number": self._frame_count,
        }

    def _analyze_frame(self, frame_bytes: bytes, mime_type: str) -> str:
        config = types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=200,
            thinking_config=types.ThinkingConfig(
                include_thoughts=False,
                thinking_level=types.ThinkingLevel.MINIMAL,
            ),
        )
        response = client.models.generate_content(
            model=VISION_MODEL_NAME,
            contents=[
                types.Part(inline_data=types.Blob(
                    mime_type=mime_type,
                    data=frame_bytes,
                )),
                VISION_SCENE_PROMPT,
            ],
            config=config,
        )
        text = ""
        if hasattr(response, "text"):
            text = str(response.text or "")
        if not text and hasattr(response, "candidates"):
            candidates = response.candidates or []
            if candidates:
                parts = getattr(candidates[0], "content", None)
                if parts and hasattr(parts, "parts"):
                    text = "".join(str(getattr(p, "text", "")) for p in parts.parts)
        return text.strip()

    def _enqueue_visual_clip(self, analysis: str, now: float) -> None:
        cfg = control_plane.get_config()
        if not cfg.get("clip_pipeline_enabled"):
            return

        candidate_payload = {
            "candidate_id": f"vision_{int(now)}",
            "broadcaster_id": str(CHANNEL_ID),
            "mode": str(cfg.get("clip_mode_default", "live")),
            "suggested_duration": 30.0,
            "suggested_title": analysis[:100],
            "source": "vision_trigger",
            "source_ts": utc_iso(now),
            "context_excerpt": analysis,
            "dedupe_key": f"vision_{int(now / 60)}",
        }
        control_plane.enqueue_action(
            kind="clip_candidate",
            risk=RISK_CLIP_CANDIDATE,
            title=f"Visual Clip Trigger",
            body=analysis,
            payload=candidate_payload,
            created_by="vision",
        )
        logger.info("Clip candidate visual enfileirado: %s", analysis[:60])

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "frame_count": self._frame_count,
                "last_ingest_at": self._last_ingest_at,
                "last_analysis": self._last_analysis,
            }


vision_runtime = VisionRuntime()

__all__ = ["VisionRuntime", "vision_runtime"]
