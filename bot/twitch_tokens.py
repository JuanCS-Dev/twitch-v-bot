import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def is_irc_auth_failure_line(line: str) -> bool:
    lowered_line = (line or "").lower()
    return "login authentication failed" in lowered_line or "improperly formatted auth" in lowered_line


class TwitchAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class TwitchTokenManagerSettings:
    validate_endpoint: str = "https://id.twitch.tv/oauth2/validate"
    refresh_endpoint: str = "https://id.twitch.tv/oauth2/token"
    validate_timeout_seconds: float = 5.0
    refresh_timeout_seconds: float = 8.0


class TwitchTokenManager:
    def __init__(
        self,
        *,
        access_token: str,
        refresh_token: str = "",
        client_id: str = "",
        client_secret: str = "",
        refresh_margin_seconds: int = 300,
        settings: TwitchTokenManagerSettings | None = None,
        observability: Any | None = None,
        logger: Any | None = None,
        urlopen_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.access_token = access_token.strip().removeprefix("oauth:")
        self.refresh_token = refresh_token.strip()
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.refresh_margin_seconds = max(30, int(refresh_margin_seconds))
        self.settings = settings or TwitchTokenManagerSettings()
        self.observability = observability
        self.logger = logger
        self.urlopen_fn = urlopen_fn or urlopen
        self.expires_at_monotonic: float | None = None
        self.validated_once = False

    @property
    def can_refresh(self) -> bool:
        return bool(self.refresh_token and self.client_id and self.client_secret)

    def _set_expiration(self, expires_in: int | float | str | None) -> None:
        if expires_in is None:
            self.expires_at_monotonic = None
            return
        try:
            expiry_seconds = float(expires_in)
        except (TypeError, ValueError):
            self.expires_at_monotonic = None
            return
        self.expires_at_monotonic = time.monotonic() + max(expiry_seconds, 0.0)

    def _is_expiring_soon(self) -> bool:
        if self.expires_at_monotonic is None:
            return False
        return time.monotonic() >= (self.expires_at_monotonic - self.refresh_margin_seconds)

    def _validate_token_sync(self) -> dict | None:
        request = Request(
            self.settings.validate_endpoint,
            headers={"Authorization": f"OAuth {self.access_token}"},
        )
        try:
            with self.urlopen_fn(request, timeout=self.settings.validate_timeout_seconds) as response:
                if response.status != 200:
                    return None
                payload = response.read()
        except HTTPError as error:
            if error.code in {400, 401}:
                return None
            raise TwitchAuthError(f"Falha ao validar token Twitch (HTTP {error.code}).") from error
        except (URLError, TimeoutError, ValueError) as error:
            raise TwitchAuthError(f"Falha de rede ao validar token Twitch: {error}") from error

        try:
            parsed_payload = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TwitchAuthError("Resposta invalida ao validar token Twitch.") from error
        return parsed_payload if isinstance(parsed_payload, dict) else None

    def _refresh_token_sync(self) -> dict:
        payload = urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        ).encode("utf-8")
        request = Request(
            self.settings.refresh_endpoint,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with self.urlopen_fn(request, timeout=self.settings.refresh_timeout_seconds) as response:
                raw_payload = response.read()
                status_code = response.status
        except HTTPError as error:
            response_text = ""
            try:
                response_text = error.read().decode("utf-8", errors="ignore").strip()
            except Exception:
                response_text = ""
            details = response_text or f"HTTP {error.code}"
            raise TwitchAuthError(f"Falha ao renovar token Twitch: {details}") from error
        except (URLError, TimeoutError, ValueError) as error:
            raise TwitchAuthError(f"Falha de rede ao renovar token Twitch: {error}") from error

        if status_code != 200:
            raise TwitchAuthError(f"Falha ao renovar token Twitch: HTTP {status_code}")

        try:
            parsed_payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TwitchAuthError("Resposta invalida no refresh de token Twitch.") from error

        if not isinstance(parsed_payload, dict) or not parsed_payload.get("access_token"):
            raise TwitchAuthError("Resposta de refresh da Twitch sem access_token.")
        return parsed_payload

    async def force_refresh(self, reason: str) -> str:
        if not self.can_refresh:
            raise TwitchAuthError(
                "Refresh automatico requer TWITCH_REFRESH_TOKEN, TWITCH_CLIENT_ID e TWITCH_CLIENT_SECRET."
            )
        refreshed_payload = await asyncio.to_thread(self._refresh_token_sync)
        self.access_token = str(refreshed_payload.get("access_token", "")).strip().removeprefix("oauth:")
        previous_refresh_token = self.refresh_token
        rotated_refresh_token = str(refreshed_payload.get("refresh_token", "")).strip()
        if rotated_refresh_token:
            self.refresh_token = rotated_refresh_token
            if rotated_refresh_token != previous_refresh_token and self.logger:
                self.logger.info("Refresh token Twitch rotacionado em memoria para esta instancia.")
        self._set_expiration(refreshed_payload.get("expires_in"))
        self.validated_once = True
        if self.logger:
            self.logger.info("Token Twitch renovado automaticamente (%s).", reason)
        if self.observability:
            self.observability.record_token_refresh(reason=reason)
        return self.access_token

    async def ensure_token_for_connection(self) -> str:
        if not self.access_token:
            raise TwitchAuthError("TWITCH_USER_TOKEN ausente.")

        if self.can_refresh:
            if self.expires_at_monotonic is None:
                validation = await asyncio.to_thread(self._validate_token_sync)
                self.validated_once = True
                if validation is None:
                    if self.logger:
                        self.logger.warning("Token Twitch invalido. Tentando renovar automaticamente...")
                    await self.force_refresh("token invalido antes da conexao IRC")
                else:
                    self._set_expiration(validation.get("expires_in"))
            if self._is_expiring_soon():
                await self.force_refresh("token proximo da expiracao")
            return self.access_token

        if not self.validated_once:
            validation = await asyncio.to_thread(self._validate_token_sync)
            self.validated_once = True
            if validation is None:
                raise TwitchAuthError("TWITCH_USER_TOKEN invalido e refresh automatico nao configurado.")
            self._set_expiration(validation.get("expires_in"))

        return self.access_token

    async def validate_now(self) -> dict[str, Any] | None:
        """Valida o token atual e retorna o payload da Twitch (incluindo scopes)."""
        validation = await asyncio.to_thread(self._validate_token_sync)
        if validation:
            self._set_expiration(validation.get("expires_in"))
            self.validated_once = True
        return validation
