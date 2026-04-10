from collections import defaultdict
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
import jwt
from sqlalchemy import and_, func, or_
from db.database import SessionLocal
from services.nsg_service import *
from models import *
from utils.security import verify_password
from werkzeug.security import generate_password_hash

from models.rol import Rol
from models.appuser import AppUser
from models.appuserrol import AppUserRol
from sqlalchemy.orm import joinedload

dashboard = Blueprint('dashboard', __name__)

TZ_LIMA = timezone(timedelta(hours=-5))

@dashboard.route("/stats", methods=['GET'])
def fetchAll():
    if request.method == 'OPTIONS':
        # El after_request de CORS ya pondrá los headers; responde 204 sin redirigir
        return ('', 204)

    db = SessionLocal()
    try:
        rules = (
            db.query(func.count(Regla.Id)).filter(
            Regla.Estado == 1)
        ).scalar()
        mastersap = (
            db.query(func.count(MatrizSap.Id)).filter(
                MatrizSap.Estado == 1
            )
        ).scalar()
        versions_processed = (
                db.query(func.count(Version.Id)).filter(
                Version.Estado == 1, Version.Procesado == 1
            )
        ).scalar()
        versions = (
                db.query(func.count(Version.Id)).filter(
                Version.Estado == 1
            )
        ).scalar()

        dashboard_stats = {
            "qty_rules": rules,
            "qty_mastersap": mastersap,
            "qty_versions_processed": versions_processed,
            "qty_versions_total": versions
        }
        
        return jsonify(dashboard_stats), 200
    except Exception as e:
        return jsonify({"success":False, "message": str(e)})
    finally:
        db.close()
