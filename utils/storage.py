import json
import os
from azure.data.tables import TableServiceClient, UpdateMode
from azure.storage.blob import BlobServiceClient
from utils.environment import load_environment, get_environment
from uuid import uuid4
from utils.helper import Helper

CONNECTION_STRING = get_environment("AZUREWEBJOBSTORAGE")
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

