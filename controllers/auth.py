from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
import jwt
from sqlalchemy import or_
from db.database import SessionLocal
from services.nsg_service import *
from models import *
from utils.security import verify_password

auth = Blueprint('auth', __name__)

SECRET_KEY = "1234"
TZ_LIMA = timezone(timedelta(hours=-5))

@auth.route("/login", methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        # El after_request de CORS ya pondrá los headers; responde 204 sin redirigir
        return ('', 204)

    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    
    if not username or not password:
        return jsonify({"error": "Usuario y contraseña son requeridos"}), 400
    
    db = SessionLocal()
    try:
        # Permite login por UserName o Email
        user = db.query(AppUser.Id,
                        AppUser.UserName,
                        AppUser.Password,
                        AppUser.Email,
                        AppUser.Estado,
                        AppUserRol.IdRol).join(AppUserRol, AppUserRol.IdAppUser == AppUser.Id).filter(or_(AppUser.UserName == username, AppUser.Email == username)).first()

        # Respuesta genérica para no filtrar usuarios existentes
        if not user:
            return jsonify({"error": "Credenciales inválidas"})

        # Verifica flags
        if not (user.Estado == 1):
            return jsonify({"error": "Usuario deshabilitado"})        

        # Verifica contraseña (bcrypt $2y$)
        if not verify_password(password, user.Password):
            return jsonify({"error": "Credenciales inválidas"})

        # Genera JWT (exp 4h, en UTC)
        now_utc = datetime.now(timezone.utc)
        exp_utc = now_utc + timedelta(hours=4)

        token = jwt.encode(
            {
                "id_user": str(user.Id),
                "id_rol": user.IdRol,
                "username": user.UserName,
                "exp": exp_utc
            },
            SECRET_KEY,
            algorithm="HS256",
        )

        return jsonify({
            "token": token,
            "id_user": str(user.Id),
            "id_rol": user.IdRol,
            "username": user.UserName,
            "exp": exp_utc
        })
    except Exception as e:
        return jsonify({"error": "Error de servidor"}), 500
    finally:
        db.close()

