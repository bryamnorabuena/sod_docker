
import os
import sys
import time
import socket
import traceback
from datetime import datetime, timedelta, timezone

from azure.data.tables import TableServiceClient, UpdateMode
from azure.core.exceptions import ResourceModifiedError
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
    

# Importa tu función pesada desde tu proyecto
# Ajusta el import según tu estructura real:
from controllers.conflict import process_excute_php
from utils import storage  # si quieres reusar update_progress/complete/fail

POLL_SECONDS = int(os.getenv("WORKER_POLL_SECONDS", "5"))
CONN_STR = os.getenv("AZUREWEBJOBSTORAGE")
TABLE_NAME = "AnalysisProgress"

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
LOCK_MINUTES = int(os.getenv("JOB_LOCK_MINUTES", "30"))

if not CONN_STR:
    raise RuntimeError("Falta AZUREWEBJOBSTORAGE en variables de entorno.")

service = TableServiceClient.from_connection_string(CONN_STR)
table = service.get_table_client(TABLE_NAME)


def now_utc():
    return datetime.now(timezone.utc)


def claim_job(entity):
    """
    Intenta 'tomar' el job usando control de concurrencia (ETag).
    Si otro worker lo toma primero, Azure lanzará ResourceModifiedError.
    """
    # Requiere que el entity venga con etag
    etag = entity.metadata.get("etag") if hasattr(entity, "metadata") else entity.get("_etag")
    # En azure-data-tables, el etag suele venir en entity.metadata.etag o entity['etag'] según versión.
    # Para robustez, intentamos varios:
    if etag is None:
        etag = getattr(getattr(entity, "metadata", None), "etag", None) or entity.get("etag")

    lock_until = (now_utc() + timedelta(minutes=LOCK_MINUTES)).isoformat()

    entity["Status"] = "running"
    entity["LockedBy"] = WORKER_ID
    entity["LockUntil"] = lock_until
    entity["UpdatedAt"] = now_utc().isoformat()

    # Update con ETag: si cambió, falla => otro worker lo tomó
    table.update_entity(mode=UpdateMode.MERGE, entity=entity, etag=etag)


def find_one_queued_job():
    # Filtra por PartitionKey conflict y Status Queued
    # Ajusta si usas otros valores.
    query = "PartitionKey eq 'Conflicts' and Status eq 'queued'"
    entities = table.query_entities(query_filter=query, results_per_page=1)

    for e in entities:
        return e
    return None


def run_job(job_entity):
    job_id = job_entity["RowKey"]
    id_version = job_entity.get("Version")
    user_id = job_entity.get("User")

    # Si decides guardar token en el job:
    token = job_entity.get("Token")  # Opción A
    # Si no guardas token, esto será None y tu función no ejecutará.
    # En ese caso, debes ajustar el diseño (Opción B).

    try:
        # Puedes reusar tus helpers si ya existen
        storage.update_progress(job_id, 10)

        ok = process_excute_php(token=token, id_version=id_version, job_id=job_id, user_id=user_id)

        if ok:
            storage.complete_job(job_id)
        elif isinstance(ok, list):
            storage.update_job_with_errors(job_id, ok)
            storage.fail_job(job_id)
        else:
            storage.fail_job(job_id)

    except Exception as ex:
        err = f"{ex}\n{traceback.format_exc()}"
        try:
            storage.update_job_with_errors(job_id, [err])
        except Exception:
            pass
        try:
            storage.fail_job(job_id)
        except Exception:
            pass


def main():
    print(f"[{now_utc().isoformat()}] Worker iniciado: {WORKER_ID} - Table={TABLE_NAME}")

    while True:
        try:
            job = find_one_queued_job()
            if not job:
                time.sleep(POLL_SECONDS)
                continue

            # Intentar tomar el job (lock)
            try:
                claim_job(job)
            except ResourceModifiedError:
                # otro worker ganó el lock
                continue

            print(f"[{now_utc().isoformat()}] Procesando Job: {job['RowKey']}")
            run_job(job)

        except Exception as e:
            print(f"[{now_utc().isoformat()}] Error en worker loop: {e}")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()