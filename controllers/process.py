from collections import defaultdict
from fnmatch import fnmatch
import io
import sys
import threading
from datetime import datetime, timezone
from typing import DefaultDict, Iterable
import os
import time

from flask import Blueprint, request, jsonify
from sqlalchemy import and_, desc, exc, insert, select
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
from utils.environment import load_environment, get_environment
from typing import Iterable, Dict, Set, List, Tuple, Optional

process = Blueprint('process', __name__)

comodin = '*'

@process.route('/newprocess', methods=['POST'])
def new_Process():
    try:        
        body = request.get_json(silent=True)
        rule_id = body.get("idrule")
        matrixsap_id = body.get("idmatrixsap")
        name = body.get("name")
        description = body.get("description") or ''
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

        #job_id = storage.create_job()
        job_id = ''

        def run_prov():
            try:
                #storage.update_progress(job_id, 10)
                
                #response = process_usuario_transaccion(name,description,matrixsap_id,rule_id,2,'S_TCODE',"*",user_id)
                #response = migrar_autorizaciones_masivo_mysql(name=name,description=description,app_user_id=user_id,id_matriz_sap=matrixsap_id,
                                                              #id_regla=rule_id,id_sistema=config.SYSTEMS['SAP'],campo_transaccion=config.TRANSACTION_OBJECT,current_app_user_id=user_id)
                response = create(job_id, rule_id, matrixsap_id, name, description,user_id)                                                              
                
                print(f"Termina llamada a función set_sod_matrix")

                if response:
                    print("Proceso creado correctamente")
                    #storage.complete_job(job_id)
                elif isinstance(response, list):
                    print("Errores en el proceso")
                    for err in response:
                        print(err)
                    #storage.update_job_with_errors(job_id, response)                                                
                else:
                    # Fallo LÓGICO sin excepción (e.g., datos iniciales faltantes)
                    #storage.fail_job(job_id)
                    print("Fallo lógico en el proceso")                        
            except Exception as e:
                # Captura EXCEPCIONES (conexión DB, I/O, etc.)
                # El traceback de rules_process_form ya habrá hecho rollback y logging en el error de la sub-función

                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

                error_msg = f"Error para job {job_id}: {e} en {fname}:{exc_tb.tb_lineno}"

                #storage.update_job_with_errors(job_id, [error_msg])
                #storage.fail_job(job_id)
                print(f"Error FINAL en job {job_id}: {e}")
                return
                

        def run():
            MAX_ATTEMPTS = 3
            RETRY_DELAY = 5 # segundos

            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    print(f"Iniciando intento {attempt} para job {job_id}")
                    storage.update_progress(job_id, 10)
                    
                    response = create(job_id, rule_id, matrixsap_id, name, description, user_id)
                    
                    
                    print(f"Termina llamada a función set_sod_matrix")

                    if response:
                        storage.complete_job(job_id)
                        return
                    elif isinstance(response, list):
                        storage.update_job_with_errors(job_id, response)                                                
                    else:
                        # Fallo LÓGICO sin excepción (e.g., datos iniciales faltantes)
                        storage.fail_job(job_id)
                        return                        
                except Exception as e:
                    # Captura EXCEPCIONES (conexión DB, I/O, etc.)
                    # El traceback de rules_process_form ya habrá hecho rollback y logging en el error de la sub-función

                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

                    error_msg = f"Error para job {job_id}: {e} en {fname}:{exc_tb.tb_lineno}"

                    storage.update_job_with_errors(job_id, [error_msg])
                    storage.fail_job(job_id)
                    print(f"Error FINAL en job {job_id}: {e}")
                    return
                    
        threading.Thread(target=run_prov).start()

        return jsonify({"jobId": job_id}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    except exc.SQLAlchemyError as e:
        return jsonify({"error": f"SQLALCHEMY:{e}"}), 500

def create(job_id, rule_id, matrixsap_id, name, description, user_id):
    try:        
        now = datetime.now()
        campo_transaccion = config.TRANSACTION_OBJECT
        HISTORY = 0

        with SessionLocal() as session:
            with session.begin():
                proceso = Proceso()
                proceso.IdRegla = rule_id
                proceso.IdMatrizSap = matrixsap_id
                proceso.Nombre = name
                proceso.Descripcion = ''
                proceso.IdAppUserCreacion = user_id
                proceso.IdAppUserActualizacion = user_id
                proceso.FechaCreacion = now
                proceso.FechaActualizacion = now
                proceso.Estado = 1
                session.add(proceso)
                session.flush()

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

                #prefijos
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

                #complejos
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

                result = session.query(UsuarioTransaccion).filter_by(IdProceso = proceso.Id).count()

                print(f"Registros insertados en UsuarioTransaccion para proceso {proceso.Id}: {result}")

                    
                print("Usuarios Transaccionales insertados")

        return True       
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

        error_msg = f"Error en la función set_sod_matrix: {e} en {fname}:{exc_tb.tb_lineno}"
        print(error_msg)        
        return [error_msg]