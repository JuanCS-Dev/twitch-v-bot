import unittest
from unittest.mock import AsyncMock, MagicMock

from bot.byte_semantics_base import parse_byte_prompt
from bot.prompt_runtime import handle_byte_prompt_text


class TestReproduction(unittest.IsolatedAsyncioTestCase):
    async def test_se_apresente(self):
        prompt = "se apresente"
        author = "user123"
        replies = []

        async def reply_fn(text):
            replies.append(text)

        # We need to mock the dependencies in build_prompt_runtime or handle_byte_prompt_text_impl
        # But let's first see if parse_byte_prompt works as expected
        parsed = parse_byte_prompt("byte se apresente")
        self.assertEqual(parsed, "se apresente")

        # Now let's try to run handle_byte_prompt_text
        # We'll need to mock agent_inference and others if it reaches the LLM
        # But "se apresente" SHOULD be caught by is_intro_prompt and NOT reach LLM

        await handle_byte_prompt_text(parsed, author, reply_fn)

        print(f"Replies: {replies}")
        self.assertTrue(len(replies) > 0)
        self.assertIn("Sou Byte", replies[0])


if __name__ == "__main__":
    unittest.main()
