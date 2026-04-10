from collections import defaultdict
from fnmatch import fnmatch
import io
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

process = Blueprint('process', __name__)

comodin = '*'

@process.route('/newprocess', methods=['POST'])
def new_Process():
    try:        
        TZ_LIMA = timezone(timedelta(hours=-5))
        now = datetime.now(TZ_LIMA)
        
        body = request.get_json(silent=True)
        rule_id = body.get("idrule")
        matrixsap_id = body.get("idmatrixsap")
        name = body.get("name")
        description = body.get("description") or ''
        limit_date = body.get("limitdate")
        user_id = body.get("iduser")

        if not rule_id:
            return jsonify({"error": "Falta Regla"}), 400
        if not matrixsap_id:
            return jsonify({"error": "Falta Matriz SAP"}), 400
        if not name:
            return jsonify({"error": "Falta Nombre"}), 400
        if not description:
            description = ''
        if not user_id:
            return jsonify({'error': 'Falta Id de Usuario'}), 400      

        job_id = storage.create_job()

        def run():
            MAX_ATTEMPTS = 3

            try:
                storage.update_progress(job_id, 10)
                
                response = create(job_id, rule_id, matrixsap_id, name, description, user_id, limit_date)
                                    
                print(f"Termina llamada a función set_sod_matrix")

                if response:
                    storage.complete_job(job_id)
                    return                                                                    
                else:
                    storage.fail_job(job_id)
                    return                        
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

                error_msg = f"Error para job {job_id}: {e} en {fname}:{exc_tb.tb_lineno}"

                storage.update_job_with_errors(job_id, [error_msg])
                storage.fail_job(job_id)
                print(f"Error FINAL en job {job_id}: {e}")
                return
                
                    
        threading.Thread(target=run).start()

        return jsonify({"jobId": job_id}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    except exc.SQLAlchemyError as e:
        return jsonify({"error": f"SQLALCHEMY:{e}"}), 500

def create(job_id, rule_id, matrixsap_id, name, description, user_id, limit_date):
    session = SessionLocal()

    try:        
        TZ_LIMA = timezone(timedelta(hours=-5))
        now = datetime.now(TZ_LIMA)
        
        campo_transaccion = config.TRANSACTION_OBJECT
        progress = 0
        HISTORY = 0

        new_job = Job(
            IdJob = job_id,
            IdUsuario = user_id,
            Nombre = name,
            Tipo = "Procesamiento",
            IdAppUserCreacion = user_id,
            IdAppUserActualizacion = user_id,
            FechaCreacion = now,
            FechaActualizacion = now,
            Estado = 1
        )
        session.add(new_job)
        session.commit()
        session.expunge_all()

        proceso = Proceso()
        proceso.IdRegla = rule_id
        proceso.IdMatrizSap = matrixsap_id
        proceso.Nombre = name
        proceso.Descripcion = ''
        proceso.FechaCorte = limit_date if limit_date else None
        proceso.IdAppUserCreacion = user_id
        proceso.IdAppUserActualizacion = user_id
        proceso.FechaCreacion = now
        proceso.FechaActualizacion = now
        proceso.Estado = 1
        session.add(proceso)
        session.flush()

        progress += 20
        storage.update_progress(job_id, progress)

        # 1. Obtener Objeto Proceso
        sap_objeto_proceso = session.scalar(
            select(SapObjetoProceso)
            .filter_by(IdMatrizSap=proceso.IdMatrizSap, Nombre=campo_transaccion, Estado=True)
        )

        
        if not sap_objeto_proceso:
            return {"error": "No existe SapObjetoProceso para esa matriz y objeto"}, 400
        
        params = {
            "id_proceso": proceso.Id,
            "id_regla": proceso.IdRegla,
            "id_obj_proceso": sap_objeto_proceso.Id,
            "id_matriz": proceso.IdMatrizSap,
            "uid": user_id,
        }

        conn = session.connection()   

        #exactos
        print("Validando Exactos...")
        sql = "CALL sp_exactos_select(%s,%s,%s)"    
        
        params = (
            proceso.IdMatrizSap,      # 4) p_IdMatrizSap
            sap_objeto_proceso.Id,    # 5) p_IdSapObjetoProceso
            proceso.IdRegla           # 6) p_IdRegla
        )

        BATCH_LIMIT = 5000
        BATCH = []

        result = conn.exec_driver_sql(sql, params)            
        if result.returns_rows:
                rows = result.fetchall()
                now = datetime.now()
                for item in rows:
                    BATCH.append({
                        "IdProceso": proceso.Id,
                        "IdUsuario": item[0],
                        "IdTransaccion": item[1],
                        "IdAppUserCreacion": user_id,
                        "IdAppUserActualizacion": user_id,
                        "FechaCreacion": now,
                        "FechaActualizacion": now,
                        "Estado": 1
                    })

                    if len(BATCH) > BATCH_LIMIT:
                        uniq = {}
                        for it in BATCH:
                            key = (it['IdProceso'], it['IdUsuario'], it['IdTransaccion'])
                            if key not in uniq:
                                uniq[key] = it
                        dedup_items = list(uniq.values())
                        HISTORY += len(dedup_items)
                        print(f"Registros Insertados: {str(HISTORY)}")

                        # Opción A: IGNORE
                        stmt = mysql_insert(UsuarioTransaccion).values(dedup_items).prefix_with("IGNORE")
                        session.execute(stmt)
                        BATCH = []                            
                if len(BATCH) > 0:
                    uniq = {}
                    for it in BATCH:
                        key = (it['IdProceso'], it['IdUsuario'], it['IdTransaccion'])
                        if key not in uniq:
                            uniq[key] = it
                    dedup_items = list(uniq.values())
                    HISTORY += len(dedup_items)
                    print(f"Registros Insertados: {str(HISTORY)}")

                    # Opción A: IGNORE
                    stmt = mysql_insert(UsuarioTransaccion).values(dedup_items).prefix_with("IGNORE")
                    session.execute(stmt)
                    BATCH = []
        result.close()

        progress += 25
        storage.update_progress(job_id, progress)

        #prefijos
        print("Validando Prefijos...")
        sql = "CALL sp_prefijos_select(%s,%s,%s)"    
        
        params = (
            proceso.IdMatrizSap,      # 4) p_IdMatrizSap
            sap_objeto_proceso.Id,    # 5) p_IdSapObjetoProceso
            proceso.IdRegla           # 6) p_IdRegla
        )

        BATCH_LIMIT = 5000
        BATCH = []

        result = conn.exec_driver_sql(sql, params)            
        if result.returns_rows:
                rows = result.fetchall()
                now = datetime.now()
                for item in rows:
                    BATCH.append({
                        "IdProceso": proceso.Id,
                        "IdUsuario": item[0],
                        "IdTransaccion": item[1],
                        "IdAppUserCreacion": user_id,
                        "IdAppUserActualizacion": user_id,
                        "FechaCreacion": now,
                        "FechaActualizacion": now,
                        "Estado": 1
                    })

                    if len(BATCH) > BATCH_LIMIT:
                        uniq = {}
                        for it in BATCH:
                            key = (it['IdProceso'], it['IdUsuario'], it['IdTransaccion'])
                            if key not in uniq:
                                uniq[key] = it
                        dedup_items = list(uniq.values())
                        HISTORY += len(dedup_items)
                        print(f"Registros Insertados: {str(HISTORY)}")

                        # Opción A: IGNORE
                        stmt = mysql_insert(UsuarioTransaccion).values(dedup_items).prefix_with("IGNORE")
                        session.execute(stmt)
                        BATCH = []                            
                if len(BATCH) > 0:
                    uniq = {}
                    for it in BATCH:
                        key = (it['IdProceso'], it['IdUsuario'], it['IdTransaccion'])
                        if key not in uniq:
                            uniq[key] = it
                    dedup_items = list(uniq.values())
                    HISTORY += len(dedup_items)
                    print(f"Registros Insertados: {str(HISTORY)}")

                    # Opción A: IGNORE
                    stmt = mysql_insert(UsuarioTransaccion).values(dedup_items).prefix_with("IGNORE")
                    session.execute(stmt)
                    BATCH = []
        result.close()

        progress += 25
        storage.update_progress(job_id, progress)
    

        #complejos
        print("Validando Complejos...")
        sql = "CALL sp_complejos_select(%s,%s,%s)"    
        
        params = (
            proceso.IdMatrizSap,      # 4) p_IdMatrizSap
            sap_objeto_proceso.Id,    # 5) p_IdSapObjetoProceso
            proceso.IdRegla           # 6) p_IdRegla
        )

        BATCH_LIMIT = 5000
        BATCH = []

        result = conn.exec_driver_sql(sql, params)            
        if result.returns_rows:
                rows = result.fetchall()
                now = datetime.now()
                for item in rows:
                    BATCH.append({
                        "IdProceso": proceso.Id,
                        "IdUsuario": item[0],
                        "IdTransaccion": item[1],
                        "IdAppUserCreacion": user_id,
                        "IdAppUserActualizacion": user_id,
                        "FechaCreacion": now,
                        "FechaActualizacion": now,
                        "Estado": 1
                    })

                    if len(BATCH) > BATCH_LIMIT:
                        uniq = {}
                        for it in BATCH:
                            key = (it['IdProceso'], it['IdUsuario'], it['IdTransaccion'])
                            if key not in uniq:
                                uniq[key] = it
                        dedup_items = list(uniq.values())
                        HISTORY += len(dedup_items)
                        print(f"Registros Insertados: {str(HISTORY)}")

                        # Opción A: IGNORE
                        stmt = mysql_insert(UsuarioTransaccion).values(dedup_items).prefix_with("IGNORE")
                        session.execute(stmt)
                        BATCH = []                            
                if len(BATCH) > 0:
                    uniq = {}
                    for it in BATCH:
                        key = (it['IdProceso'], it['IdUsuario'], it['IdTransaccion'])
                        if key not in uniq:
                            uniq[key] = it
                    dedup_items = list(uniq.values())
                    HISTORY += len(dedup_items)
                    print(f"Registros Insertados: {str(HISTORY)}")

                    # Opción A: IGNORE
                    stmt = mysql_insert(UsuarioTransaccion).values(dedup_items).prefix_with("IGNORE")
                    session.execute(stmt)
                    BATCH = []
        result.close()

        progress += 25
        storage.update_progress(job_id, progress)

        session.flush()
        session.commit()

        result = session.query(UsuarioTransaccion).filter_by(IdProceso = proceso.Id).count()

        print(f"Registros insertados en UsuarioTransaccion para proceso {proceso.Id}: {result}")

            
        print("Usuarios Transaccionales insertados")
        
        session.close()
        return True       
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

        error_msg = f"Error en la función set_sod_matrix: {e} en {fname}:{exc_tb.tb_lineno}"
        print(error_msg)   
        storage.update_job_with_errors(job_id, [error_msg])     
        return False
    finally:
        session.close()
    
DATE_FMT = "%Y-%m-%d %H:%M:%S"

def json_500(e):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    return jsonify({
        "status": "Error",
        "detail": f"Error at {fname}:{exc_tb.tb_lineno}: {e}"
    }), 500

def serialize_proceso(p):
    """Equivalente a tu ProcessResponse usado en /all."""
    estado_texto = "Procesado" if (p.Procesado == 1 or p.Procesado is True) else "Pendiente"
    return {
        "Id": p.Id,
        "IdRegla": getattr(p.IdRegla, "Id", None) if hasattr(p, "IdRegla") else None,
        "IdMatrizSap": getattr(p.IdMatrizSap, "Id", None) if hasattr(p, "IdMatrizSap") else None, 
        "Regla": getattr(p.Regla, "Nombre", None) if hasattr(p, "Regla") else None,
        "MatrizSap": getattr(p.MatrizSap, "Nombre", None) if hasattr(p, "MatrizSap") else None,
        "Nombre": p.Nombre,
        "Descripcion": p.Descripcion,
        "FechaCorte": p.FechaCorte.strftime(DATE_FMT).split(" ")[0] if p.FechaCorte else None,
        "Fecha_Creacion": p.FechaCreacion.strftime(DATE_FMT) if p.FechaCreacion else None,
        "Fecha_Actualizacion": p.FechaActualizacion.strftime(DATE_FMT) if p.FechaActualizacion else None,
        "Estado": {
            "Estado": estado_texto,
            "Cantidad": p.Cantidad,
            "Tiempo": p.Tiempo
        },
        "Activo": True if (p.Estado == 1 or p.Estado is True) else False
    }


@process.route('/all', methods=['GET'])
def getall():
    session = SessionLocal()
    try:
        # SELECT con JOINs equivalentes y filtro Estado == 1
        rows = (
            session.query(
                Proceso.Id.label("id"),
                Regla.Nombre.label("regla"),
                MatrizSap.Nombre.label("maestrosap"),
                Proceso.Nombre.label("nombre"),
                Proceso.FechaCorte.label("fecha_Corte"),
                Proceso.FechaCreacion.label("fecha_Creacion"),
                Proceso.FechaActualizacion.label("fecha_Actualizacion"),
                Proceso.Procesado.label("procesado"),
                Proceso.Cantidad.label("cantidad"),
                Proceso.Tiempo.label("tiempo"),
                Proceso.Estado.label("estado"),
            )
            .join(Regla, Proceso.IdRegla == Regla.Id)
            .join(MatrizSap, Proceso.IdMatrizSap == MatrizSap.Id)
            .filter(Proceso.Estado == 1)
            .order_by(Proceso.FechaActualizacion.desc())
            .all()
        )

        # Proyección al mismo shape de tu ProcessResponse
        result = []
        for r in rows:
            result.append({
                "Id": r.id,
                "Regla": r.regla,
                "MatrizSap": r.maestrosap,
                "Nombre": r.nombre,
                "Fecha_Corte": r.fecha_Corte.strftime(DATE_FMT).split(" ")[0] if r.fecha_Corte else None,
                "Fecha_Creacion": r.fecha_Creacion.strftime(DATE_FMT) if r.fecha_Creacion else None,
                "Fecha_Actualizacion": r.fecha_Actualizacion.strftime(DATE_FMT) if r.fecha_Actualizacion else None,
                "Estado": {
                    "Procesado": True if (r.procesado == 1 or r.procesado is True) else False,
                    "Cantidad": r.cantidad,
                    "Tiempo": r.tiempo
                },
                "Activo": True if (r.estado == 1 or r.estado is True) else False
            })

        return jsonify(result), 200

    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()

@process.route('/<int:proc_id>', methods=['GET'])
def get_by_id(proc_id):
    session = SessionLocal()
    try:
        # Cargar Proceso + nombres de Regla y MatrizSap
        row = (
            session.query(Proceso, Regla.Id.label("regla"), MatrizSap.Id.label("matrizsap"))
            .join(Regla, Proceso.IdRegla == Regla.Id)
            .join(MatrizSap, Proceso.IdMatrizSap == MatrizSap.Id)
            .filter(Proceso.Id == proc_id)
            .first()
        )

        if not row:
            return jsonify({"error": "Proceso no encontrado"}), 404

        p = row.Proceso
        # Inyectamos en el objeto p atributos temporales para el serializer:
        p.IdRegla = type("Tmp", (), {"Id": row.regla})
        p.IdMatrizSap = type("Tmp", (), {"Id": row.matrizsap})

        return jsonify(serialize_proceso(p)), 200

    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()

@process.route('/edit', methods=['POST'])
def edit():
    session = SessionLocal()
    try:
        data = request.get_json() or {}
        proc_id = data.get("Id")
        nombre = data.get("Nombre")
        limit_date = data.get("FechaCorte")
        if not limit_date:
            limit_date = None

        if not proc_id:
            return jsonify({"error": "Falta id"}), 400

        p = session.get(Proceso, proc_id)
        if not p:
            return jsonify({"error": "Proceso no encontrado"}), 404
        
        duplicate = (
            session.query(Proceso)
            .filter(Proceso.Nombre == nombre, Proceso.Id != proc_id)
            .first()
        )

        if duplicate:
            return jsonify({"error": "Ya existe un proceso con ese nombre"}), 400

        # Asignaciones parciales (si el campo viene en el body, se actualiza)
        if "Nombre" in data: p.Nombre = data["Nombre"]
        if "Descripcion" in data: p.Descripcion = data["Descripcion"]
        p.FechaCorte = limit_date
        if "IdAppUserActualizacion" in data: p.IdAppUserActualizacion = data["IdAppUserActualizacion"]

        # Fecha de actualización en Lima
        now_dt = datetime.now(timezone(timedelta(hours=-5)))
        p.FechaActualizacion = now_dt

        session.commit()
        return jsonify({"status": "success", "Id": proc_id}), 200

    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()

@process.route('/<int:proc_id>', methods=['DELETE'])
def delete_one(proc_id):
    session = SessionLocal()
    try:
        p = session.get(Proceso, proc_id)
        if not p:
            return jsonify({"error": "Proceso no encontrado"}), 404

        session.delete(p)
        session.commit()
        return jsonify({"status": "success", "deletedId": proc_id}), 200

    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()

@process.route('/delete-multiple', methods=['POST'])
def delete_multiple():
    session = SessionLocal()
    try:
        ids = request.get_json() or []
        if not isinstance(ids, list) or not all(isinstance(x, int) for x in ids):
            return jsonify({"error": "Se requiere lista de enteros (ids)"}), 400
        if not ids:
            return jsonify({"error": "Lista de ids vacía"}), 400

        procesos = session.query(Proceso).filter(Proceso.Id.in_(ids)).all()
        if not procesos:
            return jsonify({"error": "No se encontraron procesos con esos ids"}), 404

        for p in procesos:
            session.delete(p)
        session.commit()

        return jsonify({"status": "success", "deletedCount": len(procesos)}), 200

    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()

@process.route('/versions/save', methods=['POST'])
def save_version():
    session = SessionLocal()       

    body = request.get_json(silent=True)
    id_version = body.get("id")
    process_id = body.get("idprocess")
    name = body.get("name")
    description = body.get("description") or ''
    complete = body.get("complete")
    details = body.get("details")
    user_id = body.get("iduser")

    if id_version:
        nuevo = False
    else:
        nuevo = True
    if not process_id:
        return jsonify({"success": False, "message": "Falta Proceso"})
    if not name:
        return jsonify({"success": False, "message": "Falta Nombre"})
    if not description:
        description = ''
    if complete is None:
        return jsonify({"success": False, "message": "Falta determinar si es una versión completa"})
    if not details:
        details = []
    if not user_id:
        return jsonify({"success": False, "message": 'Falta Id de Usuario'})
    
    try:
        process = session.get(Proceso, process_id)
        if not process:
            return jsonify({"success": False, "message": "El proceso ingresado no existe"})
        
        if nuevo:
            exist = session.query(Version).filter(and_(func.upper(Version.Nombre) == func.upper(name),Version.IdProceso == process_id)).first()
        else:
            exist = session.query(Version).filter(and_(func.upper(Version.Nombre) == func.upper(name),Version.IdProceso == process_id, Version.Id != id_version)).first()

        if exist:
            return jsonify({"success": False, "message": "La versión ingresada ya existe"})
        
        TZ_LIMA = timezone(timedelta(hours=-5))
        now = datetime.now(TZ_LIMA)
        
        if nuevo == True:
            _version =  Version()
        else:
            _version = session.get(Version, id_version)
            if _version is None:
                return jsonify({"success": False, "message": "La versión no existe"})
            
        _version.IdProceso = process_id
        _version.Nombre = name
        _version.Descripcion = description
        _version.Completo = complete
        _version.Procesado = 0
        _version.Tiempo = 0
        _version.Cantidad = 0
        _version.CantidadSa = 0
        _version.CantidadAlto = 0
        _version.CantidadMedio = 0
        _version.CantidadBajo = 0
        _version.CantidadUsuario = 0
        _version.CantidadSinConflicto = 0
        _version.CantidadConConflicto = 0
        _version.CantidadReglaSinConflicto = 0
        _version.CantidadReglaConConflicto = 0
        _version.CantidadRegla = 0        
        _version.IdAppUserCreacion = user_id
        _version.IdAppUserActualizacion = user_id
        _version.FechaCreacion = now
        _version.FechaActualizacion = now
        _version.Estado = 1
        if nuevo:
            session.add(_version)
        else:
            _version.Id = id_version

        session.commit()

        if not nuevo:
            subq_ids = (
                    select(VersionUsuario.Id)
                    .where(VersionUsuario.IdVersion == id_version)
                    .subquery()
                )

            # 2) Borra hijos que referencian esos VersionUsuario
            session.execute(
                delete(VersionUsuarioTransaccion)
                .where(VersionUsuarioTransaccion.IdVersionUsuario.in_(select(subq_ids.c.Id)))
            )

            session.execute(
                delete(VersionUsuarioRol)
                .where(VersionUsuarioRol.IdVersionUsuario.in_(select(subq_ids.c.Id)))
            )

            session.execute(
                delete(VersionUsuarioObjeto)
                .where(VersionUsuarioObjeto.IdVersionUsuario.in_(select(subq_ids.c.Id)))
            )

            # 3) Borra los VersionUsuario
            session.execute(
                delete(VersionUsuario)
                .where(VersionUsuario.Id.in_(select(subq_ids.c.Id)))
            )

            session.commit()

        
        for user in details:
            new_userversion = VersionUsuario()
            new_userversion.IdVersion = _version.Id
            new_userversion.IdUsuario = user["IdUsuario"]
            new_userversion.IdAppUserCreacion = user_id
            new_userversion.IdAppUserActualizacion = user_id
            new_userversion.FechaCreacion = now
            new_userversion.FechaActualizacion = now
            new_userversion.Estado = 1
            session.add(new_userversion)
            session.flush() 

            for trx in user["Transacciones"]:
                new_userversiontrx = VersionUsuarioTransaccion()                
                new_userversiontrx.IdTransaccion = trx
                new_userversiontrx.IdVersionUsuario = new_userversion.Id
                new_userversiontrx.IdAppUserCreacion = user_id
                new_userversiontrx.IdAppUserActualizacion = user_id
                new_userversiontrx.FechaCreacion = now
                new_userversiontrx.FechaActualizacion = now
                new_userversiontrx.Estado = 1
                session.add(new_userversiontrx)
            
            for rol in user["Roles"]:
                new_userversionrol = VersionUsuarioRol()
                new_userversionrol.IdSapRol = rol
                new_userversionrol.IdVersionUsuario = new_userversion.Id
                new_userversionrol.IdAppUserCreacion = user_id
                new_userversionrol.IdAppUserActualizacion = user_id
                new_userversionrol.FechaCreacion = now
                new_userversionrol.FechaActualizacion = now
                new_userversionrol.Estado = 1
                session.add(new_userversionrol)

            for obj in user["Objetos"]:
                new_userversionobj = VersionUsuarioObjeto()
                new_userversionobj.IdVersionUsuario = new_userversion.Id
                new_userversionobj.IdSapObjetoProceso = obj['Id_Objeto']
                new_userversionobj.IdSapCampoProceso = obj['Id_Campo']
                new_userversionobj.Desde = obj['Desde']
                new_userversionobj.Hasta = obj['Hasta']
                new_userversionobj.IdAppUserCreacion = user_id
                new_userversionobj.IdAppUserActualizacion = user_id
                new_userversionobj.FechaCreacion = now
                new_userversionobj.FechaActualizacion = now
                new_userversionobj.Estado = 1
                session.add(new_userversionobj)

        session.commit()

        return jsonify({"success": True, "message": "Versión registrada correctamente."}), 200
    except Exception as e:
        session.expunge_all()
        session.rollback()
        return jsonify({"success": False, "message": str(e)})
    finally:
        session.close()

@process.route('/versions/<int:proc_id>', methods=['GET'])
def get_versions(proc_id):
    session = SessionLocal()
    try:
        rows = session.query(Version).filter(Version.IdProceso == proc_id).order_by(desc(Version.FechaActualizacion)).all()

        result = [{
            "Id": v.Id,
            "Nombre": v.Nombre,
            "FechaCreacion": v.FechaCreacion.strftime(DATE_FMT) if v.FechaCreacion else None,
            "FechaActualizacion": v.FechaActualizacion.strftime(DATE_FMT) if v.FechaActualizacion else None,
            "Procesado": v.Procesado,
            "Completo": v.Completo,
            "Estado": v.Estado,
            "Tiempo": v.Tiempo,
            "Cantidad": v.Cantidad
        } for v in rows]

        return jsonify(result), 200

    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()

@process.route('/versions/get/<int:id>', methods=['GET'])
def get_version_by_id(id):
    
    session = SessionLocal()
    try:
        # ========================
        # 1. INFO DE LA VERSIÓN
        # ========================
        row = (
            session.query(
                Version.Id,
                Version.Nombre,
                Version.Descripcion,
                Version.FechaCreacion,
                Version.FechaActualizacion,
                Version.Procesado,
                Version.Completo,
                Version.Estado,
                Version.Tiempo,
                Version.Cantidad,
                Proceso.Nombre.label("ProcesoNombre")
            )
            .join(Proceso, Version.IdProceso == Proceso.Id)
            .filter(Version.Id == id)
            .first()
        )

        if not row:
            return jsonify({"success": False, "message": "Versión no encontrada", "data": None}), 404

        # Si es completa, no hay usuarios asociados
        if row.Completo == 1:
            return jsonify({
                "success": True,
                "message": "OK",
                "data": {
                    "Id": row.Id,
                    "Nombre": row.Nombre,
                    "Descripcion": row.Descripcion,
                    "FechaCreacion": row.FechaCreacion,
                    "FechaActualizacion": row.FechaActualizacion,
                    "Procesado": row.Procesado,
                    "Completo": row.Completo,
                    "Estado": row.Estado,
                    "Tiempo": row.Tiempo,
                    "Cantidad": row.Cantidad,
                    "Activo": True,
                    "Usuarios": []
                }
            }), 200

        # ========================
        # 2. USUARIOS
        # ========================
        usuarios = session.query(
            VersionUsuario.Id.label("IdVersionUsuario"),
            VersionUsuario.IdUsuario,
            Usuario.Usuario
        ).join(Usuario, VersionUsuario.IdUsuario == Usuario.Id)\
        .filter(VersionUsuario.IdVersion == id)\
        .all()

        # ========================
        # 3. TRANSACCIONES AGRUPADAS
        # ========================
        trx_rows = session.query(
            VersionUsuarioTransaccion.IdVersionUsuario,
            VersionUsuarioTransaccion.IdTransaccion,
            Transaccion.Codigo,
        ).join(VersionUsuario, VersionUsuarioTransaccion.IdVersionUsuario == VersionUsuario.Id)\
        .join(Transaccion, VersionUsuarioTransaccion.IdTransaccion == Transaccion.Id)\
        .filter(VersionUsuario.IdVersion == id)\
        .all()

        transacciones = defaultdict(list)
        for r in trx_rows:
            transacciones[r.IdVersionUsuario].append({
                "Id": r.IdTransaccion,
                "Codigo": r.Codigo
            })

        # ========================
        # 4. ROLES AGRUPADOS
        # ========================
        rol_rows = session.query(
            VersionUsuarioRol.IdVersionUsuario,
            VersionUsuarioRol.IdSapRol,
            SapRol.Nombre.label("Rol")
        ).join(VersionUsuario, VersionUsuarioRol.IdVersionUsuario == VersionUsuario.Id)\
        .join(SapRol, VersionUsuarioRol.IdSapRol == SapRol.Id)\
        .filter(VersionUsuario.IdVersion == id)\
        .all()

        roles = defaultdict(list)
        for r in rol_rows:
            roles[r.IdVersionUsuario].append({
                "Id": r.IdSapRol,
                "Rol": r.Rol
            })

        # ========================
        # 5. OBJETOS AGRUPADOS
        # ========================
        obj_rows = session.query(
            VersionUsuarioObjeto.IdVersionUsuario,
            VersionUsuarioObjeto.IdSapObjetoProceso,
            VersionUsuarioObjeto.IdSapCampoProceso,
            SapObjetoProceso.Nombre.label("Objeto"),
            SapCampoProceso.Nombre.label("Campo"),
            VersionUsuarioObjeto.Desde,
            VersionUsuarioObjeto.Hasta
        ).join(VersionUsuario, VersionUsuarioObjeto.IdVersionUsuario == VersionUsuario.Id)\
        .join(SapObjetoProceso, VersionUsuarioObjeto.IdSapObjetoProceso == SapObjetoProceso.Id)\
        .join(SapCampoProceso, VersionUsuarioObjeto.IdSapCampoProceso == SapCampoProceso.Id)\
        .filter(VersionUsuario.IdVersion == id)\
        .all()

        objetos = defaultdict(list)
        for r in obj_rows:
            objetos[r.IdVersionUsuario].append({
                "Id_Objeto": r.IdSapObjetoProceso,
                "Id_Campo": r.IdSapCampoProceso,
                "Objeto": r.Objeto,
                "Campo": r.Campo,
                "Desde": r.Desde,
                "Hasta": r.Hasta
            })

        # ========================
        # 6. ARMAR ESTRUCTURA FINAL
        # ========================
        usuarios_result = []
        for u in usuarios:
            usuarios_result.append({
                "IdUsuario": u.IdUsuario,
                "Usuario": u.Usuario,
                "Transacciones": transacciones.get(u.IdVersionUsuario, []),
                "Roles": roles.get(u.IdVersionUsuario, []),
                "Objetos": objetos.get(u.IdVersionUsuario, [])
            })

        # ========================
        # 7. RESPONSE FINAL
        # ========================
        return jsonify({
            "Id": row.Id,
            "Nombre": row.Nombre,
            "Descripcion": row.Descripcion,
            "FechaCreacion": row.FechaCreacion.isoformat(),
            "FechaActualizacion": row.FechaActualizacion.isoformat(),
            "Procesado": row.Procesado,
            "Completo": row.Completo,
            "Estado": row.Estado,
            "Tiempo": row.Tiempo,
            "Cantidad": row.Cantidad,
            "Activo": True,
            "Usuarios": usuarios_result
        }), 200

    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "message": str(e), "data": None}), 500
    finally:
        session.close()

@process.route('/usersxprocess/<int:id>', methods=['GET'])
def get_users_by_process(id):
    session = SessionLocal()
    try:
        proceso = session.get(Proceso,id)
        regla = session.get(Regla, proceso.IdRegla)

        U = aliased(Usuario)
        SU = aliased(SapUsuario)
        SUT = aliased(SapUsuarioTipo)

        
        sq_dialogo = (
            select(Campo.Id)  # puedes seleccionar Id o la columna que usarás en el IN
            .where(
                or_(
                    Campo.Nombre.like("%Diálogo%"),
                    Campo.Nombre.like("%Dialogo%")
                )
            )
            .subquery()
        )

        # Subquery 2: coincidencias con "Serv" o "Servicio"
        sq_servicio = (
            select(Campo.Id)
            .where(
                or_(
                    Campo.Nombre.like("%Serv%"),
                    Campo.Nombre.like("%Servicio%")
                )
            )
            .subquery()
        )

        union_ids = union_all(select(sq_dialogo.c.Id), select(sq_servicio.c.Id)).subquery()

        stmt = (
            session.query(
                U.Id,U.Usuario
            )
            .join(SU, U.Id == SU.IdUsuario)
            .join(SUT, SUT.IdUsuario == U.Id)
            .filter(SU.IdMatrizSap == proceso.IdMatrizSap, SUT.IdTipoUsuario.in_(union_ids))
            .distinct()
            .all()
        )

        users = [{
            "Id": v.Id,
            "Usuario": v.Usuario            
        } for v in stmt]

        return jsonify(users), 200
    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()

@process.route('/trxsbyuser/<int:id>', methods=['GET'])
def get_trx_by_user(id):
    session = SessionLocal()
    try:
        usuario = session.get(Usuario, id)
        if usuario is None:
            return jsonify({"error": "No se encuentra el usuario"})
        
        T = aliased(Transaccion)
        UT = aliased(UsuarioTransaccion)

        stmt = session.query(T.Id,T.Codigo).join(UT, T.Id == UT.IdTransaccion).filter(UT.IdUsuario == usuario.Id).distinct().all()
        
        transactions = [{
            "Id": v.Id,
            "Codigo": v.Codigo            
        } for v in stmt]

        return jsonify(transactions), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": e}), 400
    finally:
        session.close()

@process.route('/rolesbyuser/<int:id>', methods=['GET'])
def get_roles_by_user(id):
    session = SessionLocal()
    try:
        usuario = session.get(Usuario, id)
        if usuario is None:
            return jsonify({"error": "No se encuentra el usuario"})
        
        SR = aliased(SapRol)
        SUR = aliased(SapUsuarioRol)

        stmt = session.query(SR.Id,SR.Nombre).join(SUR, SR.Id == SUR.IdSapRol).filter(SUR.IdUsuario == usuario.Id).distinct().all()
        
        transactions = [{
            "Id": v.Id,
            "Rol": v.Nombre
        } for v in stmt]

        return jsonify(transactions), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": e}), 400
    finally:
        session.close()

@process.route('/objbyprocess/<int:id>', methods=['GET'])
def fetch_objects_by_process(id):
    session = SessionLocal()
    try:
        proceso = session.get(Proceso, id)
        if proceso is None:
            return jsonify({"error": "No se encuentra el proceso"})
        
        SOA = aliased(SapObjetoAutorizacion)
        SOP = aliased(SapObjetoProceso)
        SCP = aliased(SapCampoProceso)

        stmt = session.query(SOP.Id,SOP.Nombre).filter(and_(SOP.IdMatrizSap == proceso.IdMatrizSap,SOP.Nombre !='')).order_by(SOP.Nombre).distinct().all()
        
        objects = [{
            "Id_Objeto": v.Id,
            "Objeto": v.Nombre,
        } for v in stmt]

        return jsonify(objects), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": e}), 400
    finally:
        session.close()

@process.route('/objbyprocess/<int:id>/<int:obj>', methods=['GET'])
def get_objects_by_process(id, obj):
    session = SessionLocal()
    try:
        proceso = session.get(Proceso, id)
        if proceso is None:
            return jsonify({"error": "No se encuentra el proceso"})
        
        SOA = aliased(SapObjetoAutorizacion)
        SOP = aliased(SapObjetoProceso)
        SCP = aliased(SapCampoProceso)

        
        stmt = (
            session.query(
                SOA.IdSapObjetoProceso.label("Id_Objeto"),
                SOA.IdSapCampoProceso.label("Id_Campo"),
                SOP.Nombre.label("Objeto"),
                SCP.Nombre.label("Campo"),
            )
            .join(SOP, SOP.Id == SOA.IdSapObjetoProceso)
            .join(SCP, SCP.Id == SOA.IdSapCampoProceso)
            .filter(
                and_(
                    SOA.IdMatrizSap == proceso.IdMatrizSap,
                    SOA.IdSapObjetoProceso == obj,
                    SCP.Nombre != "",  # si necesitas excluir vacíos
                )
            )
            .group_by(
                SOA.IdSapObjetoProceso,
                SOA.IdSapCampoProceso,
                SOP.Nombre,
                SCP.Nombre,
            )
            .order_by(SCP.Nombre)
            .all()
        )

        
        objects = [{
            "Id_Objeto": v.Id_Objeto,
            "Id_Campo": v.Id_Campo,
            "Objeto": v.Objeto,
            "Campo": v.Campo
        } for v in stmt]

        return jsonify(objects), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": e}), 400
    finally:
        session.close()

@process.route('/details/<int:proc_id>', methods=['GET'])
def details(proc_id):
    session = SessionLocal()
    try:
        # Aliases de modelos para legibilidad
        UT = UsuarioTransaccion
        U  = Usuario
        T  = Transaccion
        C  = Campo

        rows = (
            session.query(
                U.Usuario.label("usuario"),
                func.concat(U.Nombre, literal(" "), U.Apellidos).label("nombres"),
                U.Email.label("email"),
                T.Codigo.label("codigo"),
                C.Nombre.label("sistema"),
                T.Codigo.label("opciones")
            )
            .select_from(UT)
            .join(U,  UT.IdUsuario == U.Id)
            .join(T,  UT.IdTransaccion == T.Id)
            .join(C,  T.IdSistema == C.Id)
            .filter(UT.IdProceso == proc_id)
            .order_by(UT.Id.asc())
            .all()
        )

        # En .NET, ToListAsync() nunca retorna null; si no hay filas, devuelve []
        result = [{
            "Usuario": r.usuario,
            "Nombres": r.nombres,
            "Email": r.email,
            "Codigo": r.codigo,
            "Sistema": r.sistema,
            "Opciones": r.opciones
        } for r in rows]

        return jsonify(result), 200

    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()


