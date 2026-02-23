import asyncio
import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger("byte.clips.api")

HELIX_BASE = "https://api.twitch.tv/helix"


class TwitchClipError(RuntimeError):
    pass


class TwitchClipAuthError(TwitchClipError):
    pass


class TwitchClipNotFoundError(TwitchClipError):
    pass


class TwitchClipRateLimitError(TwitchClipError):
    def __init__(self, message: str, reset_at: float) -> None:
        super().__init__(message)
        self.reset_at = reset_at


def _parse_response(response: Any) -> dict[str, Any]:
    try:
        raw = response.read()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))
    except Exception as error:
        raise TwitchClipError(f"Falha ao processar resposta JSON: {error}") from error


def _handle_http_error(error: HTTPError) -> None:
    code = error.code
    if code == 401:
        raise TwitchClipAuthError("Token invalido ou expirado (401).")
    if code == 403:
        raise TwitchClipAuthError("Permissao negada (403). Verifique scopes e canal.")
    if code == 404:
        raise TwitchClipNotFoundError("Recurso nao encontrado (404).")
    if code == 429:
        reset_val = error.headers.get("Ratelimit-Reset", "")
        try:
            reset_at = float(reset_val)
        except ValueError:
            import time
            reset_at = time.time() + 10.0
        raise TwitchClipRateLimitError("Rate limit excedido (429).", reset_at)
    
    body = ""
    try:
        body = error.read().decode("utf-8")
    except Exception:
        pass
    raise TwitchClipError(f"Erro HTTP {code}: {body}")


def _create_clip_sync(
    broadcaster_id: str,
    token: str,
    client_id: str,
    title: str = "",
    duration: float = 30.0,
) -> dict[str, Any]:
    """
    POST /helix/clips — `has_delay` foi removido da API Twitch em Dez/2025.
    Parametros opcionais suportados: title, duration (5.0–60.0s).
    """
    params: dict[str, str] = {"broadcaster_id": broadcaster_id}
    if title:
        params["title"] = title
    # Clamp e envia duration se diferente do default
    clamped = max(5.0, min(60.0, float(duration)))
    if clamped != 30.0:
        params["duration"] = f"{clamped:.1f}"
    url = f"{HELIX_BASE}/clips?{urlencode(params)}"
    request = Request(url, method="POST")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Client-Id", client_id)

    try:
        with urlopen(request, timeout=10.0) as response:
            if response.status != 202:
                raise TwitchClipError(f"Status inesperado no create_clip: {response.status}")
            payload = _parse_response(response)
            data = payload.get("data", [])
            if not data:
                raise TwitchClipError("Resposta de create_clip sem dados.")
            return data[0]
    except HTTPError as error:
        _handle_http_error(error)
        raise  # Should be unreachable
    except URLError as error:
        raise TwitchClipError(f"Erro de rede ao criar clip: {error}") from error


def _get_clip_sync(clip_id: str, token: str, client_id: str) -> dict[str, Any] | None:
    params = {"id": clip_id}
    url = f"{HELIX_BASE}/clips?{urlencode(params)}"
    request = Request(url, method="GET")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Client-Id", client_id)

    try:
        with urlopen(request, timeout=10.0) as response:
            payload = _parse_response(response)
            data = payload.get("data", [])
            if not data:
                return None
            return data[0]
    except HTTPError as error:
        if error.code == 404:
            return None
        _handle_http_error(error)
        raise
    except URLError as error:
        raise TwitchClipError(f"Erro de rede ao buscar clip: {error}") from error


async def create_clip_live(
    *,
    broadcaster_id: str,
    token: str,
    client_id: str,
    title: str = "",
    duration: float = 30.0,
) -> dict[str, Any]:
    """
    Cria um clip live via POST /helix/clips.
    Retorna dict com 'id' e 'edit_url'.
    has_delay foi removido da API Twitch em Dez/2025.
    """
    return await asyncio.to_thread(
        _create_clip_sync,
        broadcaster_id,
        token,
        client_id,
        title,
        duration,
    )


async def create_clip_from_vod(
    *,
    broadcaster_id: str,
    editor_id: str,
    vod_id: str,
    vod_offset: int,
    duration: int,
    token: str,
    client_id: str,
    title: str = "",
) -> dict[str, Any]:
    """
    Cria um clip a partir de um VOD via POST /helix/videos/clips.
    Token deve ter scope 'editor:manage:clips' ou 'channel:manage:clips'.
    editor_id e obrigatorio pela API oficial.
    """
    return await asyncio.to_thread(
        _create_clip_from_vod_sync,
        broadcaster_id=broadcaster_id,
        editor_id=editor_id,
        vod_id=vod_id,
        vod_offset=vod_offset,
        duration=duration,
        token=token,
        client_id=client_id,
        title=title,
    )


async def get_clip(
    *,
    clip_id: str,
    token: str,
    client_id: str,
) -> dict[str, Any] | None:
    """
    Busca metadados do clip. Retorna None se nao encontrado ou processando (empty list).
    Nota: A API retorna lista vazia enquanto processa, entao None pode significar
    'nao existe' OU 'ainda processando' dependendo do contexto.
    Para polling de criacao, tratar None como 'ainda nao pronto' (dentro da janela de 15s).
    """
    return await asyncio.to_thread(_get_clip_sync, clip_id, token, client_id)


async def get_clip_download_url(
    *,
    clip_id: str,
    token: str,
    client_id: str,
    broadcaster_id: str,
    editor_id: str,
) -> str | None:
    """
    Busca URL de download via GET /helix/clips/downloads.
    Token deve ter scope 'editor:manage:clips' ou 'channel:manage:clips'.
    Rate limit especifico: 100 req/min.
    Retorna a URL ou None se nao disponivel.
    """
    return await asyncio.to_thread(
        _get_clip_download_url_sync,
        clip_id=clip_id,
        token=token,
        client_id=client_id,
        broadcaster_id=broadcaster_id,
        editor_id=editor_id,
    )


def _create_clip_from_vod_sync(
    broadcaster_id: str,
    editor_id: str,
    vod_id: str,
    vod_offset: int,
    duration: int,
    token: str,
    client_id: str,
    title: str,
) -> dict[str, Any]:
    if vod_offset < duration:
        raise ValueError("vod_offset deve ser maior ou igual a duration.")
    if not editor_id:
        raise ValueError("editor_id e obrigatorio para create_clip_from_vod.")

    params = {
        "broadcaster_id": broadcaster_id,
        "editor_id": editor_id,
        "video_id": vod_id,
        "vod_offset": str(vod_offset),
        "duration": str(duration),
    }
    if title:
        params["title"] = title

    url = f"{HELIX_BASE}/videos/clips?{urlencode(params)}"
    request = Request(url, method="POST")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Client-Id", client_id)

    try:
        with urlopen(request, timeout=10.0) as response:
            if response.status != 202:
                raise TwitchClipError(f"Status inesperado no create_clip_from_vod: {response.status}")
            payload = _parse_response(response)
            data = payload.get("data", [])
            if not data:
                raise TwitchClipError("Resposta de create_clip_from_vod sem dados.")
            return data[0]
    except HTTPError as error:
        _handle_http_error(error)
        raise
    except URLError as error:
        raise TwitchClipError(f"Erro de rede ao criar clip VOD: {error}") from error


def _get_clip_download_url_sync(
    clip_id: str,
    token: str,
    client_id: str,
    broadcaster_id: str,
    editor_id: str,
) -> str | None:
    """
    GET /helix/clips/downloads — retorna landscape_download_url.
    A API nao tem campo 'download_url' generico; usa landscape_download_url.
    portrait_download_url pode ser None mesmo quando landscape esta disponivel.
    """
    params = {"id": clip_id, "broadcaster_id": broadcaster_id, "editor_id": editor_id}
    url = f"{HELIX_BASE}/clips/downloads?{urlencode(params)}"
    request = Request(url, method="GET")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Client-Id", client_id)

    try:
        with urlopen(request, timeout=10.0) as response:
            payload = _parse_response(response)
            data = payload.get("data", [])
            if not data:
                return None
            # landscape_download_url e o campo correto (API Twitch Dez/2025)
            return data[0].get("landscape_download_url")
    except HTTPError as error:
        # 429 especifico para downloads
        if error.code == 429:
             reset_val = error.headers.get("Ratelimit-Reset", "")
             try:
                 reset_at = float(reset_val)
             except ValueError:
                 import time
                 reset_at = time.time() + 60.0
             raise TwitchClipRateLimitError("Rate limit de download excedido (100/min).", reset_at)
        if error.code == 404:
            return None
        _handle_http_error(error)
        raise
    except URLError as error:
        raise TwitchClipError(f"Erro de rede ao buscar download URL: {error}") from error
