import unittest

import bot.byte_semantics_reply as reply_logic


class TestByteSemanticsReplyExtra(unittest.TestCase):
    def test_split_text_edge_cases(self):
        # Empty text
        self.assertEqual(reply_logic.split_text_for_chat(""), [])
        self.assertEqual(reply_logic.split_text_for_chat(None), [])

        # Long text no spaces
        self.assertEqual(len(reply_logic.split_text_for_chat("a" * 1000, max_len=400)), 2)

    def test_extract_movie_title_variations(self):
        # Movie title with "que estamos assistindo" (should return empty)
        self.assertEqual(reply_logic.extract_movie_title("ficha tecnica do que estamos vendo"), "")

        # Movie title with punctuation
        self.assertEqual(
            reply_logic.extract_movie_title("Ficha tecnica do filme Matrix!!!"), "Matrix"
        )

        # Generic terms
        self.assertEqual(reply_logic.extract_movie_title("ficha tecnica hoje"), "")
        self.assertEqual(reply_logic.extract_movie_title("ficha tecnica agora"), "")
