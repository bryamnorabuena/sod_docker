import json
import sys
import threading
from datetime import datetime
import zipfile
import base64
import time
import os
import time

from flask import Blueprint, request, jsonify
from sqlalchemy import and_, desc, exc, select, insert
from io import BytesIO
from db.database import SessionLocal
from models import *
from config import config
from utils import storage
from services.nsg_service import *
from azure.identity import DefaultAzureCredential

from sqlalchemy.orm import Session

from utils.environment import get_environment

matrixsap = Blueprint('matrixsap', __name__)

comodin = '*'

@matrixsap.route('/new', methods=['POST'])
def new():
    try: 
        body = request.get_json(silent=True)
        name = body.get("name")
        description = body.get("description") or ''
        file_base64 = body.get("filebase64")
        user_id = body.get("iduser")

        if not name:
            return jsonify({"error": "Falta Nombre"}), 400
        if not description:
            description = ''
        if not file_base64:
            return jsonify({"error": "Falta Archivo"}), 400    
        if not user_id:
            return jsonify({'error': 'Falta Id de Usuario'}), 400      

        job_id = storage.create_job()

        zip_url = storage.upload_zip_and_get_url(file_base64, job_id)
        
        input_json = {
            "job_id": job_id,
            "name": name,
            "description": description,
            "zip_url": zip_url,
            "iduser": user_id
        }
        print(input_json)

        # 3) Autenticación a ARM con Managed Identity
        cred  = DefaultAzureCredential()
        token = cred.get_token("https://management.azure.com/.default").token

        # 4) Endpoint REST oficial para iniciar la ejecución del Job (START)        
        subscription_id = os.getenv("SUBSCRIPTION_ID")
        resource_group  = os.getenv("RESOURCE_GROUP")
        job_name        = os.getenv("MATRIX_SAP_CONTAINER_NAME")
        ARM_BASE        = "https://management.azure.com"
        url = (f"{ARM_BASE}/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
               f"/providers/Microsoft.App/jobs/{job_name}/start?api-version=2025-07-01")

        # Enviamos INPUT_JSON como env var (tu runner la lee con os.getenv('INPUT_JSON'))
        body_start = {            
            
            "containers": [
                {
                "name": "runner",
                "image": "sodregistryconflicts1.azurecr.io/aca-mastersap:latest",
                "env": [
                    { "name": "INPUT_JSON", "value": json.dumps(input_json) }
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
            azure_execution_id = resp.json().get("name")  # execution name de Azure
            # (La doc del endpoint START describe que retorna el nombre/ID de la ejecución si está listo) [1](https://oneuptime.com/blog/post/2026-02-16-how-to-deploy-a-microservice-to-azure-container-apps-with-custom-scaling-rules/view)
        # Si es 202 Accepted, a veces solo hay Location para polling; puedes devolver azureExecutionId=None
        # y resolverlo más tarde, pero con 200 ya tienes el nombre.

        # 6) Respuesta al cliente con ambos identificadores
        return jsonify({
            "jobId": job_id,                   # tu ID de tracking para el progreso
            "azureExecutionId": azure_execution_id  # el execution name del Job en Azure
        }), 202





        def run():
            MAX_ATTEMPTS = 3

            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    print(f"Iniciando intento {attempt} para job {job_id}")
                    storage.update_progress(job_id, 10)
                    
                    response = set_sod_matrix(job_id, name, description, file_base64, user_id)                    
                    
                    print(f"Termina llamada a función set_sod_matrix")

                    if response:
                        storage.complete_job(job_id)
                        return
                    elif isinstance(response, list):
                        storage.update_job_with_errors(job_id, response)                                                
                    else:
                        storage.fail_job(job_id)
                        return                        
                except Exception as e:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

                    error_msg = f"Error para job {job_id}: {e} en {fname}:{exc_tb.tb_lineno}"

                    storage.update_job_with_errors(job_id, [error_msg])
                    storage.fail_job(job_id)
                    print(f"Error en job {job_id}: {e}")
                    return
                    
        threading.Thread(target=run).start()

        return jsonify({"jobId": job_id}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    except exc.SQLAlchemyError as e:
        return jsonify({"error": f"SQLALCHEMY:{e}"}), 500


#BRNC ORIGINAL
def set_sod_matrix(job_id, name, description, file_base64, current_user):
    UsuariosMemory = {}
    PerfilMemory = {}
    TipoUsuariosMemory = {}
    progress = 0

    with SessionLocal() as session:
        with session.begin():
            try:
                BATCH_USUARIOPERFIL = []
                LIMIT_BATCH_USUARIOPERFIL = 5000
                time_start = time.perf_counter() 
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')                

                matrizsap = MatrizSap()
                matrizsap.Nombre = name
                matrizsap.Descripcion = description
                matrizsap.IdAppUserCreacion = current_user
                matrizsap.IdAppUserActualizacion = current_user
                matrizsap.FechaCreacion = now
                matrizsap.FechaActualizacion = now
                matrizsap.Estado = 1
                matrizsap.Tiempo = 0

                # Iniciamos la transacción
                session.add(matrizsap)
                session.flush()

                progress += 15
                storage.update_progress(job_id, progress)

                # Aquí podrías manejar el guardado de archivos si is_new
                # base64_zip = file_base64

                # zip_bytes = base64.b64decode(base64_zip)
                # zip_in_memory = BytesIO(zip_bytes)
                zip_in_memory = file_base64

                UsuariosMemory = {}
                PerfilMemory = {}
                UsuarioPerfilesMemory = []
                PerfilSubPerfilMemory = {}
                SubPerfilMemory = {}
                TipoUsuariosMemory = {}
                RolMemory = {}
                RolSubRolMemory = {}
                ObjetosMemory = {}
                AutorizacionMemory = {}
                CamposMemory = {}
                CatalogoMemory = {}
                AppFioriMemory = {}
                CatalogoAppFioriMemory = {}
                RolCatalogoMemory = {}
                
                print("Procesando USORG.txt")
                process_USORG(session, zip_in_memory, matrizsap.Id, 1)
                progress += 4
                storage.update_progress(job_id, progress)

                print("Procesando UST04.txt")
                process_UST04(session, zip_in_memory, matrizsap.Id, 1, 1,
                            UsuariosMemory, PerfilMemory, UsuarioPerfilesMemory)                                            
                progress += 4
                storage.update_progress(job_id, progress)

                print("Procesando UST10C.txt")
                process_UST10C(session,zip_in_memory,matrizsap.Id,1,PerfilMemory,PerfilSubPerfilMemory,SubPerfilMemory)
                progress += 4
                storage.update_progress(job_id, progress)

                for item in UsuarioPerfilesMemory:
                    id_usuario = item["IdUsuario"]
                    id_perfil = item['IdSapPerfil']
                    if id_perfil in SubPerfilMemory:
                        for item_sub_perfil in SubPerfilMemory[id_perfil]:
                            id_sub_perfil = item_sub_perfil
                            now = datetime.now()  # equivalente a new \DateTime()

                            BATCH_USUARIOPERFIL.append({
                                "IdMatrizSap": matrizsap.Id,
                                "IdSapPerfil": id_sub_perfil,
                                "IdUsuario": id_usuario,
                                "IdAppUserCreacion": current_user,
                                "IdAppUserActualizacion": current_user,
                                "FechaCreacion": now,
                                "FechaActualizacion": now,
                                "Estado": True
                            })

                            if len(BATCH_USUARIOPERFIL) > LIMIT_BATCH_USUARIOPERFIL:
                                session.execute(insert(SapUsuarioPerfil.__table__).values(BATCH_USUARIOPERFIL))
                                session.flush()             
                                BATCH_USUARIOPERFIL.clear()
                
                if len(BATCH_USUARIOPERFIL) > 0:
                    session.execute(insert(SapUsuarioPerfil.__table__).values(BATCH_USUARIOPERFIL))
                    session.flush()                    
                    BATCH_USUARIOPERFIL.clear()
                    
                progress += 4
                storage.update_progress(job_id, progress)

                print("Procesando UST10S.txt")
                process_UST10S(session,zip_in_memory,matrizsap.Id,1,PerfilMemory,ObjetosMemory,AutorizacionMemory)
                progress += 10
                storage.update_progress(job_id, progress)

                print("Procesando UST12.txt")
                process_UST12(session,zip_in_memory,matrizsap.Id,1,ObjetosMemory,AutorizacionMemory,CamposMemory)
                progress += 10
                storage.update_progress(job_id, progress)

                print("Procesando AGR_USERS.txt")
                process_AGR_USERS(session,zip_in_memory,matrizsap.Id,1,1,RolMemory,UsuariosMemory)         
                progress += 10
                storage.update_progress(job_id, progress)

                print("Procesando USR02.txt")
                process_USR02(session, zip_in_memory, matrizsap.Id, 1, 1,
                            UsuariosMemory, TipoUsuariosMemory, 7,
                            config.MIN_DATE_PHP,config.MAX_DATE_PHP)
                progress += 4
                storage.update_progress(job_id, progress)

                print("Procesando AGR_1251.txt")
                process_AGR_1251(session, zip_in_memory, matrizsap.Id, 1,
                         RolMemory, ObjetosMemory, AutorizacionMemory, CamposMemory)  
                progress += 10
                storage.update_progress(job_id, progress)

                print("Procesando AGR_1252.txt")
                process_AGR_1252(session, zip_in_memory, matrizsap.Id, 1, RolMemory)  
                progress += 4
                storage.update_progress(job_id, progress)

                print("Procesando AGR_GRS.txt")
                process_AGR_AGRS(session, zip_in_memory, matrizsap.Id, 1,
                                RolMemory, RolSubRolMemory)                                 
                progress += 4
                storage.update_progress(job_id, progress)

                print("Procesando CATALOGO.csv")
                process_CATALOGO(session, zip_in_memory, matrizsap.Id, 1,
                                CatalogoMemory, AppFioriMemory, CatalogoAppFioriMemory)  
                progress += 4
                storage.update_progress(job_id, progress)

                print("Procesando ROL.csv")
                process_ROL(session, zip_in_memory, matrizsap.Id, 1,
                            RolMemory, CatalogoMemory, RolCatalogoMemory) 
                progress += 4
                storage.update_progress(job_id, progress)                
                
                return True                
            except Exception as e:
                print(str(e))
                session.rollback()
                session.expunge_all()
                session.close()
                
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(f"Error at {fname}:{exc_tb.tb_lineno}: {e}")
                storage.update_job_with_errors(job_id, [f"Error: {e} at {fname}:{exc_tb.tb_lineno}"])

                return False
      

def get_batch_limit(text_file):    
    """Determine batch limit based on total lines."""
    total_lines = sum(1 for line in text_file)

    if total_lines <= 1000:
        return 100
    elif total_lines <= 5000:
        return 500
    elif total_lines <= 10000:
        return 1000
    elif total_lines <= 50000:
        return 2000
    elif total_lines <= 100000:
        return 5000
    elif total_lines <= 500000:
        return 10000
    elif total_lines <= 1000000:
        return 20000
    else:
        return 2000


BATCH = 2000  # tamaño de lote seguro; ajusta si tu máquina aguanta más

def _now():
    return datetime.now()  # DATETIME (MySQL aceptará 'YYYY-MM-DD' como '00:00:00')

def read_zip_lines(zip_path, filename, encoding="latin-1"):
    """Lee un archivo del ZIP en memoria, línea por línea (como mostraste)."""
    with zipfile.ZipFile(zip_path, "r") as zipf:
        for file_name in zipf.namelist():
            if file_name == filename:
                with zipf.open(file_name) as file:
                    for raw in file:
                        yield raw.decode(encoding).strip()
                break

def _first_id(session, table, where_clause, order_col):
    """
    Trae el PRIMER Id que cumpla la condición (evita MultipleResultsFound).
    Uso: _first_id(session, SapPerfil.__table__, (SapPerfil.IdMatrizSap==m) & (SapPerfil.Nombre==n), SapPerfil.Id)
    """
    return session.execute(
        select(table.c.Id).where(where_clause).order_by(order_col.asc()).limit(1)
    ).scalar_one_or_none()

# --------------------------------------------------------------------
# USUARIOS: lookup por lote (si existe usar Id; si no, insertar)
# --------------------------------------------------------------------
def ensure_usuarios(session: Session, usuarios_set, id_empresa, app_user_id, now):
    """
    Réplica del PHP: si existe por 'Usuario', usar Id; si no, insertar. (Lookup por lote)
    Retorna: {nombre_usuario: {"Id": id}}
    """
    if not usuarios_set:
        return {}

    # 1) lookup por lote
    usuarios = list(usuarios_set)
    user_id_map = {}
    for i in range(0, len(usuarios), BATCH):
        chunk = usuarios[i:i+BATCH]
        q = select(Usuario.Usuario, Usuario.Id).where(Usuario.Usuario.in_(chunk))
        for u, uid in session.execute(q):
            # Si hay duplicados en BD (misma cadena 'Usuario'), tomamos el primer Id
            if u not in user_id_map:
                user_id_map[u] = uid

    # 2) insertar faltantes
    to_insert = [u for u in usuarios if u not in user_id_map]
    if to_insert:
        rows = [{
            "Usuario": u,
            "IdEmpresa": id_empresa,
            "IdAppUserCreacion": app_user_id,
            "IdAppUserActualizacion": app_user_id,
            "FechaCreacion": now,
            "FechaActualizacion": now,
            "Estado": 1
        } for u in to_insert]
        for i in range(0, len(rows), BATCH):
            session.execute(insert(Usuario.__table__).values(rows[i:i+BATCH]))
        session.flush()
        # lookup de los recién insertados (equivalente a lastInsertId() pero por lote)
        for i in range(0, len(to_insert), BATCH):
            chunk = to_insert[i:i+BATCH]
            q = select(Usuario.Usuario, Usuario.Id).where(Usuario.Usuario.in_(chunk))
            for u, uid in session.execute(q):
                user_id_map[u] = uid

    return {u: {"Id": user_id_map[u]} for u in usuarios if u in user_id_map}

# --------------------------------------------------------------------
# USORG.txt -> sapcampoorganizacional
# --------------------------------------------------------------------
def process_USORG(session: Session, zip_path: str, matriz_id: int, app_user_id: int):
    """
    Inserta en sapcampoorganizacional si el 'Campo' no está en memoria (como el PHP).
    Tablas: sapcampoorganizacional (DDL provisto).
    """
    now = _now()
    campo_memory = {}  # {Campo: {"Id": id}}
    rows = []
    with zipfile.ZipFile(zip_path, "r") as zipf:
        for file_name in zipf.namelist():
            if file_name == "USORG.txt":
                with zipf.open(file_name) as file:
                    for line in file:
                        line = line.decode("latin-1").strip()
                        if "----" in line:
                            continue
                        parts = line.split("|")
                        # En el PHP esperan 4 partes y descartan cabecera FIELD/VARBL (índices [1],[2]) [1](https://people.ey.com/personal/bryam_norabuena_pe_ey_com/Documents/Microsoft%20Copilot%20Chat%20Files/php-process.php)
                        if len(parts) != 4:
                            continue
                        if parts[1].strip() == "FIELD" or parts[2].strip() == "VARBL":
                            continue
                        campo = parts[1].strip()
                        variable = parts[2].strip()

                        if campo in campo_memory:
                            continue

                        rows.append({
                            "IdMatrizSap": matriz_id,
                            "Campo": campo,
                            "Variable": variable,
                            "IdAppUserCreacion": app_user_id,
                            "IdAppUserActualizacion": app_user_id,
                            "FechaCreacion": now,
                            "FechaActualizacion": now,
                            "Estado": 1,
                        })
                        if len(rows) >= BATCH:
                            session.execute(insert(SapCampoOrganizacional.__table__).values(rows))
                            session.flush()
                            # completar memory con SELECT por lote (por Campo)
                            campos = [r["Campo"] for r in rows]
                            for i in range(0, len(campos), BATCH):
                                q = select(SapCampoOrganizacional.Campo, SapCampoOrganizacional.Id).where(
                                    (SapCampoOrganizacional.IdMatrizSap == matriz_id) &
                                    (SapCampoOrganizacional.Campo.in_(campos[i:i+BATCH]))
                                )
                                for c, cid in session.execute(q):
                                    campo_memory[c] = {"Id": cid}
                            rows.clear()

                    if rows:
                        session.execute(insert(SapCampoOrganizacional.__table__).values(rows))
                        session.flush()
                        campos = [r["Campo"] for r in rows]
                        for i in range(0, len(campos), BATCH):
                            q = select(SapCampoOrganizacional.Campo, SapCampoOrganizacional.Id).where(
                                (SapCampoOrganizacional.IdMatrizSap == matriz_id) &
                                (SapCampoOrganizacional.Campo.in_(campos[i:i+BATCH]))
                            )
                            for c, cid in session.execute(q):
                                campo_memory[c] = {"Id": cid}
                        rows.clear()
                break

    return campo_memory  # por si lo reutilizas en otros módulos

# --------------------------------------------------------------------
# UST04.txt -> usuario + sapperfil + (sapusuarioperfil)
# --------------------------------------------------------------------
def process_UST04(session: Session, zip_path: str, matriz_id: int, id_empresa: int, app_user_id: int,
                  usuarios_memory: dict, perfil_memory: dict, usuarioperfil_memory: list):
    """
    Réplica del PHP:
    - Usuario: lookup+insert (si no existe en memoria).
    - Perfil: insertar si no está en memoria (no se checa BD).
    - Link Usuario-Perfil: insertar usando los Id de memoria.
    Tablas: usuario, sapperfil (+ sapusuarioperfil si nos confirmas su modelo).
    """
    now = _now()
    usuarios_lote = set()
    perfiles_lote = set()
    links_bucket = []  # [{"Usuario": user, "SapPerfil": perfil}]

    with zipfile.ZipFile(zip_path, "r") as zipf:
        for file_name in zipf.namelist():
            if file_name == "UST04.txt":
                with zipf.open(file_name) as file:
                    for line in file:
                        line = line.decode("latin-1").strip()
                        if "----" in line:
                            continue
                        parts = line.split("|")
                        # El PHP espera 5 partes, y descarta cabecera MANDT (índice [1]) [1](https://people.ey.com/personal/bryam_norabuena_pe_ey_com/Documents/Microsoft%20Copilot%20Chat%20Files/php-process.php)
                        if len(parts) != 5 or parts[1].strip() == "MANDT":
                            continue
                        usuario = parts[2].strip()
                        perfil  = parts[3].strip()

                        if usuario not in usuarios_memory:
                            usuarios_lote.add(usuario)
                        if perfil not in perfil_memory:
                            perfiles_lote.add(perfil)

                        links_bucket.append({"Usuario": usuario, "SapPerfil": perfil})

                        # flush por lote
                        if len(links_bucket) >= BATCH:
                            usuarioperfil_memory.extend(_flush_ust04_batch(session, matriz_id, id_empresa, app_user_id, now,
                                            usuarios_memory, perfil_memory, usuarios_lote, perfiles_lote, links_bucket))
                            usuarios_lote.clear(); perfiles_lote.clear(); links_bucket.clear()

                    # último parcial
                    if links_bucket:
                        usuarioperfil_memory.extend(_flush_ust04_batch(session, matriz_id, id_empresa, app_user_id, now,
                                        usuarios_memory, perfil_memory, usuarios_lote, perfiles_lote, links_bucket))
                        usuarios_lote.clear(); perfiles_lote.clear(); links_bucket.clear()
                break

def _flush_ust04_batch(session, matriz_id, id_empresa, app_user_id, now,
                       usuarios_memory, perfil_memory, usuarios_lote, perfiles_lote, links_bucket):
    historic = []
    # 1) usuarios: lookup+insert (misma semántica) [1](https://people.ey.com/personal/bryam_norabuena_pe_ey_com/Documents/Microsoft%20Copilot%20Chat%20Files/php-process.php)
    if usuarios_lote:
        usuarios_memory.update(ensure_usuarios(session, usuarios_lote, id_empresa, app_user_id, now))

    # 2) perfiles: insertar sin chequear BD, sólo memoria (igual al PHP) [1](https://people.ey.com/personal/bryam_norabuena_pe_ey_com/Documents/Microsoft%20Copilot%20Chat%20Files/php-process.php)
    if perfiles_lote:
        rows = [{
            "IdMatrizSap": matriz_id,
            "Nombre": nombre,
            "Descripcion": "",
            "IdPadre": 0,
            "IdAppUserCreacion": app_user_id,
            "IdAppUserActualizacion": app_user_id,
            "FechaCreacion": now,
            "FechaActualizacion": now,
            "Estado": 1
        } for nombre in perfiles_lote]
        session.execute(insert(SapPerfil.__table__).values(rows))
        session.flush()        
        # completar memoria (por Nombre)
        nombres = list(perfiles_lote)
        for i in range(0, len(nombres), BATCH):
            q = select(SapPerfil.Nombre, SapPerfil.Id).where(
                (SapPerfil.IdMatrizSap == matriz_id) & (SapPerfil.Nombre.in_(nombres[i:i+BATCH]))
            )
            for n, pid in session.execute(q):
                perfil_memory[n] = {"Id": pid}

    # 3) link usuario-perfil (igual al PHP): insertar usando memoria
    #    (si quieres evitar duplicados internos del lote, deduplicamos por (IdUsuario, IdPerfil))
    link_rows = []
    seen = set()
    for it in links_bucket:
        u = it["Usuario"]; p = it["SapPerfil"]
        uid = usuarios_memory.get(u, {}).get("Id")
        pid = perfil_memory.get(p, {}).get("Id")
        if uid and pid:
            key = (uid, pid)
            if key in seen:
                continue
            seen.add(key)
            link_rows.append({
                "IdMatrizSap": matriz_id,
                "IdSapPerfil": pid,
                "IdUsuario": uid,
                "IdAppUserCreacion": app_user_id,
                "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now,
                "FechaActualizacion": now,
                "Estado": 1
            })

    if link_rows:
        session.execute(insert(SapUsuarioPerfil.__table__).values(link_rows))
        session.flush()
        historic.extend(link_rows)

    return historic

# --------------------------------------------------------------------
# USR02.txt -> sapusuariotipo + sapusuario (+ usuario + campo)
# --------------------------------------------------------------------
def process_USR02(session: Session, zip_path: str, matriz_id: int, id_empresa: int, app_user_id: int,
                  usuarios_memory: dict, tipousuarios_memory: dict,
                  generica_tipo_usuario_id: int,
                  min_date_php_str: str, max_date_php_str: str):
    """
    Réplica del PHP:
    - Usuario: lookup+insert.
    - TipoUsuario (Campo): insertar si no está en memoria.
    - sapusuariotipo + sapusuario con fechas según reglas del PHP.
    Tablas: sapusuariotipo, sapusuario; además 'campo' para el tipo.
    """
    try:
        now = _now()
        rows_usuario_tipo = []
        rows_sap_usuario = []

        with zipfile.ZipFile(zip_path, "r") as zipf:
            for file_name in zipf.namelist():
                if file_name == "USR02.txt":
                    with zipf.open(file_name) as file:
                        for line in file:
                            line = line.decode("latin-1").strip()
                            if "----" in line:
                                continue
                            parts = line.split("|")
                            # El PHP espera 46 partes; descarta cabecera MANDT; usa indices 2,4,5,6,9 [1](https://people.ey.com/personal/bryam_norabuena_pe_ey_com/Documents/Microsoft%20Copilot%20Chat%20Files/php-process.php)
                            if len(parts) != 46 or parts[1].strip() == "MANDT":
                                continue
                            usuario = parts[2].strip()
                            tipo_usuario = parts[6].strip()
                            uflag = int(parts[9].strip())

                            # Fechas (réplica): si falta inicio -> hoy; si falta fin -> max_date_php
                            # PHP formatea 'Y-m-d'; MySQL guardará 'YYYY-MM-DD 00:00:00' en DATETIME
                            if parts[4].strip() != "":
                                # d.m.Y -> YYYY-MM-DD
                                fecha_inicio = datetime.strptime(parts[4].strip(), "%d.%m.%Y")
                            else:
                                fecha_inicio = config.MIN_DATE_PHP
                                fecha_inicio = now
                            if parts[5].strip() != "":
                                # d.m.Y + 23:59:59 -> YYYY-MM-DD (puedes mantener sólo fecha para emular PHP)
                                fecha_fin = datetime.strptime(parts[5].strip() + " 23:59:59", "%d.%m.%Y %H:%M:%S")                            
                            else:
                                # max_date_php: 'Y-m-d H:i:s' (ej. '2037-12-31 23:59:59')
                                fecha_fin = datetime.strptime(config.MAX_DATE_PHP, "%Y-%m-%d %H:%M:%S")

                            # Usuario
                            if usuario not in usuarios_memory:
                                usuarios_memory.update(ensure_usuarios(session, {usuario}, id_empresa, app_user_id, now))

                            # Tipo de usuario (Campo) — insertar si no está en memoria (igual al PHP) [1](https://people.ey.com/personal/bryam_norabuena_pe_ey_com/Documents/Microsoft%20Copilot%20Chat%20Files/php-process.php)
                            if tipo_usuario not in tipousuarios_memory:
                                session.execute(insert(Campo.__table__).values([{
                                    "IdGenerica": generica_tipo_usuario_id,
                                    "Nombre": tipo_usuario,
                                    "Descripcion": "",
                                    "IdAppUserCreacion": app_user_id,
                                    "IdAppUserActualizacion": app_user_id,
                                    "FechaCreacion": now,
                                    "FechaActualizacion": now,
                                    "Estado": 1
                                }]))
                                session.flush()
                                tid = session.execute(
                                    select(Campo.Id)
                                    .where(
                                        Campo.IdGenerica == generica_tipo_usuario_id,
                                        Campo.Nombre == tipo_usuario
                                    )
                                    .order_by(Campo.Id.asc())
                                    .limit(1)
                                ).scalar_one_or_none()

                                if tid is None:
                                    # No existe (o no lo vimos en memoria): insértalo
                                    # Opción 1 (Core) -> después haces otro SELECT con limit 1
                                    # Opción 2 (recomendada): ORM + flush y tomas obj.Id sin SELECT:
                                    obj = Campo(
                                        IdGenerica=generica_tipo_usuario_id,
                                        Nombre=tipo_usuario,
                                        Descripcion='',
                                        IdAppUserCreacion=app_user_id,
                                        IdAppUserActualizacion=app_user_id,
                                        FechaCreacion=now,
                                        FechaActualizacion=now,
                                        Estado=1
                                    )
                                    session.add(obj)
                                    session.flush([obj])
                                    tid = obj.Id  # <-- Id confiable sin riesgo de múltiples
                                tipousuarios_memory[tipo_usuario] = {"Id": tid}

                            # sapusuariotipo
                            rows_usuario_tipo.append({
                                "IdMatrizSap": matriz_id,
                                "IdUsuario": usuarios_memory[usuario]["Id"],
                                "IdTipoUsuario": tipousuarios_memory[tipo_usuario]["Id"],
                                "IdAppUserCreacion": app_user_id,
                                "IdAppUserActualizacion": app_user_id,
                                "FechaCreacion": now,
                                "FechaActualizacion": now,
                                "Estado": 1
                            })
                            # sapusuario
                            rows_sap_usuario.append({
                                "IdMatrizSap": matriz_id,
                                "IdUsuario": usuarios_memory[usuario]["Id"],
                                "FechaInicio": fecha_inicio,
                                "FechaFin": fecha_fin,
                                "Uflag": uflag,
                                "IdAppUserCreacion": app_user_id,
                                "IdAppUserActualizacion": app_user_id,
                                "FechaCreacion": now,
                                "FechaActualizacion": now,
                                "Estado": 1
                            })

                            # flush por lote
                            if len(rows_usuario_tipo) >= BATCH:
                                session.execute(insert(SapUsuarioTipo.__table__).values(rows_usuario_tipo))
                                session.flush(); rows_usuario_tipo.clear()
                            if len(rows_sap_usuario) >= BATCH:
                                session.execute(insert(SapUsuario.__table__).values(rows_sap_usuario))
                                session.flush(); rows_sap_usuario.clear()

                        # último parcial
                        if rows_usuario_tipo:
                            session.execute(insert(SapUsuarioTipo.__table__).values(rows_usuario_tipo))
                            session.flush()
                        if rows_sap_usuario:
                            session.execute(insert(SapUsuario.__table__).values(rows_sap_usuario))
                            session.flush()
                    break
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(f"Error at {fname}:{exc_tb.tb_lineno}: {e}")
        raise Exception(f"Error en la función matrizsap: {e}")

def process_UST10C(session: Session, zip_path: str, matriz_id: int, app_user_id: int,
                   perfil_memory: dict, perfil_subperfil_memory: dict, subperfil_memory: dict):
    now = _now()
    rows_new_perfiles = []
    rows_new_subperfiles = []

    for line in read_zip_lines(zip_path, "UST10C.txt", "latin-1"):
        if "----" in line:  # descartar separador
            continue
        parts = line.split("|")
        # PHP: 6 partes, descartando MANDT en [1]
        if len(parts) != 6 or parts[1].strip() == "MANDT":
            continue

        perfil     = parts[2].strip()
        sub_perfil = parts[4].strip()

        # PERFIL (memoria → crear si no está en memoria)
        if perfil not in perfil_memory:
            # INSERT con Core (o ORM + flush); luego obtenemos Id con FIRST
            rows_new_perfiles.append({
                "IdMatrizSap": matriz_id, "Nombre": perfil, "Descripcion": "",
                "IdPadre": 0, "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            })
        # SUBPERFIL (memoria por (perfil, sub_perfil))
        if perfil_subperfil_memory.get(perfil, {}).get(sub_perfil) is None:
            # Asegurar que PERFIL tenga Id (si ya existe o se insertará)
            # Si no estaba en memoria, lo insertaremos más abajo y luego resolvemos Id
            rows_new_subperfiles.append((perfil, {
                "IdMatrizSap": matriz_id, "Nombre": sub_perfil, "Descripcion": "",
                # IdPadre se completará tras resolver Id del PERFIL
                "IdPadre": None,
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }))

        # FLUSH por lote
        if len(rows_new_perfiles) >= BATCH or len(rows_new_subperfiles) >= BATCH:
            _flush_UST10C(session, matriz_id, app_user_id, now,
                          perfil_memory, perfil_subperfil_memory, subperfil_memory,
                          rows_new_perfiles, rows_new_subperfiles)

    # Último parcial
    if rows_new_perfiles or rows_new_subperfiles:
        _flush_UST10C(session, matriz_id, app_user_id, now,
                      perfil_memory, perfil_subperfil_memory, subperfil_memory,
                      rows_new_perfiles, rows_new_subperfiles)

def _flush_UST10C(session, matriz_id, app_user_id, now,
                  perfil_memory, perfil_subperfil_memory, subperfil_memory,
                  rows_new_perfiles, rows_new_subperfiles):
    # Insert PERFIL pendientes
    if rows_new_perfiles:
        session.execute(insert(SapPerfil.__table__).values(rows_new_perfiles))
        session.flush()
        # Completar memoria: por Nombre dentro de esta matriz
        nombres = [r["Nombre"] for r in rows_new_perfiles]
        for i in range(0, len(nombres), BATCH):
            q = select(SapPerfil.Nombre, SapPerfil.Id).where(
                (SapPerfil.IdMatrizSap == matriz_id) & (SapPerfil.Nombre.in_(nombres[i:i+BATCH]))
            )
            for n, pid in session.execute(q):
                perfil_memory[n] = {"Id": pid}
        rows_new_perfiles.clear()

    # Insert SUBPERFIL pendientes (ya sabemos Id del PERFIL en perfil_memory)
    if rows_new_subperfiles:
        # Completar IdPadre y preparar rows
        sub_rows = []
        for perfil, row in rows_new_subperfiles:
            pid = perfil_memory[perfil]["Id"]  # garantizado tras bloque anterior
            row["IdPadre"] = pid
            sub_rows.append(row)

        session.execute(insert(SapPerfil.__table__).values(sub_rows))
        session.flush()
        # Completar memoria de subperfil y mapas
        nombres_sub = [r["Nombre"] for r in sub_rows]
        for i in range(0, len(nombres_sub), BATCH):
            q = select(SapPerfil.Nombre, SapPerfil.Id).where(
                (SapPerfil.IdMatrizSap == matriz_id) & (SapPerfil.Nombre.in_(nombres_sub[i:i+BATCH]))
            )
            for n, spid in session.execute(q):
                perfil_memory[n] = {"Id": spid}
                # vínculos auxiliares
        for perfil, row in rows_new_subperfiles:
            spid = perfil_memory[row["Nombre"]]["Id"]
            perfil_subperfil_memory.setdefault(perfil, {})[row["Nombre"]] = {"Id": spid}
            subperfil_memory.setdefault(perfil_memory[perfil]["Id"], {})[spid] = {"Id": spid}

        rows_new_subperfiles.clear()

def process_UST10S(session: Session, zip_path: str, matriz_id: int, app_user_id: int,
                   perfil_memory: dict, objetos_memory: dict, autorizacion_memory: dict):
    now = _now()
    rel_rows = []

    for line in read_zip_lines(zip_path, "UST10S.txt", "latin-1"):
        if "----" in line:
            continue
        parts = line.split("|")
        if len(parts) != 7 or parts[1].strip() == "MANDT":
            continue

        perfil = parts[2].strip()
        objeto = parts[4].strip()
        autorizacion = parts[5].strip()

        # PERFIL
        if perfil not in perfil_memory:
            session.execute(insert(SapPerfil.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": perfil, "Descripcion": "",
                "IdPadre": 0, "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            pid = _first_id(session, SapPerfil.__table__,
                            (SapPerfil.IdMatrizSap == matriz_id) & (SapPerfil.Nombre == perfil),
                            SapPerfil.Id)
            perfil_memory[perfil] = {"Id": pid}

        # OBJETO
        if objeto not in objetos_memory:
            session.execute(insert(SapObjetoProceso.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": objeto, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            oid = _first_id(session, SapObjetoProceso.__table__,
                            (SapObjetoProceso.IdMatrizSap == matriz_id) & (SapObjetoProceso.Nombre == objeto),
                            SapObjetoProceso.Id)
            objetos_memory[objeto] = {"Id": oid}

        # AUTORIZACIÓN
        if autorizacion not in autorizacion_memory:
            session.execute(insert(SapAutorizacion.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": autorizacion, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            aid = _first_id(session, SapAutorizacion.__table__,
                            (SapAutorizacion.IdMatrizSap == matriz_id) & (SapAutorizacion.Nombre == autorizacion),
                            SapAutorizacion.Id)
            autorizacion_memory[autorizacion] = {"Id": aid}

        rel_rows.append({
            "IdMatrizSap": matriz_id,
            "IdSapPerfil": perfil_memory[perfil]["Id"],
            "IdSapObjetoProceso": objetos_memory[objeto]["Id"],
            "IdSapAutorizacion": autorizacion_memory[autorizacion]["Id"],
            "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
            "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
        })

        if len(rel_rows) >= BATCH:
            session.execute(insert(SapPerfilObjetoAutorizacion.__table__).values(rel_rows))
            session.flush()
            rel_rows.clear()

    if rel_rows:
        session.execute(insert(SapPerfilObjetoAutorizacion.__table__).values(rel_rows))
        session.flush()
        rel_rows.clear()

def process_UST12(session: Session, zip_path: str, matriz_id: int, app_user_id: int,
                  objetos_memory: dict, autorizacion_memory: dict, campos_memory: dict):
    now = _now()
    rel_rows = []

    for line in read_zip_lines(zip_path, "UST12.txt", "latin-1"):
        if "----" in line:
            continue
        parts = line.split("|")
        if len(parts) != 9 or parts[1].strip() == "MANDT":
            continue

        objeto       = parts[2].strip()
        autorizacion = parts[3].strip()
        campo        = parts[5].strip()
        desde        = parts[6].strip()
        hasta        = parts[7].strip()

        # OBJETO
        if objeto not in objetos_memory:
            session.execute(insert(SapObjetoProceso.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": objeto, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            oid = _first_id(session, SapObjetoProceso.__table__,
                            (SapObjetoProceso.IdMatrizSap == matriz_id) & (SapObjetoProceso.Nombre == objeto),
                            SapObjetoProceso.Id)
            objetos_memory[objeto] = {"Id": oid}

        # AUTORIZACIÓN
        if autorizacion not in autorizacion_memory:
            session.execute(insert(SapAutorizacion.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": autorizacion, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            aid = _first_id(session, SapAutorizacion.__table__,
                            (SapAutorizacion.IdMatrizSap == matriz_id) & (SapAutorizacion.Nombre == autorizacion),
                            SapAutorizacion.Id)
            autorizacion_memory[autorizacion] = {"Id": aid}

        # CAMPO
        if campo not in campos_memory:
            session.execute(insert(SapCampoProceso.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": campo, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            cid = _first_id(session, SapCampoProceso.__table__,
                            (SapCampoProceso.IdMatrizSap == matriz_id) & (SapCampoProceso.Nombre == campo),
                            SapCampoProceso.Id)
            campos_memory[campo] = {"Id": cid}

        rel_rows.append({
            "IdMatrizSap": matriz_id,
            "IdSapObjetoProceso": objetos_memory[objeto]["Id"],
            "IdSapAutorizacion": autorizacion_memory[autorizacion]["Id"],
            "IdSapCampoProceso": campos_memory[campo]["Id"],
            "Desde": desde, "Hasta": hasta,
            "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
            "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
        })

        if len(rel_rows) >= BATCH:
            session.execute(insert(SapObjetoAutorizacion.__table__).values(rel_rows))
            session.flush(); rel_rows.clear()

    if rel_rows:
        session.execute(insert(SapObjetoAutorizacion.__table__).values(rel_rows))
        session.flush(); rel_rows.clear()
    
def process_AGR_USERS(session: Session, zip_path: str, matriz_id: int, id_empresa: int, app_user_id: int,
                      rol_memory: dict, usuarios_memory: dict):
    now = _now()
    rows = []

    for line in read_zip_lines(zip_path, "AGR_USERS.txt", "latin-1"):
        if "----" in line:
            continue
        parts = line.split("|")
        if len(parts) != 13 or parts[1].strip() == "MANDT":
            continue

        rol     = parts[2].strip()
        usuario = parts[3].strip()

        # Fechas
        fecha_inicio = datetime.strptime(parts[4].strip(), "%d.%m.%Y")
        fecha_fin    = datetime.strptime(parts[5].strip() + " 23:59:59", "%d.%m.%Y %H:%M:%S")

        # ROL
        if rol not in rol_memory:
            session.execute(insert(SapRol.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": rol, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            rid = _first_id(session, SapRol.__table__,
                            (SapRol.IdMatrizSap == matriz_id) & (SapRol.Nombre == rol), SapRol.Id)
            rol_memory[rol] = {"Id": rid}

        # USUARIO (lookup+insert)
        if usuario not in usuarios_memory:
            usuarios_memory.update(ensure_usuarios(session, {usuario}, id_empresa, app_user_id, now))

        rows.append({
            "IdMatrizSap": matriz_id,
            "IdSapRol": rol_memory[rol]["Id"],
            "IdUsuario": usuarios_memory[usuario]["Id"],
            "FechaInicio": fecha_inicio, "FechaFin": fecha_fin,
            "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
            "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
        })

        if len(rows) >= BATCH:
            session.execute(insert(SapUsuarioRol.__table__).values(rows))
            session.flush(); rows.clear()

    if rows:
        session.execute(insert(SapUsuarioRol.__table__).values(rows))
        session.flush(); rows.clear()

def process_AGR_1251(session: Session, zip_path: str, matriz_id: int, app_user_id: int,
                     rol_memory: dict, objetos_memory: dict, autorizacion_memory: dict, campos_memory: dict):
    now = _now()
    rel_rows = []
    BATCH_1251 = 5000

    for line in read_zip_lines(zip_path, "AGR_1251.txt", "latin-1"):
        if "----" in line:
            continue
        parts = line.split("|")
        if len(parts) != 16 or parts[1].strip() == "MANDT":
            continue  # reglas del PHP para AGR_1251 [1](https://people.ey.com/personal/bryam_norabuena_pe_ey_com/Documents/Microsoft%20Copilot%20Chat%20Files/php-process.php)

        rol          = parts[2].strip()
        objeto       = parts[4].strip()
        autorizacion = parts[5].strip()
        campo        = parts[7].strip()
        desde        = parts[8].strip()
        hasta        = parts[9].strip()

        # ROL
        if rol not in rol_memory:
            session.execute(insert(SapRol.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": rol, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            rid = _first_id(session, SapRol.__table__,
                            (SapRol.IdMatrizSap == matriz_id) & (SapRol.Nombre == rol), SapRol.Id)
            rol_memory[rol] = {"Id": rid}

        # OBJETO
        if objeto not in objetos_memory:
            session.execute(insert(SapObjetoProceso.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": objeto, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            oid = _first_id(session, SapObjetoProceso.__table__,
                            (SapObjetoProceso.IdMatrizSap == matriz_id) & (SapObjetoProceso.Nombre == objeto),
                            SapObjetoProceso.Id)
            objetos_memory[objeto] = {"Id": oid}

        # AUTORIZACIÓN
        if autorizacion not in autorizacion_memory:
            session.execute(insert(SapAutorizacion.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": autorizacion, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            aid = _first_id(session, SapAutorizacion.__table__,
                            (SapAutorizacion.IdMatrizSap == matriz_id) & (SapAutorizacion.Nombre == autorizacion),
                            SapAutorizacion.Id)
            autorizacion_memory[autorizacion] = {"Id": aid}

        # CAMPO
        if campo not in campos_memory:
            session.execute(insert(SapCampoProceso.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": campo, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            cid = _first_id(session, SapCampoProceso.__table__,
                            (SapCampoProceso.IdMatrizSap == matriz_id) & (SapCampoProceso.Nombre == campo),
                            SapCampoProceso.Id)
            campos_memory[campo] = {"Id": cid}

        # RELACIÓN Rol-Objeto-Autorización-Campo
        rel_rows.append({
            "IdMatrizSap": matriz_id,
            "IdSapRol": rol_memory[rol]["Id"],
            "IdSapObjetoProceso": objetos_memory[objeto]["Id"],
            "IdSapAutorizacion": autorizacion_memory[autorizacion]["Id"],
            "IdSapCampoProceso": campos_memory[campo]["Id"],
            "Desde": desde, "Hasta": hasta,
            "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
            "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
        })

        if len(rel_rows) >= BATCH_1251:
            session.execute(insert(SapRolObjetoAutorizacion.__table__).values(rel_rows))
            session.flush(); rel_rows.clear()

    if rel_rows:
        session.execute(insert(SapRolObjetoAutorizacion.__table__).values(rel_rows))
        session.flush(); rel_rows.clear()

def process_AGR_1252(session: Session, zip_path: str, matriz_id: int, app_user_id: int,
                     rol_memory: dict):
    now = _now()
    rows = []

    for line in read_zip_lines(zip_path, "AGR_1252.txt", "latin-1"):
        if "----" in line:
            continue
        parts = line.split("|")
        if len(parts) != 8 or parts[1].strip() == "MANDT":
            continue  # reglas del PHP para AGR_1252 [1](https://people.ey.com/personal/bryam_norabuena_pe_ey_com/Documents/Microsoft%20Copilot%20Chat%20Files/php-process.php)

        rol = parts[2].strip()
        nivel_org = parts[4].strip()
        desde = parts[5].strip()
        hasta = parts[6].strip()

        # ROL
        if rol not in rol_memory:
            session.execute(insert(SapRol.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": rol, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            rid = _first_id(session, SapRol.__table__,
                            (SapRol.IdMatrizSap == matriz_id) & (SapRol.Nombre == rol), SapRol.Id)
            rol_memory[rol] = {"Id": rid}

        rows.append({
            "IdMatrizSap": matriz_id,
            "IdSapRol": rol_memory[rol]["Id"],
            "NivelOrganizacional": nivel_org,
            "Desde": desde, "Hasta": hasta,
            "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
            "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
        })

        if len(rows) >= BATCH:
            session.execute(insert(SapNivelOrganizacional.__table__).values(rows))
            session.flush(); rows.clear()

    if rows:
        session.execute(insert(SapNivelOrganizacional.__table__).values(rows))
        session.flush(); rows.clear()

def process_AGR_AGRS(session: Session, zip_path: str, matriz_id: int, app_user_id: int,
                     rol_memory: dict, rol_subrol_memory: dict):
    now = _now()
    rows = []

    for line in read_zip_lines(zip_path, "AGR_AGRS.txt", "latin-1"):
        if "----" in line:
            continue
        parts = line.split("|")
        if len(parts) != 6 or parts[1].strip() == "MANDT":
            continue  # reglas del PHP para AGR_AGRS [1](https://people.ey.com/personal/bryam_norabuena_pe_ey_com/Documents/Microsoft%20Copilot%20Chat%20Files/php-process.php)

        rol = parts[2].strip()
        sub_rol = parts[3].strip()

        # Crear ambos si no estaban en memoria
        for r in (rol, sub_rol):
            if r not in rol_memory:
                session.execute(insert(SapRol.__table__).values([{
                    "IdMatrizSap": matriz_id, "Nombre": r, "Descripcion": "",
                    "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                    "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
                }]))
                session.flush()
                rid = _first_id(session, SapRol.__table__,
                                (SapRol.IdMatrizSap == matriz_id) & (SapRol.Nombre == r), SapRol.Id)
                rol_memory[r] = {"Id": rid}

        rows.append({
            "IdMatrizSap": matriz_id,
            "IdSapRol": rol_memory[rol]["Id"],
            "IdSapSubRol": rol_memory[sub_rol]["Id"],
            "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
            "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
        })

        if len(rows) >= BATCH:
            session.execute(insert(SapRolSubRol.__table__).values(rows))
            session.flush(); rows.clear()

    if rows:
        session.execute(insert(SapRolSubRol.__table__).values(rows))
        session.flush(); rows.clear()

def process_CATALOGO(session: Session, zip_path: str, matriz_id: int, app_user_id: int,
                     catalogo_memory: dict, appfiori_memory: dict, catalogo_appfiori_memory: dict):
    now = _now()
    rows_link = []

    for line in read_zip_lines(zip_path, "CATALOGO.csv", "latin-1"):
        if not line.strip():
            continue
        parts = line.split(";")
        if parts[0].strip() == "Catalogo":
            continue
        if len(parts) != 2:
            continue  # reglas del PHP para CATALOGO.csv [1](https://people.ey.com/personal/bryam_norabuena_pe_ey_com/Documents/Microsoft%20Copilot%20Chat%20Files/php-process.php)

        catalogo = parts[0].strip()
        app_fiori = parts[1].strip()

        # Catalogo
        if catalogo not in catalogo_memory:
            session.execute(insert(Catalogo.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": catalogo, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            cid = _first_id(session, Catalogo.__table__,
                            (Catalogo.IdMatrizSap == matriz_id) & (Catalogo.Nombre == catalogo), Catalogo.Id)
            catalogo_memory[catalogo] = {"Id": cid}

        # AppFiori
        if app_fiori not in appfiori_memory:
            session.execute(insert(AppFiori.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": app_fiori, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            aid = _first_id(session, AppFiori.__table__,
                            (AppFiori.IdMatrizSap == matriz_id) & (AppFiori.Nombre == app_fiori), AppFiori.Id)
            appfiori_memory[app_fiori] = {"Id": aid}

        # Link Catalogo–AppFiori (evitar duplicar dentro del lote)
        key = (catalogo_memory[catalogo]["Id"], appfiori_memory[app_fiori]["Id"])
        if key not in catalogo_appfiori_memory:
            rows_link.append({
                "IdCatalogo": key[0],
                "IdAppFiori": key[1],
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            })
            catalogo_appfiori_memory[key] = {"Id": None}

        if len(rows_link) >= BATCH:
            session.execute(insert(CatalogoAppFiori.__table__).values(rows_link))
            session.flush(); rows_link.clear()

    if rows_link:
        session.execute(insert(CatalogoAppFiori.__table__).values(rows_link))
        session.flush(); rows_link.clear()

def process_ROL(session: Session, zip_path: str, matriz_id: int, app_user_id: int,
                rol_memory: dict, catalogo_memory: dict, rol_catalogo_memory: dict):
    now = _now()
    rows = []

    for line in read_zip_lines(zip_path, "ROL.csv", "latin-1"):
        if not line.strip():
            continue
        parts = line.split(";")
        if parts[0].strip() == "Rol":
            continue
        if len(parts) != 5:
            continue  # reglas del PHP para ROL.csv [1](https://people.ey.com/personal/bryam_norabuena_pe_ey_com/Documents/Microsoft%20Copilot%20Chat%20Files/php-process.php)

        rol = parts[0].strip()
        catalogo = parts[3].strip()

        # Rol
        if rol not in rol_memory:
            session.execute(insert(SapRol.__table__).values([{
                "IdMatrizSap": matriz_id, "Nombre": rol, "Descripcion": "",
                "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
            }]))
            session.flush()
            rid = _first_id(session, SapRol.__table__,
                            (SapRol.IdMatrizSap == matriz_id) & (SapRol.Nombre == rol), SapRol.Id)
            rol_memory[rol] = {"Id": rid}

        # Rol–Catalogo (solo si el catálogo fue creado en CATALOGO.csv)
        if catalogo in catalogo_memory:
            key = (rol_memory[rol]["Id"], catalogo_memory[catalogo]["Id"])
            if key not in rol_catalogo_memory:
                rows.append({
                    "IdMatrizSap": matriz_id,
                    "IdSapRol": key[0], "IdCatalogo": key[1],
                    "IdAppUserCreacion": app_user_id, "IdAppUserActualizacion": app_user_id,
                    "FechaCreacion": now, "FechaActualizacion": now, "Estado": 1
                })
                rol_catalogo_memory[key] = {"Id": None}

        if len(rows) >= BATCH:
            session.execute(insert(SapRolCatalogo.__table__).values(rows))
            session.flush(); rows.clear()

    if rows:
        session.execute(insert(SapRolCatalogo.__table__).values(rows))
        session.flush(); rows.clear()
