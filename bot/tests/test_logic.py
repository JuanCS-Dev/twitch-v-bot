import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.logic import agent_inference, build_dynamic_prompt, context_manager, enforce_reply_limits
from bot.logic_inference import (
    _build_agent_notes_instruction,
    _build_messages,
    _execute_inference,
    _record_token_usage,
    _resolve_generation_params,
)


class TestBotLogic(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await context_manager.cleanup("default")

    def test_enforce_reply_limits(self):
        # Suite espera que se houver 5 linhas, a 5a seja removida.
        text = "L1\nL2\nL3\nL4\nL5"
        res = enforce_reply_limits(text, max_lines=4)
        self.assertNotIn("L5", res)
        self.assertEqual(len(res.split()), 4)

    def test_build_prompt(self):
        ctx = context_manager.get_sync("default")
        ctx.remember_user_message("user", "oi")
        prompt = build_dynamic_prompt("teste", "autor", ctx)
        self.assertIn("Historico recente:", prompt)
        self.assertIn("user: oi", prompt)

    @patch("bot.logic_inference._execute_inference_with_retry")
    async def test_agent_inference_success(self, mock_execute):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Resposta do bot"
        mock_execute.return_value = mock_response

        ctx = context_manager.get("test")
        mock_client = MagicMock()
        res = await agent_inference("pergunta", "user", mock_client, ctx)
        self.assertEqual(res, "Resposta do bot")
        self.assertEqual(mock_execute.await_args.kwargs["temperature"], 0.15)
        self.assertIsNone(mock_execute.await_args.kwargs["top_p"])
        self.assertEqual(mock_execute.await_args.kwargs["channel_id"], "test")

    @patch("bot.logic_inference._execute_inference_with_retry")
    async def test_agent_inference_uses_channel_generation_overrides(self, mock_execute):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Resposta tunada"
        mock_execute.return_value = mock_response

        ctx = context_manager.get("override_channel")
        ctx.inference_temperature = 0.42
        ctx.inference_top_p = 0.88

        mock_client = MagicMock()
        res = await agent_inference("pergunta", "user", mock_client, ctx)

        self.assertEqual(res, "Resposta tunada")
        self.assertEqual(mock_execute.await_args.kwargs["temperature"], 0.42)
        self.assertEqual(mock_execute.await_args.kwargs["top_p"], 0.88)
        self.assertEqual(mock_execute.await_args.kwargs["channel_id"], "override_channel")

    @patch("bot.logic_inference.observability")
    def test_record_token_usage_includes_channel_id(self, mock_observability):
        response = MagicMock()
        response.usage.prompt_tokens = 11
        response.usage.completion_tokens = 7

        _record_token_usage(response, channel_id="canal_a")

        self.assertEqual(mock_observability.record_token_usage.call_count, 1)
        self.assertEqual(
            mock_observability.record_token_usage.call_args.kwargs["channel_id"],
            "canal_a",
        )

    async def test_execute_inference_includes_optional_top_p(self):
        mock_client = MagicMock()
        mock_to_thread = AsyncMock(return_value={"ok": True})

        with patch("bot.logic_inference.asyncio.to_thread", mock_to_thread):
            result = await _execute_inference(
                mock_client,
                "test-model",
                [{"role": "user", "content": "oi"}],
                temperature=0.3,
                top_p=0.9,
            )

        self.assertEqual(result, {"ok": True})
        mock_to_thread.assert_awaited_once_with(
            mock_client.chat.completions.create,
            model="test-model",
            messages=[{"role": "user", "content": "oi"}],
            temperature=0.3,
            max_tokens=2048,
            top_p=0.9,
        )

    def test_resolve_generation_params_invalid_override_falls_back_to_default(self):
        ctx = MagicMock(inference_temperature="bad", inference_top_p=1.5)

        temperature, top_p = _resolve_generation_params(ctx)

        self.assertEqual(temperature, 0.15)
        self.assertIsNone(top_p)

    def test_build_agent_notes_instruction_returns_empty_for_blank_notes(self):
        ctx = MagicMock(agent_notes=" \n ")

        instruction = _build_agent_notes_instruction(ctx)

        self.assertEqual(instruction, "")

    def test_build_messages_injects_agent_notes_into_system_prompt(self):
        ctx = context_manager.get("notes_channel")
        ctx.agent_notes = (
            "Priorize contexto do streamer.\nEvite backseat agressivo.\nFoque em perguntas curtas."
        )

        messages = _build_messages("oque rolou", "viewer", ctx, True, [])

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Diretrizes operacionais do canal", messages[0]["content"])
        self.assertIn("- Priorize contexto do streamer.", messages[0]["content"])
        self.assertIn("- Evite backseat agressivo.", messages[0]["content"])
        self.assertEqual(messages[1]["role"], "user")

    def test_build_agent_notes_instruction_limits_and_compacts_lines(self):
        ctx = MagicMock(
            agent_notes="\n".join(
                [
                    "  Linha   1  ",
                    "Linha 2",
                    "Linha 3",
                    "Linha 4",
                    "Linha 5",
                    "Linha 6",
                    "Linha 7",
                ]
            )
        )

        instruction = _build_agent_notes_instruction(ctx)

        self.assertIn("- Linha 1", instruction)
        self.assertIn("- Linha 6", instruction)
        self.assertNotIn("Linha 7", instruction)


if __name__ == "__main__":
    unittest.main()
