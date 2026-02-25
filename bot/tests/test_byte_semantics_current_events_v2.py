import unittest

from bot.byte_semantics_current_events import (
    _build_grounding_source_line,
    _extract_grounding_source_urls,
    _fit_high_risk_current_events_reply,
    build_current_events_safe_fallback_reply,
    normalize_current_events_reply_contract,
)


class TestCurrentEventsV2(unittest.TestCase):
    def test_extract_grounding_source_urls_types(self):
        self.assertEqual(_extract_grounding_source_urls(None), [])
        self.assertEqual(_extract_grounding_source_urls({"source_urls": "not-a-list"}), [])
        res = _extract_grounding_source_urls({"source_urls": [123, None, "  https://ok.com  "]})
        self.assertIn("123", res)
        self.assertIn("https://ok.com", res)

    def test_build_grounding_source_line_multi_hosts(self):
        meta = {"source_urls": ["https://a.com/1", "https://www.b.com/2", "https://c.com/3"]}
        line = _build_grounding_source_line(meta)
        self.assertIn("a.com", line)
        self.assertIn("b.com", line)

    def test_fit_high_risk_reply_extreme_length(self):
        body = ["Line 1", "Line 2 " * 100]
        conf = "Confianca: alta"
        src = "Fonte: X"
        res = _fit_high_risk_current_events_reply(body, conf, src)
        self.assertLessEqual(len(res), 500)
        self.assertIn("Fonte: X", res)

    def test_normalize_contract_high_risk_uncertainty(self):
        prompt = "Quem venceu a eleição presidencial dos EUA hoje?"
        # Using a term from UNCERTAINTY_HINT_TERMS in constants.py: "incerto"
        answer = "Ainda é incerto quem venceu a eleição hoje."
        res = normalize_current_events_reply_contract(prompt, answer)
        from bot.byte_semantics_constants import QUALITY_SAFE_FALLBACK

        self.assertIn(QUALITY_SAFE_FALLBACK, res)

    def test_normalize_contract_high_risk_no_grounding(self):
        prompt = "Quem venceu a eleição presidencial dos EUA hoje?"
        answer = "Candidato X venceu."
        res = normalize_current_events_reply_contract(prompt, answer, grounding_metadata={})
        from bot.byte_semantics_constants import QUALITY_SAFE_FALLBACK

        self.assertIn(QUALITY_SAFE_FALLBACK, res)

    def test_build_safe_fallback_low_risk(self):
        from bot.byte_semantics_constants import QUALITY_SAFE_FALLBACK

        self.assertEqual(build_current_events_safe_fallback_reply("oi"), QUALITY_SAFE_FALLBACK)
