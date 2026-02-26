import time

from bot.tests.scientific_shared import ScientificTestCase


class ScientificSentimentTestsMixin(ScientificTestCase):
    """Testes cientificos para SentimentEngine (Fase 8)."""

    def test_sentiment_score_positive_emotes(self) -> None:
        from bot.sentiment_engine import _score_message

        self.assertGreater(_score_message("PogChamp insano!"), 0)
        self.assertGreater(_score_message("LUL KEKW morrendo de rir"), 0)
        self.assertGreater(_score_message("HYPERS vamos!"), 0)

    def test_sentiment_score_negative_emotes(self) -> None:
        from bot.sentiment_engine import _score_message

        self.assertLess(_score_message("Sadge PepeHands"), 0)
        self.assertLess(_score_message("BibleThump que triste"), 0)
        self.assertLess(_score_message("??? nao entendi nada"), 0)

    def test_sentiment_score_neutral(self) -> None:
        from bot.sentiment_engine import _score_message

        self.assertEqual(_score_message("oi tudo bem"), 0.0)
        self.assertEqual(_score_message(""), 0.0)

    def test_sentiment_score_keywords(self) -> None:
        from bot.sentiment_engine import _score_message

        self.assertGreater(_score_message("gg, partida incrivel"), 0)
        self.assertLess(_score_message("que chato isso, boring demais"), 0)

    def test_sentiment_ingest_updates_events(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        engine.ingest_message("default", "PogChamp")
        scores = engine.get_scores("default")
        self.assertEqual(scores["count"], 1)
        self.assertGreater(scores["avg"], 0)

    def test_sentiment_vibe_hyped(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        for _ in range(10):
            engine.ingest_message("default", "HYPERS PogChamp LETS")
        self.assertEqual(engine.get_vibe("default"), "Hyped")

    def test_sentiment_vibe_chill(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        vibe = engine.get_vibe("default")
        self.assertEqual(vibe, "Chill")  # Default com 0 eventos

    def test_sentiment_vibe_confuso(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        # Mild confusion: avg should land in (-1.0, -0.3) range
        for _ in range(10):
            engine.ingest_message("default", "Hmm hein")

        # A lógica nova de vibe é mais estrita. Vamos garantir que atinja Confuso.
        # threshold de Confuso é -1.0. 'Hmm'=-0.5, 'hein'=-0.5 -> total -1.0.
        # 2 tokens -> avg -0.5. Isso cai em Confuso?
        # Pela lógica nova: avg < 0 e avg <= threshold.
        # -0.5 não é <= -1.0. Então cai em VIBE_DEFAULT (Triste).
        # Para testar CONFUSO real, precisamos de avg <= -1.0.

        for _ in range(5):
            engine.ingest_message("default", "??? ???")  # avg -1.0

        self.assertEqual(engine.get_vibe("default"), "Confuso")

    def test_sentiment_anti_boredom_not_triggered_few_messages(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        engine.ingest_message("default", "oi")
        self.assertFalse(engine.should_trigger_anti_boredom("default"))

    def test_sentiment_anti_boredom_triggered(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        for _ in range(20):
            engine.ingest_message("default", "Sadge que boring")
        self.assertTrue(engine.should_trigger_anti_boredom("default"))

    def test_sentiment_anti_confusion_triggered(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        for _ in range(10):
            engine.ingest_message("default", "??? nao entendi confuso")
        self.assertTrue(engine.should_trigger_anti_confusion("default"))

    def test_sentiment_anti_confusion_not_triggered_few(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        engine.ingest_message("default", "???")
        self.assertFalse(engine.should_trigger_anti_confusion("default"))

    def test_sentiment_rolling_window_respects_time(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        # Inject old event
        old_ts = time.time() - 120  # 2 min ago, outside 60s window
        engine.ingest_message("default", "ignore")

        with engine._lock:
            # Substitui o evento gerado por um antigo manualmente para o teste
            engine._channel_events["default"][-1] = (old_ts, 5.0)

        engine.ingest_message("default", "oi")  # neutral, within window
        scores = engine.get_scores("default", window_seconds=60.0)
        self.assertEqual(scores["count"], 1)  # Only the recent one

    def test_sentiment_get_scores_empty(self) -> None:
        from bot.sentiment_engine import SentimentEngine

        engine = SentimentEngine()
        scores = engine.get_scores("default")
        self.assertEqual(scores["count"], 0)
        self.assertEqual(scores["avg"], 0.0)

    def test_sentiment_mixed_emotes(self) -> None:
        from bot.sentiment_engine import _score_message

        # Mixed message — PogChamp (+2) and Sadge (-1.5) = +0.5
        score = _score_message("PogChamp mas tambem Sadge")
        self.assertAlmostEqual(score, 0.5, places=1)
