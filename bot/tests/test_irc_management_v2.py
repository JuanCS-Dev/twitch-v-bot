from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.irc_management import IrcChannelManagementMixin


class DummyManagement(IrcChannelManagementMixin):
    def __init__(self):
        self.owner_id = "owner"
        self.channel_logins = ["chan1"]
        self.joined_channels = {"chan1"}
        self._send_tracked_channel_reply = AsyncMock()
        self._join_channel = AsyncMock()
        self._part_channel = AsyncMock()
        self._can_wait_for_channel_confirmation = MagicMock(return_value=True)


class TestIrcManagementV2:
    def test_parse_channel_management_prompt(self):
        mgr = DummyManagement()
        assert mgr._parse_channel_management_prompt(" canais ") == ("list", "")
        assert mgr._parse_channel_management_prompt("join mychan") == ("join", "mychan")
        assert mgr._parse_channel_management_prompt(" part mychan ") == ("part", "mychan")
        assert mgr._parse_channel_management_prompt("unknown") is None
        assert mgr._parse_channel_management_prompt("") is None

    @pytest.mark.asyncio
    async def test_handle_channel_management_prompt_not_command(self):
        mgr = DummyManagement()
        assert await mgr._handle_channel_management_prompt("hello", MagicMock(), "chan1") is False

    @pytest.mark.asyncio
    async def test_handle_channel_management_prompt_not_owner(self):
        mgr = DummyManagement()
        author = MagicMock()
        author.id = "not_owner"
        with patch("bot.irc_management.is_owner", return_value=False):
            assert (
                await mgr._handle_channel_management_prompt("join chan2", author, "chan1") is True
            )
            mgr._send_tracked_channel_reply.assert_called_with(
                "chan1", "Somente o owner pode gerenciar canais do Byte."
            )

    @pytest.mark.asyncio
    async def test_handle_channel_management_prompt_list(self):
        mgr = DummyManagement()
        author = MagicMock()
        author.id = "owner"
        with patch("bot.irc_management.is_owner", return_value=True):
            assert await mgr._handle_channel_management_prompt("canais", author, "chan1") is True
            mgr._send_tracked_channel_reply.assert_called_with("chan1", "Canais ativos: #chan1.")

    @pytest.mark.asyncio
    async def test_handle_channel_management_prompt_join_success(self):
        mgr = DummyManagement()
        author = MagicMock()
        author.id = "owner"
        mgr._join_channel.return_value = True
        with patch("bot.irc_management.is_owner", return_value=True):
            assert (
                await mgr._handle_channel_management_prompt("join chan2", author, "chan1") is True
            )
            mgr._send_tracked_channel_reply.assert_called_with(
                "chan1", "Canal adicionado: #chan2. Byte responde onde for acionado."
            )

    @pytest.mark.asyncio
    async def test_handle_channel_management_prompt_join_fail(self):
        mgr = DummyManagement()
        author = MagicMock()
        author.id = "owner"
        mgr._join_channel.return_value = False
        with patch("bot.irc_management.is_owner", return_value=True):
            assert (
                await mgr._handle_channel_management_prompt("join chan2", author, "chan1") is True
            )
            mgr._send_tracked_channel_reply.assert_called_with(
                "chan1", "Nao consegui entrar em #chan2."
            )

    @pytest.mark.asyncio
    async def test_handle_channel_management_prompt_join_already_joined(self):
        mgr = DummyManagement()
        author = MagicMock()
        author.id = "owner"
        with patch("bot.irc_management.is_owner", return_value=True):
            assert (
                await mgr._handle_channel_management_prompt("join chan1", author, "chan1") is True
            )
            mgr._send_tracked_channel_reply.assert_called_with("chan1", "Ja estou no canal #chan1.")

    @pytest.mark.asyncio
    async def test_handle_channel_management_prompt_part_success(self):
        mgr = DummyManagement()
        mgr.channel_logins = ["chan1", "chan2"]
        mgr.joined_channels = {"chan1", "chan2"}
        author = MagicMock()
        author.id = "owner"
        mgr._part_channel.return_value = True
        with patch("bot.irc_management.is_owner", return_value=True):
            assert (
                await mgr._handle_channel_management_prompt("part chan2", author, "chan1") is True
            )
            mgr._send_tracked_channel_reply.assert_called_with("chan1", "Canal removido: #chan2.")

    @pytest.mark.asyncio
    async def test_handle_channel_management_prompt_part_last_channel(self):
        mgr = DummyManagement()
        author = MagicMock()
        author.id = "owner"
        with patch("bot.irc_management.is_owner", return_value=True):
            assert (
                await mgr._handle_channel_management_prompt("part chan1", author, "chan1") is True
            )
            mgr._send_tracked_channel_reply.assert_called_with(
                "chan1",
                "Nao posso sair do ultimo canal ativo. Entre em outro canal primeiro com 'byte join <canal>'.",
            )
