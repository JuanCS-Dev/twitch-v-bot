import logging
import threading
import time
from typing import Any, List, Optional

from google.cloud import firestore
from bot.control_plane_constants import utc_iso
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
        Para simplificar, carrega todos com status != ready e != failed.
        """
        db = self._get_db()
        if not db:
            return []

        try:
            jobs_ref = db.collection(COLLECTION_NAME)
            # Query: status not in ['ready', 'failed'] is not directly supported by Firestore
            # We can use multiple queries or just fetch active ones by status
            
            # Simple approach: Fetch queued, creating, polling
            active_statuses = ["queued", "creating", "polling"]
            # Note: Firestore 'in' query supports up to 10 values
            query = jobs_ref.where(filter=firestore.FieldFilter("status", "in", active_statuses))
            
            docs = query.stream()
            jobs = []
            for doc in docs:
                job_data = doc.to_dict()
                if job_data:
                    jobs.append(job_data)
            
            logger.info("Carregados %d jobs ativos do Firestore.", len(jobs))
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
