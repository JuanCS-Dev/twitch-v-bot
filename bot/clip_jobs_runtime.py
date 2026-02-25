import asyncio
import logging
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

from bot.clip_jobs_store import job_store
from bot.control_plane import control_plane
from bot.control_plane_constants import utc_iso
from bot.runtime_config import CLIENT_ID, EDITOR_ID
from bot.twitch_clips_api import (
    TwitchClipAuthError,
    TwitchClipError,
    TwitchClipNotFoundError,
    TwitchClipRateLimitError,
    create_clip_from_vod,
    create_clip_live,
    get_clip,
    get_clip_download_url,
)

logger = logging.getLogger("byte.clips.runtime")

TokenProvider = Callable[[], Awaitable[str]]


class ClipJobsRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._token_provider: TokenProvider | None = None
        self._loop_task: asyncio.Task[Any] | None = None
        self._running = False

        # Hydrate from store
        self._load_from_store()

    def _load_from_store(self) -> None:
        try:
            active_jobs = job_store.load_active_jobs()
            for job in active_jobs:
                action_id = str(job.get("action_id"))
                if action_id:
                    self._jobs[action_id] = job
        except Exception as e:
            logger.error("Erro ao hidratar jobs do store: %s", e)

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
        actions_payload = control_plane.list_actions(status="approved", limit=20)
        items = actions_payload.get("items", [])

        for item in items:
            if item.get("kind") != "clip_candidate":
                continue

            action_id = str(item.get("id"))
            with self._lock:
                if action_id in self._jobs:
                    continue

                now = time.time()
                payload = item.get("payload") or {}
                job = {
                    "job_id": f"job_{action_id}",
                    "action_id": action_id,
                    "broadcaster_id": str(payload.get("broadcaster_id", "")),
                    "mode": str(payload.get("mode", "live")),
                    "status": "queued",
                    "title": str(payload.get("suggested_title", "")),
                    # Persist VOD params if present
                    "vod_id": payload.get("vod_id"),
                    "vod_offset": payload.get("vod_offset"),
                    "duration": payload.get("suggested_duration"),
                    "created_at": utc_iso(now),
                    "updated_at": utc_iso(now),
                    "twitch_clip_id": None,
                    "edit_url": None,
                    "clip_url": None,
                    "download_url": None,
                    "error": None,
                    "attempts": 0,
                    "next_poll_at": 0.0,
                    "poll_until": 0.0,
                    "next_download_poll_at": 0.0,
                }
                self._jobs[action_id] = job
                job_store.save_job(job)
                logger.info("Novo job de clip criado: %s", job["job_id"])

    async def _advance_jobs(self) -> None:
        with self._lock:
            active_jobs = [
                job
                for job in self._jobs.values()
                if job["status"] in {"queued", "creating", "polling", "ready"}
                and not (
                    job["status"] == "ready" and job.get("download_url")
                )  # Keep processing ready jobs until download URL fetched
            ]

        for job in active_jobs:
            try:
                if job["status"] == "queued":
                    await self._handle_queued(job)
                elif job["status"] == "polling":
                    await self._handle_polling(job)
                elif job["status"] == "ready" and not job.get("download_url"):
                    await self._handle_download_fetch(job)
            except Exception as error:
                logger.error("Erro ao processar job %s: %s", job["job_id"], error)
                if (
                    job["status"] != "ready"
                ):  # Don't fail a ready job just because download fetch failed
                    self._update_job(job["action_id"], status="failed", error=str(error))

    async def _get_token(self) -> str:
        if not self._token_provider:
            raise RuntimeError("Token provider nao configurado.")
        return await self._token_provider()

    async def _handle_queued(self, job: dict[str, Any]) -> None:
        action_id = job["action_id"]
        broadcaster_id = job["broadcaster_id"]
        mode = job["mode"]

        self._update_job(action_id, status="creating")

        try:
            token = await self._get_token()
            client_id = CLIENT_ID or ""

            resp = {}
            if mode == "live":
                resp = await create_clip_live(
                    broadcaster_id=broadcaster_id,
                    token=token,
                    client_id=client_id,
                    title=job.get("title", ""),
                    duration=float(job.get("duration") or 30.0),
                )
            elif mode == "vod":
                vod_id = job.get("vod_id")
                vod_offset = job.get("vod_offset")
                duration = job.get("duration", 30)
                title = job.get("title", "")

                if not vod_id or not vod_offset:
                    raise ValueError("Dados de VOD ausentes no job.")

                resp = await create_clip_from_vod(
                    broadcaster_id=broadcaster_id,
                    editor_id=EDITOR_ID or "",
                    vod_id=vod_id,
                    vod_offset=int(vod_offset),
                    duration=int(duration),
                    token=token,
                    client_id=client_id,
                    title=title,
                )
            else:
                self._update_job(action_id, status="failed", error=f"mode_not_supported: {mode}")
                return

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
                poll_until=now + 20.0,
                next_poll_at=now + 2.0,
            )
            logger.info("Clip criado na Twitch (%s): %s. Polling...", mode, clip_id)

        except TwitchClipAuthError as e:
            self._update_job(action_id, status="failed", error=f"auth_error: {e}")
        except TwitchClipNotFoundError as e:
            self._update_job(action_id, status="failed", error=f"not_found: {e}")
        except TwitchClipRateLimitError as e:
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
                clip_url = clip_data.get("url")
                self._update_job(
                    action_id,
                    status="ready",
                    clip_url=clip_url,
                )
                logger.info("Clip pronto: %s", clip_url)
            else:
                self._update_job(
                    action_id,
                    next_poll_at=now + 3.0,
                )

        except Exception as e:
            logger.warning("Erro no polling do clip %s: %s", clip_id, e)
            self._update_job(action_id, next_poll_at=now + 3.0)

    async def _handle_download_fetch(self, job: dict[str, Any]) -> None:
        # Tenta buscar a URL de download para jobs 'ready'
        # Isso é um "best effort" e pode falhar por rate limit
        action_id = job["action_id"]
        clip_id = job["twitch_clip_id"]
        broadcaster_id = job["broadcaster_id"]

        now = time.time()
        if now < job.get("next_download_poll_at", 0):
            return

        try:
            token = await self._get_token()
            client_id = CLIENT_ID or ""

            url = await get_clip_download_url(
                clip_id=clip_id,
                token=token,
                client_id=client_id,
                broadcaster_id=broadcaster_id,
                editor_id=EDITOR_ID or "",
            )

            if url:
                self._update_job(action_id, download_url=url)
                logger.info("Download URL obtida para clip %s", clip_id)
            else:
                # Nao disponivel ainda, tenta novamente em 60s
                self._update_job(action_id, next_download_poll_at=now + 60.0)

        except TwitchClipRateLimitError as e:
            # Respeita o reset do rate limit se fornecido, senao espera 60s
            wait_until = getattr(e, "reset_at", now + 60.0)
            self._update_job(action_id, next_download_poll_at=wait_until)
            logger.warning(
                "Rate limit atingido para download do clip %s. Retentando em %ds",
                clip_id,
                int(wait_until - now),
            )
        except Exception as e:
            logger.warning("Falha ao buscar download URL para %s: %s", clip_id, e)
            # Espera um pouco antes de tentar novamente em caso de erro generico
            self._update_job(action_id, next_download_poll_at=now + 120.0)

    def _update_job(self, action_id: str, **kwargs: Any) -> None:
        with self._lock:
            if action_id not in self._jobs:
                return
            job = self._jobs[action_id]
            job.update(kwargs)
            job["updated_at"] = utc_iso(time.time())

            # Persist async-ish (fire and forget for now, store handles errors)
            job_store.save_job(job)


clip_jobs = ClipJobsRuntime()

__all__ = ["ClipJobsRuntime", "clip_jobs"]
