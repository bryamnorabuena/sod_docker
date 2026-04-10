from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
from db.database import SessionLocal
from services.nsg_service import *
from utils.security import verify_password
from utils.storage import list_all_jobs
from models import Job as job_bd

job_ = Blueprint('job', __name__)

TZ_LIMA = timezone(timedelta(hours=-5))

@job_.route("/", methods=["GET"])
def getAll():
    if request.method == 'OPTIONS':
        # El after_request de CORS ya pondrá los headers; responde 204 sin redirigir
        return ('', 204)
    session = SessionLocal()
    
    try:
        jobs_TS_original = list_all_jobs()
        jobs_TS = { list(d.keys())[0]: list(d.values())[0] for d in jobs_TS_original }
        print("Total:", len(jobs_TS))

        jobs_BD = session.query(job_bd).order_by(job_bd.FechaActualizacion.desc()).all()

        jobs = []
        for j in jobs_BD:
            a = jobs_TS.get(j.IdJob)
            if a is not None:
                jobs.append(
                    {
                        "Id": j.Id,
                        "IdJob": j.IdJob,
                        "IdUser": j.IdUsuario,
                        "Type": j.Tipo,
                        "Name": j.Nombre,
                        "Time": a['timestamp'],
                        "Progress": a['progress'],
                        "Status": a["status"],
                        "UrlReport": j.UrlReporte,
                        "Errors": a["errors"]
                    }
                )


        return jsonify(jobs), 200
    except Exception as e:
        return jsonify({"error": e}), 500
    finally:
        session.close()
