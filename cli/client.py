# SPDX-License-Identifier: MIT
"""HTTP client for the Byte Agent Dashboard API.

Provides a thin, production-grade wrapper over urllib.request with:
- Automatic authentication header injection
- Structured error handling with typed exceptions
- JSON request/response serialization
- Configurable timeouts
- Connection health probing
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Final

from cli.config import CLIConfig

_DEFAULT_TIMEOUT_SECONDS: Final[float] = 15.0
_HEALTH_TIMEOUT_SECONDS: Final[float] = 5.0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CLIClientError(Exception):
    """Base exception for all client errors."""

    def __init__(self, message: str, *, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(CLIClientError):
    """Raised when the API rejects the admin token (401/403)."""


class NotFoundError(CLIClientError):
    """Raised when the requested route does not exist (404)."""


class ServerError(CLIClientError):
    """Raised when the server returns 5xx."""


class ConnectionError_(CLIClientError):
    """Raised when the agent is unreachable."""


class InvalidResponseError(CLIClientError):
    """Raised when the server returns non-JSON or malformed data."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ByteClient:
    """HTTP client for the Byte Agent Dashboard API.

    Usage:
        client = ByteClient.from_config(config)
        data = client.get("/api/control-plane")
        client.post("/api/agent/suspend", {"reason": "maintenance"})
    """

    base_url: str
    token: str
    hf_token: str = ""
    timeout: float = _DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_config(cls, config: CLIConfig) -> ByteClient:
        return cls(
            base_url=config.url.rstrip("/"),
            token=config.token,
            hf_token=config.hf_token,
        )

    # -- Public API ---------------------------------------------------------

    def get(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """HTTP GET. Query params are URL-encoded automatically."""
        url = self._build_url(path, params)
        return self._request(url, method="GET")

    def put(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """HTTP PUT with JSON body."""
        url = self._build_url(path)
        return self._request(url, method="PUT", payload=payload or {})

    def post(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """HTTP POST with JSON body."""
        url = self._build_url(path)
        return self._request(url, method="POST", payload=payload or {})

    def health_check(self) -> bool:
        """Return True if the agent responds to /health."""
        url = f"{self.base_url}/health"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=_HEALTH_TIMEOUT_SECONDS) as resp:
                return 200 <= resp.getcode() < 300
        except Exception:
            return False

    # -- Internals ----------------------------------------------------------

    def _build_url(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> str:
        url = f"{self.base_url}{path}"
        if params:
            # Filter out empty values
            filtered = {k: v for k, v in params.items() if v}
            if filtered:
                url = f"{url}?{urllib.parse.urlencode(filtered)}"
        return url

    def _build_headers(self, *, with_body: bool = False) -> dict[str, str]:
        headers: dict[str, str] = {
            "User-Agent": "ByteCLI/1.0",
            "Accept": "application/json",
        }
        if self.token:
            headers["X-Byte-Admin-Token"] = self.token
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        if with_body:
            headers["Content-Type"] = "application/json; charset=utf-8"
        return headers

    def _request(
        self,
        url: str,
        *,
        method: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        has_body = payload is not None
        headers = self._build_headers(with_body=has_body)
        body_bytes: bytes | None = None
        if has_body:
            body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read()
                if not raw:
                    return {"ok": True}
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as exc:
                    # Some endpoints return plain text (e.g. health)
                    text = raw.decode("utf-8", errors="replace").strip()
                    if text == "AGENT_ONLINE":
                        return {"ok": True, "status": "AGENT_ONLINE"}
                    raise InvalidResponseError(
                        f"Invalid JSON from {method} {url}: {text[:200]}",
                        status_code=response.getcode(),
                    ) from exc

        except urllib.error.HTTPError as exc:
            status = exc.code
            body_text = ""
            try:
                body_text = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:
                pass

            # Try to extract JSON error message
            detail = body_text
            try:
                error_json = json.loads(body_text)
                detail = error_json.get("error", error_json.get("message", body_text))
            except (json.JSONDecodeError, AttributeError):
                pass

            if status in (401, 403):
                raise AuthenticationError(
                    f"Authentication failed ({status}): {detail}",
                    status_code=status,
                )
            if status == 404:
                raise NotFoundError(
                    f"Not found ({status}): {method} {url}",
                    status_code=status,
                )
            if status >= 500:
                raise ServerError(
                    f"Server error ({status}): {detail}",
                    status_code=status,
                )
            raise CLIClientError(
                f"HTTP {status}: {detail}",
                status_code=status,
            )

        except urllib.error.URLError as exc:
            raise ConnectionError_(
                f"Cannot connect to agent at {self.base_url}: {exc.reason}",
            ) from exc

        except TimeoutError as exc:
            raise ConnectionError_(
                f"Connection to {self.base_url} timed out after {self.timeout}s",
            ) from exc

        except OSError as exc:
            raise ConnectionError_(
                f"Network error connecting to {self.base_url}: {exc}",
            ) from exc
