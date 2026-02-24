import logging
import threading
from typing import Any, List, Optional
import os
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("byte.clips.store")

COLLECTION_NAME = "clip_jobs"

class SupabaseJobStore:
    def __init__(self) -> None:
        self._db_url = os.environ.get("SUPABASE_DB_URL")
        self._lock = threading.Lock()
        self._initialized = False
        
        if not self._db_url:
            logger.warning("SUPABASE_DB_URL nao definido. SupabaseJobStore operando em modo offline (no-op).")

    def _get_connection(self):
        if not self._db_url:
            return None
        try:
            # Tentar extrair componentes para conexao robusta sem DSN string
            if self._db_url.startswith("postgresql://"):
                url = self._db_url.split("://")[1]
                auth, rest = url.split("@")
                user, pwd = auth.split(":")
                host_port, dbname = rest.split("/")
                host, port = host_port.split(":")
                conn = psycopg2.connect(
                    user=user.strip(),
                    password=pwd.strip(),
                    host=host.strip(),
                    port=int(port),
                    database=dbname.strip(),
                    sslmode="require",
                    connect_timeout=10
                )
            else:
                conn = psycopg2.connect(self._db_url)
            
            if not self._initialized:
                self._ensure_table(conn)
            return conn
        except Exception as e:
            # Mask sensitive info for debug
            logger.error("Falha ao conectar no Supabase/Postgres (Modo Explicit Args): %s", e)
            return None

    def _ensure_table(self, conn):
        try:
            with self._lock:
                if self._initialized:
                    return
                with conn.cursor() as cur:
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {COLLECTION_NAME} (
                            job_id TEXT PRIMARY KEY,
                            status TEXT NOT NULL,
                            download_url TEXT,
                            metadata JSONB,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    conn.commit()
                self._initialized = True
        except Exception as e:
            logger.error("Erro ao criar tabela no Supabase: %s", e)

    def save_job(self, job: dict[str, Any]) -> None:
        conn = self._get_connection()
        if not conn:
            return

        job_id = job.get("job_id")
        status = job.get("status", "unknown")
        download_url = job.get("download_url")
        
        # O resto do job vira metadados JSON
        job_metadata = {k: v for k, v in job.items() if k not in ["job_id", "status", "download_url"]}

        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {COLLECTION_NAME} (job_id, status, download_url, metadata, updated_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (job_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        download_url = EXCLUDED.download_url,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP;
                """, (job_id, status, download_url, psycopg2.extras.Json(job_metadata)))
                conn.commit()
        except Exception as e:
            logger.error("Erro ao salvar job %s no Supabase: %s", job_id, e)
        finally:
            conn.close()

    def load_active_jobs(self) -> List[dict[str, Any]]:
        conn = self._get_connection()
        if not conn:
            return []

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                active_statuses = ["queued", "creating", "polling"]
                cur.execute(f"""
                    SELECT * FROM {COLLECTION_NAME} 
                    WHERE status IN %s 
                    OR (status = 'ready' AND download_url IS NULL)
                """, (tuple(active_statuses),))
                
                rows = cur.fetchall()
                jobs = []
                for row in rows:
                    job = dict(row)
                    # Mescla o JSONB de metadados de volta no dict principal para paridade com o bot
                    if job.get("metadata"):
                        meta = job.pop("metadata")
                        job.update(meta)
                    jobs.append(job)
                
                logger.info("Carregados %d jobs ativos do Supabase.", len(jobs))
                return jobs
        except Exception as e:
            logger.error("Erro ao carregar jobs do Supabase: %s", e)
            return []
        finally:
            conn.close()

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        conn = self._get_connection()
        if not conn:
            return None

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SELECT * FROM {COLLECTION_NAME} WHERE job_id = %s", (job_id,))
                row = cur.fetchone()
                if row:
                    job = dict(row)
                    if job.get("metadata"):
                        meta = job.pop("metadata")
                        job.update(meta)
                    return job
                return None
        except Exception as e:
            logger.error("Erro ao buscar job %s no Supabase: %s", job_id, e)
            return None
        finally:
            conn.close()

job_store = SupabaseJobStore()
