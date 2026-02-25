import unittest
import bot.byte_semantics_reply as reply_logic
from bot.byte_semantics_constants import MULTIPART_SEPARATOR

class TestByteSemanticsReply(unittest.TestCase):
    def test_split_text_for_chat_short(self):
        self.assertEqual(reply_logic.split_text_for_chat("hello"), ["hello"])

    def test_split_text_for_chat_with_newlines(self):
        text = "First line.\nSecond line that is also quite long for a single message."
        parts = reply_logic.split_text_for_chat(text, max_len=20, max_parts=2)
        self.assertEqual(parts[0], "First line.")

    def test_extract_multi_reply_parts_separator(self):
        text = f"Part 1 {MULTIPART_SEPARATOR} Part 2 {MULTIPART_SEPARATOR} Part 3"
        parts = reply_logic.extract_multi_reply_parts(text, max_parts=2)
        self.assertEqual(len(parts), 2)

    def test_extract_movie_title_advanced(self):
        # Test the regex fallback for "ficha tecnica"
        self.assertEqual(reply_logic.extract_movie_title("Qual a ficha tecnica do filme Pulp Fiction?"), "Pulp Fiction")
        self.assertEqual(reply_logic.extract_movie_title("Ficha tecnica de Matrix"), "Matrix")
        # Unicode
        self.assertEqual(reply_logic.extract_movie_title("Ficha técnica de Bacurau"), "Bacurau")
        # Empty
        self.assertEqual(reply_logic.extract_movie_title("ficha tecnica"), "")

    def test_build_movie_fact_sheet_query(self):
        query = reply_logic.build_movie_fact_sheet_query("Matrix")
        self.assertIn("'Matrix'", query)
