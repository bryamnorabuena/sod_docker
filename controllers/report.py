from collections import defaultdict
from fnmatch import fnmatch
import io
import json
import sys
import threading
from datetime import datetime, timedelta, timezone
from typing import DefaultDict, Iterable
import os
import time

from flask import Blueprint, request, jsonify
from sqlalchemy import and_, delete, desc, exc, func, insert, literal, or_, select, union_all
from sqlalchemy.dialects.mysql import insert as mysql_insert
from io import BytesIO
from db.database import SessionLocal
from dotenv import load_dotenv
from models import *
from config import config
from repository.conflict_repository import ConflictRepository
from repository.log_repository import LogRepository
from utils import storage
from services.nsg_service import *
from sqlalchemy import desc, select, and_, tuple_
from sqlalchemy.orm import aliased
from utils.environment import load_environment, get_environment
from typing import Iterable, Dict, Set, List, Tuple, Optional

report = Blueprint('report', __name__)

comodin = '*'

@report.route('/export', methods=['POST'])
def get_report():    
    session = SessionLocal()

    TZ_LIMA = timezone(timedelta(hours=-5))
    now = datetime.now(TZ_LIMA)

    try: 
        body = request.get_json(silent=True)
        id_version = body.get("id_version")
        type_report = body.get("type") or ''
        id_user = body.get("id_user")

        if not id_version:
            return jsonify({"error": "Falta Nombre"}), 400
        if not type_report:
            type_report = ''
        if not id_user:
            return jsonify({'error': 'Falta Id de Usuario'}), 400      

        job_id = storage.create_job()

        new_job = Job(
            IdJob = job_id,
            IdUsuario = id_user,
            Nombre = f"Reporte General Versión {id_version}" if type_report == 1 else f"Reporte Detallado Versión {id_version}",
            Tipo = "Procesamiento",
            IdAppUserCreacion = id_user,
            IdAppUserActualizacion = id_user,
            FechaCreacion = now,
            FechaActualizacion = now,
            Estado = 1
        )
        session.add(new_job)
        session.commit()
        session.expunge_all()

        input_json = {
            "id_job": job_id,
            "id_version": id_version,
            "type": type_report,
            "id_user": id_user
        }

        # 3) Autenticación a ARM con Managed Identity
        cred  = DefaultAzureCredential()
        token = cred.get_token("https://management.azure.com/.default").token

        # 4) Endpoint REST oficial para iniciar la ejecución del Job (START)        
        subscription_id = os.getenv("SUBSCRIPTION_ID")
        resource_group  = os.getenv("RESOURCE_GROUP")
        job_name        = os.getenv("REPORT_CONTAINER_NAME")
        ARM_BASE        = "https://management.azure.com"
        url = (f"{ARM_BASE}/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
               f"/providers/Microsoft.App/jobs/{job_name}/start?api-version=2025-07-01")

        body_start = {            
            "containers": [
                {
                "name": "runner",
                "image": "crsodqa.azurecr.io/aca-reports:latest",
                "env": [
                    { "name": "APP_ENV", "value": "production" },      
                    { "name": "PATH_PEM", "value": "/app/certs/mysql-ca-cert" },              
                    { "name": "INPUT_JSON", "value": json.dumps(input_json) },
                    { "name": "DB_CONNECTION", "secretRef": "db-connection-secret"},
                    { "name": "AZUREWEBJOBSTORAGE", "value": os.getenv("AZUREWEBJOBSTORAGE") },
                    { "name": "AZURESTORAGEKEY", "value": os.getenv("AZURESTORAGEKEY")},
                    { "name": "AZURE_STORAGE_CONNECTION_STRING", "value": os.getenv("AZUREWEBJOBSTORAGE")},
                    { "name": "DB_CONNECTION_TYPE", "value": os.getenv("DB_CONNECTION_TYPE", "MYSQL") }
                ]
                }
            ]
        }

        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json=body_start,
            timeout=30
        )

        # 5) Manejo de respuesta del START
        if resp.status_code not in (200, 202):
            try:
                details = resp.json()
            except Exception:
                details = {"status_code": resp.status_code, "text": resp.text[:500]}
            return jsonify({"error": "No se pudo iniciar el Job en ACA", "details": details}), 502

        azure_execution_id = None
        if resp.status_code == 200:
            azure_execution_id = resp.json().get("name")

        return jsonify({
            "jobId": job_id,                   # tu ID de tracking para el progreso
            "azureExecutionId": [azure_execution_id]  # el execution name del Job en Azure
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    except exc.SQLAlchemyError as e:
        return jsonify({"error": f"SQLALCHEMY:{e}"}), 500
    finally:
        session.close()

