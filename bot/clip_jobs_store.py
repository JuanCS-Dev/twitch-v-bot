import logging
import threading
from typing import Any, List, Optional

from google.cloud import firestore  # type: ignore[attr-defined,import-untyped]
from bot.runtime_config import PROJECT_ID

logger = logging.getLogger("byte.clips.store")

COLLECTION_NAME = "clip_jobs"

class FirestoreJobStore:
    def __init__(self) -> None:
        self._db: Optional[firestore.Client] = None
        self._lock = threading.Lock()
        self._project_id = PROJECT_ID
        
        if not self._project_id:
            logger.warning("PROJECT_ID nao definido. FirestoreJobStore operando em modo offline (no-op).")

    def _get_db(self) -> Optional[firestore.Client]:
        if self._db:
            return self._db
        
        if not self._project_id:
            return None

        try:
            # Lazy init to avoid slow import/auth at module level
            with self._lock:
                if not self._db:
                    self._db = firestore.Client(project=self._project_id)
            return self._db
        except Exception as e:
            logger.error("Falha ao inicializar Firestore: %s", e)
            return None

    def save_job(self, job: dict[str, Any]) -> None:
        db = self._get_db()
        if not db:
            return

        job_id = job.get("job_id")
        if not job_id:
            logger.error("Tentativa de salvar job sem job_id.")
            return

        try:
            # Firestore requires a clean dict, ensure types are compatible
            # job dict is usually flat with strings/floats, safe for Firestore
            doc_ref = db.collection(COLLECTION_NAME).document(job_id)
            doc_ref.set(job, merge=True)
        except Exception as e:
            logger.error("Erro ao salvar job %s no Firestore: %s", job_id, e)

    def load_active_jobs(self) -> List[dict[str, Any]]:
        """
        Carrega jobs que ainda nao estao finalizados (ready/failed) ou que sao recentes.
        Inclui jobs 'ready' que ainda nao possuem download_url para retry.
        """
        db = self._get_db()
        if not db:
            return []

        try:
            jobs_ref = db.collection(COLLECTION_NAME)
            jobs = []
            
            # 1. Fetch queued, creating, polling
            active_statuses = ["queued", "creating", "polling"]
            query_active = jobs_ref.where(filter=firestore.FieldFilter("status", "in", active_statuses))
            
            for doc in query_active.stream():
                job_data = doc.to_dict()
                if job_data:
                    jobs.append(job_data)

            # 2. Fetch ready but missing download_url
            # Firestore trata None como null.
            query_incomplete = jobs_ref.where(filter=firestore.FieldFilter("status", "==", "ready"))\
                                       .where(filter=firestore.FieldFilter("download_url", "==", None))
            
            # Evitar duplicatas se algo estranho acontecer (embora status sejam exclusivos)
            existing_ids = {j.get("job_id") for j in jobs}
            
            for doc in query_incomplete.stream():
                job_data = doc.to_dict()
                if job_data and job_data.get("job_id") not in existing_ids:
                    jobs.append(job_data)
            
            logger.info("Carregados %d jobs (ativos + incompletos) do Firestore.", len(jobs))
            return jobs
        except Exception as e:
            logger.error("Erro ao carregar jobs do Firestore: %s", e)
            return []

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        db = self._get_db()
        if not db:
            return None

        try:
            doc = db.collection(COLLECTION_NAME).document(job_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error("Erro ao buscar job %s do Firestore: %s", job_id, e)
            return None

job_store = FirestoreJobStore()
