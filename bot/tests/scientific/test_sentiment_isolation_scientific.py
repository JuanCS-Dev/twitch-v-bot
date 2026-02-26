import unittest

from bot.sentiment_engine import SentimentEngine


class TestSentimentIsolationScientific(unittest.TestCase):
    def setUp(self):
        self.engine = SentimentEngine()

    def test_sentiment_isolation_between_channels(self):
        """Valida que o hype do Canal A não anima o Canal B."""
        # Canal A: Super Hype
        self.engine.ingest_message("canal_a", "PogChamp LETS GO PogChamp")
        self.engine.ingest_message("canal_a", "incrivel epico")

        # Canal B: Confusão
        self.engine.ingest_message("canal_b", "??? o que ha ???")
        self.engine.ingest_message("canal_b", "confuso nao entendi")

        vibe_a = self.engine.get_vibe("canal_a")
        vibe_b = self.engine.get_vibe("canal_b")

        print("\n--- SCIENTIFIC SENTIMENT AUDIT ---")
        print(f"Canal A Vibe: {vibe_a}")
        print(f"Canal B Vibe: {vibe_b}")

        self.assertEqual(vibe_a, "Hyped")
        self.assertEqual(vibe_b, "Confuso")

    def test_empty_channel_is_chill(self):
        """Valida que um canal sem mensagens retorna a vibe default."""
        vibe = self.engine.get_vibe("novo_canal")
        self.assertEqual(vibe, "Chill")


if __name__ == "__main__":
    unittest.main()
