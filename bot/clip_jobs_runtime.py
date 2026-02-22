import asyncio
import logging
import threading
import time
from typing import Any, Awaitable, Callable, Optional

from bot.control_plane import control_plane
from bot.control_plane_constants import utc_iso
from bot.runtime_config import CLIENT_ID
from bot.twitch_clips_api import (
    TwitchClipAuthError,
    TwitchClipError,
    TwitchClipNotFoundError,
    TwitchClipRateLimitError,
    create_clip_live,
    get_clip,
)

logger = logging.getLogger("byte.clips.runtime")

TokenProvider = Callable[[], Awaitable[str]]


class ClipJobsRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._token_provider: Optional[TokenProvider] = None
        self._loop_task: Optional[asyncio.Task[Any]] = None
        self._running = False

    def bind_token_provider(self, provider: TokenProvider) -> None:
        with self._lock:
            self._token_provider = provider

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._running:
            return
        self._running = True
        self._loop_task = loop.create_task(self._process_loop())

    def stop(self) -> None:
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            self._loop_task = None

    def get_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            # Sort by created_at desc
            return sorted(
                self._jobs.values(),
                key=lambda x: str(x.get("created_at", "")),
                reverse=True,
            )

    async def _process_loop(self) -> None:
        logger.info("ClipJobsRuntime loop iniciado.")
        while self._running:
            try:
                await self._sync_from_queue()
                await self._advance_jobs()
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.error("Erro no loop de clips: %s", error)
            
            await asyncio.sleep(2.0)

    async def _sync_from_queue(self) -> None:
        # Get approved clip candidates
        # Note: 'control_plane.list_actions' returns a snapshot.
        actions_payload = control_plane.list_actions(status="approved", limit=20)
        items = actions_payload.get("items", [])
        
        for item in items:
            if item.get("kind") != "clip_candidate":
                continue
            
            action_id = str(item.get("id"))
            with self._lock:
                if action_id in self._jobs:
                    continue
                
                # New job
                now = time.time()
                payload = item.get("payload", {})
                job = {
                    "job_id": f"job_{action_id}",
                    "action_id": action_id,
                    "broadcaster_id": str(payload.get("broadcaster_id", "")),
                    "mode": str(payload.get("mode", "live")),
                    "status": "queued",
                    "title": str(payload.get("suggested_title", "")),
                    "created_at": utc_iso(now),
                    "updated_at": utc_iso(now),
                    "twitch_clip_id": None,
                    "edit_url": None,
                    "clip_url": None,
                    "error": None,
                    "attempts": 0,
                    "next_poll_at": 0.0,
                    "poll_until": 0.0,
                }
                self._jobs[action_id] = job
                logger.info("Novo job de clip criado: %s", job["job_id"])

    async def _advance_jobs(self) -> None:
        # Copy to avoid holding lock during async ops
        with self._lock:
            active_jobs = [
                job for job in self._jobs.values()
                if job["status"] in {"queued", "creating", "polling"}
            ]

        for job in active_jobs:
            try:
                if job["status"] == "queued":
                    await self._handle_queued(job)
                elif job["status"] == "polling":
                    await self._handle_polling(job)
            except Exception as error:
                logger.error("Erro ao processar job %s: %s", job["job_id"], error)
                self._update_job(job["action_id"], status="failed", error=str(error))

    async def _get_token(self) -> str:
        if not self._token_provider:
            raise RuntimeError("Token provider nao configurado.")
        return await self._token_provider()

    async def _handle_queued(self, job: dict[str, Any]) -> None:
        action_id = job["action_id"]
        broadcaster_id = job["broadcaster_id"]
        
        # Only live mode supported in Phase 2
        if job["mode"] != "live":
             self._update_job(action_id, status="failed", error="mode_not_supported_yet")
             return

        self._update_job(action_id, status="creating")
        
        try:
            token = await self._get_token()
            client_id = CLIENT_ID or ""
            
            # Call API
            resp = await create_clip_live(
                broadcaster_id=broadcaster_id,
                token=token,
                client_id=client_id,
                has_delay=False, # Default for now
            )
            
            clip_id = resp.get("id")
            edit_url = resp.get("edit_url")
            
            if not clip_id:
                raise TwitchClipError("API retornou sucesso mas sem ID.")
            
            now = time.time()
            self._update_job(
                action_id,
                status="polling",
                twitch_clip_id=clip_id,
                edit_url=edit_url,
                poll_until=now + 20.0, # 15s official + margin
                next_poll_at=now + 2.0,
            )
            logger.info("Clip criado na Twitch: %s. Polling...", clip_id)

        except TwitchClipAuthError as e:
            self._update_job(action_id, status="failed", error=f"auth_error: {e}")
        except TwitchClipNotFoundError as e:
            self._update_job(action_id, status="failed", error=f"not_found: {e}")
        except TwitchClipRateLimitError as e:
             # Simple backoff logic could go here, but for Phase 2 fail fast or simple retry?
             # Roadmap: "retry com backoff". But for create, it's usually one-shot.
             self._update_job(action_id, status="failed", error=f"rate_limit: {e}")
        except Exception as e:
            self._update_job(action_id, status="failed", error=str(e))

    async def _handle_polling(self, job: dict[str, Any]) -> None:
        now = time.time()
        if now < job["next_poll_at"]:
            return
        
        if now > job["poll_until"]:
            self._update_job(job["action_id"], status="failed", error="poll_timeout")
            return

        action_id = job["action_id"]
        clip_id = job["twitch_clip_id"]
        
        try:
            token = await self._get_token()
            client_id = CLIENT_ID or ""
            
            clip_data = await get_clip(
                clip_id=clip_id,
                token=token,
                client_id=client_id,
            )
            
            if clip_data:
                # Clip ready!
                clip_url = clip_data.get("url")
                self._update_job(
                    action_id,
                    status="ready",
                    clip_url=clip_url,
                )
                logger.info("Clip pronto: %s", clip_url)
            else:
                # Still processing
                self._update_job(
                    action_id,
                    next_poll_at=now + 3.0,
                )
        
        except Exception as e:
             logger.warning("Erro no polling do clip %s: %s", clip_id, e)
             self._update_job(action_id, next_poll_at=now + 3.0) # Retry poll

    def _update_job(self, action_id: str, **kwargs: Any) -> None:
        with self._lock:
            if action_id not in self._jobs:
                return
            job = self._jobs[action_id]
            job.update(kwargs)
            job["updated_at"] = utc_iso(time.time())


clip_jobs = ClipJobsRuntime()

__all__ = ["ClipJobsRuntime", "clip_jobs"]
