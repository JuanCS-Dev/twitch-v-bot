import unittest

import bot.byte_semantics_current_events as events
import bot.byte_semantics_quality as quality


class TestByteSemanticsLargeFiles(unittest.TestCase):
    def test_quality_functions(self):
        # Trigger is_serious_technical_prompt:
        # 1. len >= 24
        # 2. technical term: "medicina"
        # 3. relevance term: "hoje"
        tech_prompt = "Como está a medicina hoje em dia no Brasil?"
        self.assertIn("pesquisa", quality.build_research_priority_instruction(tech_prompt))

        # Anti-generic
        self.assertIn(
            "Contrato anti-generico", quality.build_anti_generic_contract_instruction("Pergunta")
        )

    def test_events_functions(self):
        self.assertIn("Timestamp", events.build_server_time_anchor_instruction())

        # build_verifiable_prompt with current event trigger ("hoje")
        res = events.build_verifiable_prompt("Quem ganhou o jogo de hoje?", concise_mode=False)
        self.assertIn("confiabilidade", res)

    def test_events_utility(self):
        # build_server_time_anchor_instruction custom
        self.assertIn(
            "2026-01-01", events.build_server_time_anchor_instruction("2026-01-01T00:00:00Z")
        )

        # check uncertainty (looks for UNCERTAINTY_HINT_TERMS like "incerto")
        if hasattr(events, "has_current_events_uncertainty"):
            self.assertTrue(events.has_current_events_uncertainty("isso é incerto"))
            self.assertFalse(events.has_current_events_uncertainty("certeza"))
