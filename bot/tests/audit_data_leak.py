import unittest

from bot.logic_context import build_dynamic_prompt, context_manager


class TestDataLeakAudit(unittest.TestCase):
    def test_context_leak_between_channels(self):
        # Limpa contextos para o teste
        context_manager.cleanup("canal_a")
        context_manager.cleanup("canal_b")

        ctx_a = context_manager.get("canal_a")
        ctx_b = context_manager.get("canal_b")

        # Simula atividade no CANAL A
        ctx_a.remember_user_message("User_Canal_A", "Isso e um segredo do Canal A")

        # O prompt gerado para o Canal B NÃO deve conter o histórico do Canal A
        prompt_canal_b = build_dynamic_prompt("quem e voce?", "User_Canal_B", ctx_b)

        print("\n--- AUDIT: PROMPT GERADO PARA CANAL B (ISOLADO) ---")
        print(prompt_canal_b)
        print("---------------------------------------------------")

        # O segredo do Canal A NÃO deve estar no prompt do Canal B
        leak_detected = "User_Canal_A" in prompt_canal_b

        if leak_detected:
            print("\n[FALHA] VAZAMENTO DETECTADO!")
        else:
            print("\n[SUCESSO] Contexto isolado corretamente.")

        self.assertFalse(leak_detected, "O contexto do Canal A vazou para o Canal B!")


if __name__ == "__main__":
    unittest.main()
