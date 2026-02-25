import asyncio
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Adiciona o diretorio raiz ao PYTHONPATH para testes no vscode ou pytest chamados isoladamente
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from bot.autonomy_logic import process_autonomy_goal
from bot.clip_jobs_runtime import ClipJobsRuntime
from bot.clip_jobs_store import SupabaseJobStore
from bot.control_plane import RISK_CLIP_CANDIDATE, control_plane


class TestE2EClipsPipeline(unittest.TestCase):
    """
    Teste E2E Científico: Simula o ciclo de vida completo de um clip,
    da detecção autônoma até o download e persistência, com injeção de caos.
    """

    def setUp(self):
        # Reset global state
        self.store_mock = MagicMock(spec=SupabaseJobStore)
        self.store_mock.load_active_jobs.return_value = []

        # Patch store at module level for runtime
        self.store_patch = patch("bot.clip_jobs_runtime.job_store", self.store_mock)
        self.store_patch.start()

        self.runtime = ClipJobsRuntime()
        self.runtime.bind_token_provider(self._fake_token)

        # Config override
        control_plane.update_config(
            {"autonomy_enabled": True, "clip_pipeline_enabled": True, "clip_mode_default": "live"}
        )

    def tearDown(self):
        self.store_patch.stop()
        self.runtime.stop()

    async def _fake_token(self):
        return "mock_token_abc123"

    def test_e2e_happy_path_live_clip(self):
        """
        Cenário: Autonomia detecta -> Aprovação -> Criação -> Polling -> Ready -> Persistência
        """
        # 1. Autonomia gera candidato
        goal = {"id": "detect_clip", "risk": RISK_CLIP_CANDIDATE, "name": "Detect"}

        with patch(
            "bot.autonomy_logic.generate_goal_text", return_value="Momentazo épico aconteceu"
        ):
            result = asyncio.run(process_autonomy_goal(goal, None))

        self.assertEqual(result["outcome"], "queued")
        action_id = result["action_id"]

        # 2. Operador Aprova
        control_plane.decide_action(action_id=action_id, decision="approve")

        # 3. Runtime sincroniza
        asyncio.run(self.runtime._sync_from_queue())
        jobs = self.runtime.get_jobs()
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["status"], "queued")
        self.store_mock.save_job.assert_called()  # Verificando persistência inicial

        # 4. Runtime processa criação (Mock API)
        with patch("bot.clip_jobs_runtime.create_clip_live") as mock_create:
            mock_create.return_value = {"id": "TwitchClip123", "edit_url": "http://edit"}
            asyncio.run(self.runtime._advance_jobs())

        job = self.runtime.get_jobs()[0]
        self.assertEqual(job["status"], "polling")
        self.assertEqual(job["twitch_clip_id"], "TwitchClip123")

        # Force next poll to be immediate for test speed
        self.runtime._update_job(job["action_id"], next_poll_at=0.0)

        # 5. Runtime faz polling (Mock API ainda não pronto)
        with patch("bot.clip_jobs_runtime.get_clip") as mock_get:
            mock_get.return_value = None  # Processando...
            asyncio.run(self.runtime._advance_jobs())

        job = self.runtime.get_jobs()[0]
        self.assertEqual(job["status"], "polling")  # Mantém polling

        # Force next poll again
        self.runtime._update_job(job["action_id"], next_poll_at=0.0)

        # 6. Runtime faz polling (Mock API pronto)
        with patch("bot.clip_jobs_runtime.get_clip") as mock_get:
            mock_get.return_value = {"id": "TwitchClip123", "url": "http://clip.tv"}
            asyncio.run(self.runtime._advance_jobs())

        job = self.runtime.get_jobs()[0]
        self.assertEqual(job["status"], "ready")
        self.assertEqual(job["clip_url"], "http://clip.tv")

        # 7. Runtime busca download (Best effort)
        with patch("bot.clip_jobs_runtime.get_clip_download_url") as mock_dl:
            mock_dl.return_value = "http://dl.mp4"
            asyncio.run(self.runtime._advance_jobs())

        job = self.runtime.get_jobs()[0]
        self.assertEqual(job["download_url"], "http://dl.mp4")

        # Verificação final de persistência
        self.assertGreater(self.store_mock.save_job.call_count, 4)

    # ... (previous tests) ...

    def test_e2e_persistence_rehydration(self):
        """
        Cenário: Container restart. Runtime deve carregar jobs do Store.
        """
        # Simula jobs salvos COMPLETO com campos obrigatorios
        active_jobs = [
            {
                "job_id": "j1",
                "action_id": "a1",
                "status": "polling",
                "twitch_clip_id": "c1",
                "created_at": "2023-01-01",
                "broadcaster_id": "999",
                "next_poll_at": 0.0,
                "poll_until": 9999999999.0,
            },
            {
                "job_id": "j2",
                "action_id": "a2",
                "status": "queued",
                "created_at": "2023-01-02",
                "broadcaster_id": "999",
                "mode": "live",
            },
        ]
        self.store_mock.load_active_jobs.return_value = active_jobs

        # Novo runtime (simula restart)
        new_runtime = ClipJobsRuntime()

        jobs = new_runtime.get_jobs()
        self.assertEqual(len(jobs), 2)
        # Ordenação por data desc: j2 (02/01) vem antes de j1 (01/01)
        self.assertEqual(jobs[0]["job_id"], "j2")
        self.assertEqual(jobs[1]["job_id"], "j1")

        # Verifica se o novo runtime consegue processar os jobs reidratados
        with patch("bot.clip_jobs_runtime.get_clip") as mock_get:
            mock_get.return_value = {"id": "c1", "url": "http://done"}

            # Precisamos bindar token provider no novo runtime
            new_runtime.bind_token_provider(self._fake_token)

            # Patch store no modulo para o novo runtime funcionar (já está patchado globalmente no setUp)
            # Mas vamos garantir que o runtime use o mock
            asyncio.run(new_runtime._advance_jobs())

        # j1 deve ter avançado para ready
        updated_jobs = new_runtime.get_jobs()
        j1 = next(j for j in updated_jobs if j["job_id"] == "j1")
        self.assertEqual(j1["status"], "ready")
