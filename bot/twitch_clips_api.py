import asyncio
import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bot.control_plane_constants import utc_iso

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
    has_delay: bool,
) -> dict[str, Any]:
    params = {"broadcaster_id": broadcaster_id, "has_delay": str(has_delay).lower()}
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
        raise # Should be unreachable
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
    has_delay: bool = False,
) -> dict[str, Any]:
    """
    Cria um clip live via POST /helix/clips.
    Retorna dict com 'id' e 'edit_url'.
    """
    return await asyncio.to_thread(
        _create_clip_sync,
        broadcaster_id,
        token,
        client_id,
        has_delay,
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
