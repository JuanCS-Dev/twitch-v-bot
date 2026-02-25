import asyncio
import ssl
import time
from typing import TYPE_CHECKING, Any

from bot.irc_protocol import IRC_WELCOME_PATTERN
from bot.logic import BOT_BRAND
from bot.observability import observability
from bot.runtime_config import logger
from bot.twitch_tokens import TwitchAuthError, is_irc_auth_failure_line


class IrcConnectionMixin:
    host: str
    port: int
    use_tls: bool
    bot_login: str
    channel_logins: list[str]
    reader: asyncio.StreamReader | None
    writer: Any
    token_manager: Any
    _line_reader_running: bool
    _line_reader_task: asyncio.Task[Any] | None
    _pending_join_events: dict[str, asyncio.Event]
    _pending_part_events: dict[str, asyncio.Event]

    if TYPE_CHECKING:

        async def _handle_membership_event(self, line: str) -> None: ...
        async def _handle_notice_line(self, line: str) -> None: ...
        async def _handle_privmsg(self, line: str) -> None: ...
        async def _recover_authentication(self, auth_error: Exception) -> bool: ...
        def _raise_auth_error(self, line: str) -> None: ...

    async def _send_raw(self, line: str) -> None:
        if self.writer is None:
            raise RuntimeError("Conexao IRC nao inicializada.")
        self.writer.write(f"{line}\r\n".encode())
        await self.writer.drain()

    async def _await_login_confirmation(self, timeout_seconds: float = 15.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Timeout aguardando confirmacao de login IRC.")
            if self.reader is None:
                raise RuntimeError("Leitor IRC indisponivel durante login.")

            payload = await asyncio.wait_for(self.reader.readline(), timeout=remaining)
            if not payload:
                raise ConnectionError("Conexao IRC encerrada durante autenticacao.")

            line = payload.decode("utf-8", errors="ignore").rstrip("\r\n")
            if not line:
                continue
            if line.startswith("PING"):
                await self._send_raw(line.replace("PING", "PONG", 1))
                continue
            if is_irc_auth_failure_line(line):
                raise TwitchAuthError(f"Falha de autenticacao IRC: {line}")
            if IRC_WELCOME_PATTERN.search(line):
                return

    async def _connect(self) -> None:
        access_token = await self.token_manager.ensure_token_for_connection()
        ssl_context = ssl.create_default_context() if self.use_tls else None
        self.reader, self.writer = await asyncio.open_connection(
            self.host, self.port, ssl=ssl_context
        )
        await self._send_raw("CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands")
        await self._send_raw(f"PASS oauth:{access_token}")
        await self._send_raw(f"NICK {self.bot_login}")
        await self._await_login_confirmation()
        for channel_login in self.channel_logins:
            await self._send_raw(f"JOIN #{channel_login}")
        channels_summary = ", ".join(f"#{channel}" for channel in self.channel_logins)
        logger.info("%s conectado via IRC em %s", BOT_BRAND, channels_summary)

    async def _close(self) -> None:
        if self.writer is None:
            return
        try:
            self.writer.close()
            await self.writer.wait_closed()
        finally:
            self.reader = None
            self.writer = None

    async def run_forever(self) -> None:
        while True:
            reconnect_delay_seconds = 5
            self._line_reader_running = False
            self._line_reader_task = None
            try:
                await self._connect()
                self._line_reader_running = True
                self._line_reader_task = asyncio.current_task()
                while True:
                    if self.reader is None:
                        raise RuntimeError("Leitor IRC indisponivel.")
                    payload = await self.reader.readline()
                    if not payload:
                        raise ConnectionError("Conexao IRC encerrada.")
                    line = payload.decode("utf-8", errors="ignore").rstrip("\r\n")
                    if not line:
                        continue
                    if line.startswith("PING"):
                        await self._send_raw(line.replace("PING", "PONG", 1))
                        continue
                    logger.info("IRC RAW: %s", line)
                    if is_irc_auth_failure_line(line):
                        self._raise_auth_error(line)
                    if line.startswith("RECONNECT"):
                        raise ConnectionError("Servidor IRC solicitou reconexao.")
                    await self._handle_membership_event(line)
                    await self._handle_notice_line(line)
                    await self._handle_privmsg(line)
            except asyncio.CancelledError:
                raise
            except TwitchAuthError as auth_error:
                recovered = await self._recover_authentication(auth_error)
                reconnect_delay_seconds = 2 if recovered else 20
            except Exception as error:
                logger.warning("Conexao IRC instavel: %s", error)
                observability.record_error(category="irc_connection", details=str(error))
                reconnect_delay_seconds = 5
            finally:
                self._line_reader_running = False
                self._line_reader_task = None
                self._pending_join_events.clear()
                self._pending_part_events.clear()
                await self._close()
            await asyncio.sleep(reconnect_delay_seconds)
