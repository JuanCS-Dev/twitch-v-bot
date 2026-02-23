import asyncio
import base64
import binascii
import hmac
import inspect
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Coroutine, cast


CHANNEL_CONTROL_TIMEOUT_SECONDS = 15.0
SUPPORTED_ACTIONS = {"list", "join", "part"}


def extract_admin_token(headers: Any) -> str:
    direct = str(headers.get("X-Byte-Admin-Token", "") or "").strip()
    if direct:
        return direct

    authorization = str(headers.get("Authorization", "") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if authorization.lower().startswith("basic "):
        encoded_credentials = authorization[6:].strip()
        if not encoded_credentials:
            return ""
        try:
            decoded_credentials = base64.b64decode(
                encoded_credentials, validate=True
            ).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return ""

        if ":" in decoded_credentials:
            _, password = decoded_credentials.split(":", 1)
            return password.strip()
        return decoded_credentials.strip()
    return ""


def is_dashboard_admin_authorized(headers: Any, expected_token: str) -> bool:
    configured_token = (expected_token or "").strip()
    if not configured_token:
        return False

    provided_token = extract_admin_token(headers)
    if not provided_token:
        return False
    return hmac.compare_digest(provided_token, configured_token)


def parse_terminal_command(command_text: str) -> tuple[str, str]:
    normalized = " ".join((command_text or "").strip().split())
    lowered = normalized.lower()
    if not lowered:
        raise ValueError("Command is required. Use: list | join <channel> | part <channel>.")

    if lowered in {"list", "channels", "canais"}:
        return ("list", "")

    for prefix in ("join ", "entrar ", "add "):
        if lowered.startswith(prefix):
            return ("join", normalized[len(prefix):].strip())

    for prefix in ("part ", "leave ", "sair ", "remove "):
        if lowered.startswith(prefix):
            return ("part", normalized[len(prefix):].strip())

    raise ValueError("Unsupported command. Use: list | join <channel> | part <channel>.")


class IrcChannelControlBridge:
    def __init__(self, timeout_seconds: float = CHANNEL_CONTROL_TIMEOUT_SECONDS) -> None:
        self._timeout_seconds = max(1.0, float(timeout_seconds))
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._bot: Any = None

    def bind(self, *, loop: asyncio.AbstractEventLoop, bot: Any) -> None:
        with self._lock:
            self._loop = loop
            self._bot = bot

    def unbind(self) -> None:
        with self._lock:
            self._loop = None
            self._bot = None

    def _snapshot(self) -> tuple[Any, asyncio.AbstractEventLoop | None]:
        with self._lock:
            return self._bot, self._loop

    def _submit(self, coroutine: Coroutine[Any, Any, Any]) -> Any:
        bot, loop = self._snapshot()
        if bot is None or loop is None or loop.is_closed() or not loop.is_running():
            raise RuntimeError("IRC runtime is not connected yet.")

        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        try:
            return future.result(timeout=self._timeout_seconds)
        except FutureTimeoutError as error:
            future.cancel()
            raise TimeoutError("Channel control timeout while waiting for IRC runtime.") from error

    def execute(self, *, action: str, channel_login: str = "") -> dict[str, Any]:
        normalized_action = (action or "").strip().lower()
        normalized_channel = (channel_login or "").strip()
        if normalized_action not in SUPPORTED_ACTIONS:
            return {
                "ok": False,
                "error": "invalid_action",
                "message": "Unsupported action. Use: list, join, part.",
            }

        try:
            if normalized_action == "list":
                channels = self._submit(self._safe_call("admin_list_channels"))
                return {
                    "ok": True,
                    "action": "list",
                    "channels": channels,
                    "message": f"Connected channels: {', '.join(f'#{item}' for item in channels) or 'none'}.",
                }

            if not normalized_channel:
                return {
                    "ok": False,
                    "error": "missing_channel",
                    "message": f"Action '{normalized_action}' requires a channel login.",
                }

            method_name = "admin_join_channel" if normalized_action == "join" else "admin_part_channel"
            success, message, channels = self._submit(self._safe_call(method_name, normalized_channel))
            return {
                "ok": bool(success),
                "action": normalized_action,
                "channels": channels,
                "message": str(message),
            }
        except TimeoutError as error:
            return {"ok": False, "error": "timeout", "message": str(error)}
        except RuntimeError as error:
            return {"ok": False, "error": "runtime_unavailable", "message": str(error)}
        except Exception as error:
            return {"ok": False, "error": "runtime_error", "message": str(error)}

    async def _safe_call(self, method_name: str, *args: Any) -> Any:
        bot, _ = self._snapshot()
        if bot is None:
            raise RuntimeError("IRC runtime is not connected yet.")

        target = getattr(bot, method_name, None)
        if not callable(target):
            raise RuntimeError(f"IRC runtime method not available: {method_name}")
        result = target(*args)
        if not inspect.iscoroutine(result):
            raise RuntimeError(f"IRC runtime method is not awaitable: {method_name}")
        return await cast(Coroutine[Any, Any, Any], result)
