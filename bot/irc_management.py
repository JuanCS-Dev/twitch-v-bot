from typing import TYPE_CHECKING, Any

from bot.access_control import is_owner
from bot.status_runtime import normalize_channel_login


class IrcChannelManagementMixin:
    owner_id: str
    channel_logins: list[str]
    joined_channels: set[str]

    if TYPE_CHECKING:
        async def _send_tracked_channel_reply(self, channel_login: str, text: str) -> None: ...
        async def _join_channel(self, channel_login: str) -> bool: ...
        async def _part_channel(self, channel_login: str) -> bool: ...
        def _can_wait_for_channel_confirmation(self) -> bool: ...

    def _parse_channel_management_prompt(self, prompt: str) -> tuple[str, str] | None:
        normalized_prompt = " ".join((prompt or "").strip().split())
        if not normalized_prompt:
            return None

        lowered_prompt = normalized_prompt.lower()
        if lowered_prompt in {
            "canais",
            "canal",
            "channels",
            "channel",
            "list channels",
            "listar canais",
        }:
            return ("list", "")
        for prefix in ("join ", "entrar ", "add "):
            if lowered_prompt.startswith(prefix):
                return ("join", normalized_prompt[len(prefix):].strip())
        for prefix in ("part ", "leave ", "sair ", "remove "):
            if lowered_prompt.startswith(prefix):
                return ("part", normalized_prompt[len(prefix):].strip())
        return None

    async def _handle_channel_management_prompt(
        self, prompt: str, author: Any, source_channel: str
    ) -> bool:
        command = self._parse_channel_management_prompt(prompt)
        if command is None:
            return False
        if not is_owner(getattr(author, "id", ""), self.owner_id):
            await self._send_tracked_channel_reply(
                source_channel,
                "Somente o owner pode gerenciar canais do Byte.",
            )
            return True

        action, raw_target = command
        if action == "list":
            channels = ", ".join(f"#{channel}" for channel in self.channel_logins)
            await self._send_tracked_channel_reply(source_channel, f"Canais ativos: {channels}.")
            return True
        if action == "join":
            target_channel = normalize_channel_login(raw_target)
            if not target_channel:
                await self._send_tracked_channel_reply(source_channel, "Uso: byte join <canal>.")
                return True
            if target_channel in self.joined_channels:
                await self._send_tracked_channel_reply(
                    source_channel, f"Ja estou no canal #{target_channel}."
                )
                return True
            can_wait_confirmation = self._can_wait_for_channel_confirmation()
            joined = await self._join_channel(target_channel)
            if joined and can_wait_confirmation:
                message = (
                    f"Canal adicionado: #{target_channel}. Byte responde onde for acionado."
                )
            elif joined:
                message = (
                    f"Solicitacao enviada para entrar em #{target_channel}. "
                    "Aguarde confirmacao do IRC."
                )
            else:
                message = f"Nao consegui entrar em #{target_channel}."
            await self._send_tracked_channel_reply(source_channel, message)
            return True
        if action != "part":
            return False

        target_channel = normalize_channel_login(raw_target or source_channel)
        if not target_channel:
            await self._send_tracked_channel_reply(source_channel, "Uso: byte part <canal>.")
            return True
        if target_channel not in self.joined_channels:
            await self._send_tracked_channel_reply(
                source_channel, f"Nao estou no canal #{target_channel}."
            )
            return True
        if len(self.channel_logins) <= 1:
            await self._send_tracked_channel_reply(
                source_channel,
                "Nao posso sair do ultimo canal ativo. Entre em outro canal primeiro com 'byte join <canal>'.",
            )
            return True
        if target_channel == source_channel:
            await self._send_tracked_channel_reply(
                source_channel,
                f"Solicitacao recebida: tentando sair de #{target_channel}.",
            )
            parted = await self._part_channel(target_channel)
            if not parted:
                await self._send_tracked_channel_reply(
                    source_channel,
                    f"Nao consegui sair de #{target_channel}.",
                )
            return True

        can_wait_confirmation = self._can_wait_for_channel_confirmation()
        parted = await self._part_channel(target_channel)
        if parted and can_wait_confirmation:
            message = f"Canal removido: #{target_channel}."
        elif parted:
            message = (
                f"Solicitacao enviada para sair de #{target_channel}. "
                "Aguarde confirmacao do IRC."
            )
        else:
            message = f"Nao consegui sair de #{target_channel}."
        await self._send_tracked_channel_reply(source_channel, message)
        return True
