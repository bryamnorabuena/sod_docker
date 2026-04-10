from collections import defaultdict
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
import jwt
from sqlalchemy import and_, or_
from db.database import SessionLocal
from services.nsg_service import *
from models import *
from utils.security import verify_password
from werkzeug.security import generate_password_hash

from models.rol import Rol
from models.appuser import AppUser
from models.appuserrol import AppUserRol
from sqlalchemy.orm import joinedload
from utils.security import hash_password_bcrypt

user = Blueprint('user', __name__)

SECRET_KEY = "1234"
TZ_LIMA = timezone(timedelta(hours=-5))

@user.route("/", methods=['GET'])
def fetchAll():
    if request.method == 'OPTIONS':
        # El after_request de CORS ya pondrá los headers; responde 204 sin redirigir
        return ('', 204)

    db = SessionLocal()
    try:
        users = (
            db.query(
                AppUser,
                AppUserRol,
                Rol
            )
            .outerjoin(AppUserRol, AppUserRol.IdAppUser == AppUser.Id)
            .outerjoin(Rol, Rol.Id == AppUserRol.IdRol)
            .all()
        )


        
        users_dict = defaultdict(lambda: {
                "Id": None,
                "Nombre": "",
                "Apellidos": "",
                "UserName": "",
                "Email": "",
                "Activo": False,
                "FechaCreacion": None,
                "FechaActualizacion": None,
                "Estado": False,
                "Roles": []
            })

        for user, user_rol, rol_data in users:
            if users_dict[user.Id]["Id"] is None:
                users_dict[user.Id].update({
                    "Id": user.Id,
                    "Nombre": user.Nombre,
                    "Apellidos": user.Apellidos,
                    "UserName": user.UserName,
                    "Email": user.Email,
                    "Activo": bool(user.Activo),
                    "FechaCreacion": user.FechaCreacion,
                    "FechaActualizacion": user.FechaActualizacion,
                    "Estado": bool(user.Estado),
                })

            if user_rol:
                users_dict[user.Id]["Roles"].append({
                    "Id": user_rol.Id,
                    "IdAppUser": user_rol.IdAppUser,
                    "IdRol": user_rol.IdRol,
                    "Nombre": rol_data.Nombre,
                    "Role": rol_data.Role,
                    "IdAppUserCreacion": user_rol.IdAppUserCreacion,
                    "FechaCreacion": user_rol.FechaCreacion,
                    "FechaActualizacion": user_rol.FechaActualizacion,
                    "Estado": bool(user_rol.Estado),
                })
        
        
        return jsonify(list(users_dict.values())), 200
    except Exception as e:
        return jsonify({"error": "Error de servidor"}), 500
    finally:
        db.close()

@user.route("/<int:id_target>", methods=["GET"])
def handle_get_user(id_target):
    id_user = int(request.args.get("id_user"))
    return get_user_by_id(id_target, id_user)

def get_user_by_id(id_target, id_user):
    # ----------------------------------------------
    # 1. Obtener roles del usuario que hace la solicitud
    # ----------------------------------------------
    session = SessionLocal()
    ADMIN_ROLE = int(os.getenv("ADMIN_ROLE", 1))

    requester_rows = (
        session.query(AppUserRol)
        .filter(AppUserRol.IdAppUser == id_user)
        .all()
    )

    requester_roles = [r.IdRol for r in requester_rows]

    # Validar si es admin
    is_admin = ADMIN_ROLE in requester_roles

    # ----------------------------------------------
    # 2. Obtener datos del usuario objetivo (sin roles aún)
    # ----------------------------------------------
    target_user = (
        session.query(AppUser)
        .filter(AppUser.Id == id_target)
        .first()
    )

    if not target_user:
        return jsonify({
            "error": "Usuario no encontrado"
        }), 404

    # ----------------------------------------------
    # 3. Construir respuesta base
    # ----------------------------------------------
    user_base_data = {
        "Id": target_user.Id,
        "Nombre": target_user.Nombre,
        "Apellidos": target_user.Apellidos,
        "UserName": target_user.UserName,
        "Email": target_user.Email,
        "Activo": bool(target_user.Activo),
        "FechaCreacion": target_user.FechaCreacion,
        "FechaActualizacion": target_user.FechaActualizacion,
        "Estado": bool(target_user.Estado)
    }

    # ----------------------------------------------
    # 4. Si NO es admin → devolver solo datos del usuario
    # ----------------------------------------------
    if not is_admin:
        return jsonify(user_base_data), 200

    # ----------------------------------------------
    # 5. Si ES admin → obtener también roles del usuario objetivo
    # ----------------------------------------------
    rows = (
        session.query(AppUser, AppUserRol, Rol)
        .outerjoin(AppUserRol, AppUserRol.IdAppUser == AppUser.Id)
        .outerjoin(Rol, Rol.Id == AppUserRol.IdRol)
        .filter(AppUser.Id == id_target)
        .all()
    )

    roles_list = []

    for _, role_item, role_info in rows:
        if role_item:
            roles_list.append({
                "Id": role_item.Id,
                "IdAppUser": role_item.IdAppUser,
                "IdRol": role_item.IdRol,
                "Nombre": role_info.Nombre,
                "IdAppUserCreacion": role_item.IdAppUserCreacion,
                "FechaCreacion": role_item.FechaCreacion,
                "FechaActualizacion": role_item.FechaActualizacion,
                "Estado": bool(role_item.Estado)
            })

    user_base_data["Roles"] = roles_list

    return jsonify(user_base_data), 200

@user.route("/create", methods=["POST"])
def create():
    db = SessionLocal()

    try:
        data = request.get_json()

        required = ["Nombre", "Apellidos", "UserName", "Email", "Password"]
        for field in required:
            if field not in data:
                raise ValueError(f"Falta el campo {field}")        

        # Validar duplicados
        exists = db.query(AppUser).filter(
            (AppUser.Email == data["Email"]) |
            (AppUser.UserName == data["UserName"])
        ).first()

        if exists:
            raise ValueError("Email o Username ya existe")

        # Crear nuevo usuario
        new_user = AppUser(
            Nombre=data["Nombre"],
            Apellidos=data["Apellidos"],
            UserName=data["UserName"],
            Email=data["Email"],
            Password=hash_password_bcrypt(data["Password"]),
            Activo=data.get("Activo", 1),
            Estado=data.get("Estado", 1),
            FechaCreacion=datetime.now(TZ_LIMA),
            FechaActualizacion=datetime.now(TZ_LIMA)
        )

        db.add(new_user)
        db.commit()

        return jsonify({"success":True, "message": "Usuario creado correctamente"}), 200
    except Exception as e:
        return jsonify({"success":False, "message": str(e)})
    finally:
        db.close()

@user.route("/update", methods=["PUT"])
def update():
    db = SessionLocal()
    try:
        data = request.get_json()        

        user = db.query(AppUser).get(data.get("Id"))
        if not user:
            raise ValueError("Usuario no encontrado")

        # Validar email/username duplicado por otro usuario
        exists = db.query(AppUser).filter(
            and_(
                AppUser.Id != data.get("Id"),
                (AppUser.Email == data.get("Email")) |
                (AppUser.UserName == data.get("UserName"))
            )
        ).first()

        if exists:
            raise ValueError("Email o Username ya está usado por otro usuario")

        # Actualizar campos
        user.Nombre = data.get("Nombre", user.Nombre)
        user.Apellidos = data.get("Apellidos", user.Apellidos)
        user.UserName = data.get("UserName", user.UserName)
        user.Email = data.get("Email", user.Email)
        user.Activo = data.get("Activo", user.Activo)
        user.Estado = data.get("Estado", user.Estado)
        user.FechaActualizacion = datetime.now(TZ_LIMA)

        db.commit()

        return jsonify({"success":True, "message": "Usuario actualizado correctamente"}), 200
    except Exception as e:
        return jsonify({"success":False, "message": str(e)})
    finally:
        db = SessionLocal()

@user.route("/delete/<int:id>", methods=["DELETE"])
def delete_user(id):
    db = SessionLocal()

    try:
        user = db.query(AppUser).filter(AppUser.Id == id).first()

        if not user:
            raise ValueError("Usuario no encontrado")

        user.Activo = 0
        user.Estado = 0
        user.FechaActualizacion = datetime.now(TZ_LIMA)

        db.commit()

        return jsonify({"success": True, "message": "Usuario deshabilitado correctamente"}), 200
    except Exception as e:
        return jsonify({"success":False, "message": str(e)})
    finally:
        db.close()

@user.route("/roles/<int:id_user>", methods=["GET"])
def get_roles_by_user(id_user):
    db = SessionLocal()

    try:
        roles_list = []
        
        subquery = (
            db.query(AppUserRol.IdRol)
            .filter(AppUserRol.IdAppUser == id_user)
            .subquery()
        )

        roles = (
            db.query(Rol.Id, Rol.Nombre, Rol.Role)
            .filter(
                Rol.Estado == 1,
                ~Rol.Id.in_(subquery)
            )
            .order_by(Rol.Nombre)
            .all()
        )


        for rol in roles:
            roles_list.append({
                "Id": rol.Id,        
                "IdRol": rol.Id,
                "Nombre": rol.Nombre,
                "Role": rol.Role                
            })
            

        return jsonify(roles_list), 200
    except Exception as e:
        return jsonify({"success":False, "message": str(e)})
    finally:
        db.close()


@user.route("/roles/add", methods=["POST"])
def add_roles():
    db = SessionLocal()

    try:
        data = request.get_json()

        id_user = data["IdAppUser"]
        roles = data["roles"]
        id_creator = data["IdAppUserCreacion"]

        if not roles:
            return jsonify({"success": False, "message": "No hay roles para asignar"})

        # 🔹 Roles ya asignados al usuario
        existing_roles = db.query(AppUserRol.IdRol).filter(
            AppUserRol.IdAppUser == id_user,
            AppUserRol.IdRol.in_(roles),
            AppUserRol.Estado == 1
        ).all()

        existing_role_ids = {r.IdRol for r in existing_roles}

        new_roles = [
            AppUserRol(
                IdAppUser=id_user,
                IdRol=role_id,
                IdAppUserCreacion=id_creator,
                IdAppUserActualizacion=id_creator,
                FechaCreacion=datetime.now(TZ_LIMA),
                FechaActualizacion=datetime.now(TZ_LIMA),
                Estado=1
            )
            for role_id in roles
            if role_id not in existing_role_ids
        ]

        if not new_roles:
            return jsonify({
                "success": False,
                "message": "Todos los roles ya estaban asignados"
            })

        db.add_all(new_roles)
        db.commit()

        return jsonify({
            "success": True,
            "message": "Roles asignados correctamente"
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        db.close()
