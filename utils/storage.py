from datetime import datetime, timedelta, timezone
import json
import os
from zoneinfo import ZoneInfo
from azure.data.tables import TableServiceClient, UpdateMode
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.storage.blob import BlobClient
from base64 import b64decode
from models.version import Version
from utils.environment import load_environment, get_environment
from uuid import uuid4
from utils.helper import Helper

from typing import Dict, Any, List, Optional, Tuple
from azure.data.tables import TableServiceClient
from utils.environment import get_environment


CONNECTION_STRING = get_environment("AZUREWEBJOBSTORAGE")
KEY = get_environment("AZURESTORAGEKEY")
TABLE_NAME = "SodProgress"

def get_table_client():
    service = TableServiceClient.from_connection_string(CONNECTION_STRING)
    #cservice.create_table_if_not_exists(TABLE_NAME)  # esto es correcto
    table_client = service.get_table_client(table_name=TABLE_NAME)
    return table_client

def create_job():
    job_id = str(uuid4())
    client = get_table_client()
    client.create_entity({
        'PartitionKey': 'Jobs',
        'RowKey': job_id,
        'Progress': 0,
        'Status': 'running'
    })
    return job_id

def create_job_conflict(version, user):
    job_id = str(uuid4())
    client = get_table_client()
    client.create_entity({
        'PartitionKey': 'Conflicts',
        'RowKey': job_id,
        'Progress': 0,
        'Status': 'queued',
        'Version': version,
        'User': user
    })
    return job_id

def update_progress(job_id, progress):
    client = get_table_client()
    client.update_entity({
        'PartitionKey': 'Jobs',
        'RowKey': job_id,
        'Progress': progress,
        'Status': 'running'
    }, mode=UpdateMode.MERGE)

def complete_job(job_id):
    client = get_table_client()
    entity = client.get_entity('Jobs', job_id)
    entity['Status'] = 'complete'
    entity['Progress'] = 100
    client.update_entity(entity, mode=UpdateMode.REPLACE)

def fail_job(job_id):
    client = get_table_client()
    entity_update = {
        'PartitionKey': 'Jobs',
        'RowKey': job_id,
        'Status': 'error'
    }
    client.update_entity(entity_update, mode=UpdateMode.MERGE)

def get_status(job_id):
    client = get_table_client()
    try:
        entity = client.get_entity('Jobs', job_id)
        return {
            "progress": entity.get("Progress", 0),
            "errors": json.loads(entity.get("Errors", "null")),
            "status": entity.get("Status", "unknown")
        }
    except:
        return None
    
def update_job_with_errors(job_id, errors):
    try:
        # Preparar los errores para almacenamiento
        error_data = Helper().prepare_errors(errors) if errors else None

        client = get_table_client()
        client.update_entity({
            'PartitionKey': 'Jobs',
            'RowKey': job_id,
            'Status': "error" if errors else "complete",
            'Errors': json.dumps(error_data) if error_data else None
        }, mode=UpdateMode.MERGE)
    except Exception as e:
        print(f"Error al actualizar job: {str(e)}")
        raise
    
def create_blob_container(container_name):
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container_client = blob_service_client.create_container(container_name)
    return container_client

def upload_zip_and_get_url(base64_zip, job_id):
    zip_bytes = b64decode(base64_zip)
    blob_name = f"mastersap/{job_id}.zip"

    blob = BlobClient.from_connection_string(
        conn_str=CONNECTION_STRING,
        container_name="inputs",
        blob_name=blob_name
    )
    blob.upload_blob(zip_bytes, overwrite=True)

    # URL pública o SAS    
    sas_token = generate_blob_sas(
        account_name=blob.account_name,
        container_name="inputs",
        blob_name=blob_name,
        account_key=KEY,   # Necesitas la Storage Account Key
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now() + timedelta(hours=12)  # válido por 12
    )

    # 6. URL completa (lista para pasar al Job)
    sas_url = f"{blob.url}?{sas_token}"
    return sas_url



def _entity_to_job_dict(entity) -> Dict[str, Any]:
    """
    Normaliza la entidad de Table Storage a un dict para tu API/UI.
    Agrega defaults por si faltan propiedades.
    """
    ts_utc = entity.metadata.get("timestamp")
    ts_lima = ts_utc.astimezone(ZoneInfo("America/Lima"))
    iso_lima_ms = ts_lima.replace(microsecond=(ts_lima.microsecond // 1000) * 1000).isoformat()
    return {
        "partitionKey": entity.get("PartitionKey"),
        "jobId": entity.get("RowKey"),
        "progress": entity.get("Progress", 0),
        "status": entity.get("Status", "unknown"),
        "errors": entity.get("Errors"),  # puede ser None o JSON string
        "version": entity.get("Version"), # para conflicts
        "user": entity.get("User"),       # para conflicts
        "timestamp": iso_lima_ms,  # datetime con tz
    }


def list_jobs_page(
    page_size: int = 50,
    continuation_token: Optional[Tuple[Optional[str], Optional[str]]] = None,
    select: Optional[List[str]] = None,
):
    """
    Lista una página de Jobs (PartitionKey == 'Jobs').

    Params:
      - page_size: tamaño de página (máx razonable ~1000)
      - continuation_token: (next_pk, next_rk) devuelto por una llamada previa
      - select: lista de columnas a proyectar (opcional)

    Return:
      {
        "items": [ {job...}, ... ],
        "next_token": (next_pk, next_rk) | None,
        "count": int
      }
    """
    client = get_table_client()
    filter_expr = "PartitionKey eq 'Jobs'"

    # continuation_token es tupla (next_partition_key, next_row_key)
    next_pk, next_rk = continuation_token if continuation_token else (None, None)

    pager = client.query_entities(
        query_filter=filter_expr,
        select=select,
        results_per_page=page_size
    ).by_page(continuation_token={"PartitionKey": next_pk, "RowKey": next_rk} if next_pk or next_rk else None)

    items: List[Dict[str, Any]] = []
    next_token: Optional[Tuple[Optional[str], Optional[str]]] = None

    try:
        page = next(pager)  # toma la primera página
        for ent in page:
            items.append(_entity_to_job_dict(ent))

        # IMPORTANTE: Azure SDK expone tokens en propiedades del pager
        # dependiendo de la versión; obtenemos del objeto interno:
        if hasattr(pager, "continuation_token"):
            ct = pager.continuation_token or {}
            npk = ct.get("PartitionKey")
            nrk = ct.get("RowKey")
            if npk or nrk:
                next_token = (npk, nrk)
    except StopIteration:
        # no hay resultados
        pass

    # Orden local (recientes primero por Timestamp) — opcional
    # Ojo: Timestamp puede venir con tz; sort estable
    items.sort(key=lambda x: x.get("timestamp") or datetime.min, reverse=True)

    return {
        "items": items,
        "next_token": next_token,
        "count": len(items),
    }

def list_all_jobs(
    batch_size: int = 1000,
    select: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Trae todos los Jobs. Usa paginación interna hasta agotar.
    Ordena en memoria por Timestamp DESC.
    """
    client = get_table_client()
    filter_expr = "PartitionKey eq 'Jobs'"
    all_items: List[Dict[str, Any]] = []

    pager = client.query_entities(
        query_filter=filter_expr,
        select=select,
        results_per_page=batch_size
    ).by_page()

    for page in pager:
        for ent in page:
            row = {}
            ent = _entity_to_job_dict(ent)
            row[ent["jobId"]] = ent
            all_items.append(row)

    all_items.sort(key=lambda x: x.get("timestamp") or datetime.min, reverse=True)
    return all_items

def upload_to_blob(local_path: str, tipo: int, version: Version):
    """
    tipo = 1 → General
    tipo = 2 → Detallado
    """
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = "reports"

    blob_service = BlobServiceClient.from_connection_string(conn_str)
    container = blob_service.get_container_client(container_name)

    # Subcarpeta según tipo
    subfolder = "general" if tipo == 1 else "detailed"

    # Nombre bonito del archivo
    fecha_str = datetime.now().strftime("%Y%m%d")
    tipo_nombre = "General" if tipo == 1 else "Detallado"

    blob_name = f"{subfolder}/Reporte {tipo_nombre} Versión {version.Id} {fecha_str}.csv"

    # Subir archivo
    with open(local_path, "rb") as data:
        container.upload_blob(blob_name, data, overwrite=True)

    # ✅ Obtener credenciales internas para generar SAS
    account_name = blob_service.account_name
    account_key = blob_service.credential.account_key

    # ✅ Generar URL SAS
    sas_url = generate_sas_url(
        account_name=account_name,
        account_key=account_key,
        container_name=container_name,
        blob_name=blob_name
    )

    print("\n✅ Archivo subido correctamente a Azure Blob Storage")
    print("✅ SAS URL lista para el usuario:")
    print(sas_url)
    
    try:
        os.remove(local_path)
        print(f"🧹 Archivo temporal eliminado: {local_path}")
    except:
        print(f"⚠ No se pudo borrar el archivo temporal: {local_path}")


    return sas_url

def generate_sas_url(account_name: str, account_key: str, container_name: str, blob_name: str):
    """
    Genera un SAS URL válido por 24 horas para permitir descarga del archivo.
    Storage Account sigue privado, esto es seguro.
    """
    
    TZ_LIMA = timezone(timedelta(hours=-5))
    now = datetime.now(TZ_LIMA)

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry= now + timedelta(24)  # válido por 24 horas
    )

    sas_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"

    return sas_url



