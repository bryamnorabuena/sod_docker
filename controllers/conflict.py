from collections import defaultdict
import datetime
import sys
import time
import threading
from memory_profiler import profile
from datetime import date, time as dtime, timedelta, timezone
from fnmatch import fnmatch
from pathlib import Path
from zoneinfo import ZoneInfo
from flask import Blueprint, json, request, current_app, session, abort, jsonify
import numpy as np
from sqlalchemy import and_, asc, desc, func, insert, or_, select, text, union_all
from validator import rules, validate
from config import config
from db.database import SessionLocal
from models import usuariotransaccionrol
from models import sapobjeto
from models import sapcampo
from models.actividad import Actividad
from models.appuser import AppUser
from models.campo import Campo
from models.conflicto import Conflicto
from models.job import Job
from models.proceso import Proceso
from models.regla import Regla
from models.riesgo import Riesgo
from models.riesgoactividadtransaccion import RiesgoActividadTransaccion
from models.sapautorizacion import SapAutorizacion
from models.sapcampo import SapCampo
from models.sapcampoproceso import SapCampoProceso as sapcampoproceso
from models.sapcampoorganizacional import SapCampoOrganizacional
from models.sapnivelorganizacional import SapNivelOrganizacional
from models.sapobjeto import SapObjeto
from models.sapobjetoautorizacion import SapObjetoAutorizacion
from models.sapobjetocampo import SapObjetoCampo as sapobjetocampo
from models.sapobjetoproceso import SapObjetoProceso as sapobjetoproceso
from models.sapperfil import SapPerfil
from models.sapperfilobjetoautorizacion import SapPerfilObjetoAutorizacion
from models.saprol import SapRol
from models.saprolobjetoautorizacion import SapRolObjetoAutorizacion
from models.sapusuario import SapUsuario
from models.sapusuarioperfil import SapUsuarioPerfil
from models.sapusuariorol import SapUsuarioRol
from models.sapusuariotipo import SapUsuarioTipo
from models.transaccion import Transaccion as transaccion
from models.usuario import Usuario
from models.usuariotransaccion import UsuarioTransaccion
from models.version import Version
from models.versionusuario import VersionUsuario
from models.versionusuarioobjeto import VersionUsuarioObjeto
from models.versionusuariorol import VersionUsuarioRol
from models.versionusuariotransaccion import VersionUsuarioTransaccion
from models.transaccion import Transaccion as Transaccion
from utils.customValidation import white_space_rule
from security.tokenValidation import token_valid
from security.roleValidation import role_valid
from sqlalchemy.orm import aliased
from utils.helper import Helper
from datetime import datetime, timezone

from azure.identity import DefaultAzureCredential

from utils import storage
from services.nsg_service import *

conflict = Blueprint('conflict', __name__)

comodin = "*"

rules_analize_conflicts = {
  'token': [rules.Required(), white_space_rule],
  'idVersion': [rules.Required(), rules.Integer, rules.Min(1)]
}
@conflict.route('/processForm', methods = ['POST'], )
def process_form():
    session = SessionLocal()
    job_id = ''
    try:
        TZ_LIMA = timezone(timedelta(hours=-5))
        now_dt = datetime.now(TZ_LIMA)

        body = request.json
        id_version = body.get("idVersion")
        token = body.get("token")
        user_id = body.get("idUsuario")

        if not id_version:
            return jsonify({'error': 'Falta idVersion'}), 400
        if token is None:
            return jsonify({'error': 'Falta token'}), 400
        if not user_id:
            return jsonify({'error': 'Falta Id de Usuario'}), 400
        
        job_id = storage.create_job()
        #job_id = 'prb-brnc-1'

        # ================================================================
        # 1. VALIDACIONES INICIALES
        # ================================================================
        pesados = []
        livianos = []
        job_names = []       

        new_job = Job(
            IdJob = job_id,
            IdUsuario = user_id,
            Nombre = f'Ejecución de Version #{id_version}',
            Tipo = "Análisis de Conflictos",
            IdAppUserCreacion = user_id,
            IdAppUserActualizacion = user_id,
            FechaCreacion = now_dt,
            FechaActualizacion = now_dt,
            Estado = 1
        )
        session.add(new_job)
        session.commit()
        session.expunge_all()

        version = session.get(Version, id_version)

        if version is None:
            print(f"Error: No se encontró la versión con id {id_version}")
            storage.update_job_with_errors(job_id, [f"No se encontró la versión con id {id_version}"])
            return

        proceso = session.get(Proceso, version.IdProceso)

        UsuariosTransaccionesExtras = {}
        UsuariosRolesExtras = {}
        UsuariosAutorizacionesExtras = {}

        campo_transaccion = config.TRANSACTION_OBJECT
        IdSistemaSap = config.SYSTEMS['SAP']
        IdSistemaFiori = config.SYSTEMS['FIORI']

        SapObjetoProceso = session.query(sapobjetoproceso
                                            ).filter(sapobjetoproceso.IdMatrizSap == proceso.IdMatrizSap,sapobjetoproceso.Nombre == campo_transaccion
                                                ).order_by(desc(sapobjetoproceso.Id)).first()

        campo_field_transaccion = config.TRANSACTION_FIELD
        SapCampoProceso = session.query(sapcampoproceso
                                            ).filter(sapcampoproceso.IdMatrizSap == proceso.IdMatrizSap,
                                                    sapcampoproceso.Nombre == campo_field_transaccion
                                                    ).order_by(desc(sapcampoproceso.Id)).first()
        
        TransaccionesRegla = session.query(Transaccion.Id.label("id"),Transaccion.Codigo.label("codigo"),Transaccion.Nombre.label("nombre")
                                            ).filter(Transaccion.IdRegla == proceso.IdRegla, Transaccion.IdSistema == IdSistemaSap,Transaccion.Codigo != '').all()

        fechaCorte = proceso.FechaCorte
        print(f"Fecha de Corte de Ejecución: {str(fechaCorte)}")

        if not fechaCorte:
            fechaCorte = now_dt       

        # Filtros Tipo Usuario (Dialogo, Servicio) 
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

        types_dialog_service = union_all(select(sq_dialogo.c.Id), select(sq_servicio.c.Id)).subquery()

        all_users = []

        if version.Completo:
            # Lista real de usuarios            
            all_users = [
                uid for (uid,) in session.query(
                        SapUsuario.IdUsuario
                    )
                    .join(SapUsuarioTipo, and_(SapUsuarioTipo.IdMatrizSap == proceso.IdMatrizSap,SapUsuarioTipo.IdUsuario == SapUsuario.IdUsuario))
                    .filter(
                        SapUsuario.IdMatrizSap == proceso.IdMatrizSap,
                        or_(
                            SapUsuario.FechaInicio == None,
                            SapUsuario.FechaInicio <= fechaCorte
                        ),
                        SapUsuario.FechaFin >= fechaCorte,
                        SapUsuario.Uflag.in_([0, 128]),
                        SapUsuarioTipo.IdTipoUsuario.in_(types_dialog_service)                    
                    ).order_by(SapUsuario.IdUsuario).distinct().all()
            ]
        else:
            UsuariosFilters = []
            Versionusuarios = session.query(VersionUsuario).filter(VersionUsuario.IdVersion == id_version).order_by(desc(VersionUsuario.Id)).all()
            if len(Versionusuarios) > 0:
                for versionusuario in Versionusuarios:
                    IdUsuario = versionusuario.IdUsuario
                    UsuariosFilters.append(IdUsuario)

                    # Extra: transacciones especificadas para el usuario en la versión
                    Versionusuariotransacciones = session.query(
                        VersionUsuarioTransaccion
                        ).filter(VersionUsuarioTransaccion.IdVersionUsuario == versionusuario.Id
                                    ).order_by(desc(VersionUsuarioTransaccion.Id)).all()
                    if len(Versionusuariotransacciones) > 0:
                        for VUT in Versionusuariotransacciones:
                            UsuariosTransaccionesExtras.setdefault(IdUsuario, []).append(VUT.IdTransaccion)

                    # Extra: roles especificados para el usuario
                    Versionusuarioroles = session.query(VersionUsuarioRol).filter(VersionUsuarioRol.IdVersionUsuario == versionusuario.Id).order_by(desc(VersionUsuarioRol.Id)).all()
                    if len(Versionusuarioroles) > 0:
                        for VUR in Versionusuarioroles:
                            IdRol = VUR.IdSapRol
                            UsuariosRolesExtras.setdefault(IdUsuario, []).append(IdRol)

                            # Si hay objeto&campo de transacción, derivar transacciones desde roles
                            if SapObjetoProceso and SapCampoProceso:
                                RoleTransacciones = session.query(SapRolObjetoAutorizacion).filter(SapRolObjetoAutorizacion.IdMatrizSap == proceso.IdMatrizSap,
                                                                                                    SapRolObjetoAutorizacion.IdSapRol == VUR.IdSapRol,
                                                                                                    SapRolObjetoAutorizacion.IdSapObjetoProceso == SapObjetoProceso.Id,
                                                                                                    SapRolObjetoAutorizacion.IdSapCampoProceso == SapCampoProceso.Id,
                                                                                                    SapRolObjetoAutorizacion.Desde != ''
                                                                                                    ).order_by(SapRolObjetoAutorizacion.Desde).all()
                                for RoleTransaccion in RoleTransacciones:
                                    TransaccionCodigo = RoleTransaccion.Desde
                                    # Caso ALL (comodín crudo)
                                    if TransaccionCodigo == comodin:
                                        for item in TransaccionesRegla:
                                            oTransaccion = session.query(Transaccion).get(item.id)
                                            # evitar duplicados
                                            if oTransaccion.Id not in UsuariosTransaccionesExtras[IdUsuario]:
                                                UsuariosTransaccionesExtras[IdUsuario].append(oTransaccion.Id)
                                    # Caso patrón con comodín
                                    elif comodin in str(TransaccionCodigo):
                                        # Filtrar por patrón
                                        TransaccionesCodigo = [
                                            obj for obj in TransaccionesRegla
                                            if fnmatch(obj["codigo"], TransaccionCodigo)
                                        ]
                                        for item in TransaccionesCodigo:
                                            oTransaccion = session.get(Transaccion, item.id)
                                            if oTransaccion.Id not in UsuariosTransaccionesExtras[IdUsuario]:
                                                UsuariosTransaccionesExtras[IdUsuario].append(oTransaccion.Id)
                                    else:
                                        # Igualdad exacta
                                        TransaccionesCodigo = [
                                            obj for obj in TransaccionesRegla
                                            if obj["codigo"] == TransaccionCodigo
                                        ]
                                        if len(TransaccionesCodigo) > 0:
                                            oTransaccion = session.get(Transaccion, TransaccionesCodigo[0].id)
                                            if oTransaccion.id not in UsuariosTransaccionesExtras[IdUsuario]:
                                                UsuariosTransaccionesExtras[IdUsuario].append(oTransaccion.Id)

                    # Extra: objetos autorizaciones explícitas
                    Versionusuarioautorizaciones = session.query(VersionUsuarioObjeto).filter(VersionUsuarioObjeto.IdVersionUsuario == versionusuario.Id).order_by(desc(VersionUsuarioObjeto.Id)).all()
                    if len(Versionusuarioautorizaciones) > 0:
                        for VUA in Versionusuarioautorizaciones:
                            UsuariosAutorizacionesExtras.setdefault(IdUsuario, []).append({
                                    'id_objeto': VUA.IdSapObjetoProceso,
                                    'id_campo': VUA.IdSapCampoProceso,
                                    'desde': VUA.Desde,
                                    'hasta': VUA.Hasta
                                })

                # Usuarios limitados a los filtros de la versión
                all_users = [
                    uid for (uid,) in session.query(SapUsuario.IdUsuario
                        )
                        .join(SapUsuarioTipo, and_(SapUsuarioTipo.IdMatrizSap == proceso.IdMatrizSap,SapUsuarioTipo.IdUsuario == SapUsuario.IdUsuario))
                        .filter(
                            SapUsuario.IdMatrizSap == proceso.IdMatrizSap,
                            or_(
                                SapUsuario.FechaInicio == None,
                                SapUsuario.FechaInicio <= fechaCorte
                              ),
                            SapUsuario.FechaFin >= fechaCorte,
                            SapUsuario.Uflag.in_([0,128]),
                            SapUsuario.IdUsuario.in_(UsuariosFilters),
                            SapUsuarioTipo.IdTipoUsuario.in_(types_dialog_service)
                        ).distinct().all()
                ]

        stmt = (
            select(SapUsuarioRol.IdSapRol,SapUsuarioRol.IdUsuario).where(SapUsuarioRol.IdUsuario.in_(all_users)).distinct()
        )    
        roles_usuario = session.execute(stmt).mappings().all()
        map_roles = defaultdict(list)
        for row in roles_usuario:
            map_roles[row["IdUsuario"]].append(row["IdSapRol"])

        # alias por claridad
        sur = SapUsuarioRol
        sroa = SapRolObjetoAutorizacion

        stmt_conteo = (
            session.query(
                sur.IdUsuario.label("id_usuario"),
                func.count(sroa.IdSapRol).label("total")
            )
            .join(sroa, sroa.IdSapRol == sur.IdSapRol)
            .filter(
                sur.IdUsuario.in_(all_users),
                sroa.Desde != '',
                sroa.IdMatrizSap == proceso.IdMatrizSap
            )
            .group_by(sur.IdUsuario)
        )

        conteos = {row.id_usuario: row.total for row in stmt_conteo}

        for u_id in all_users:
            # Tu lógica de conteo que vimos en la foto
            conteo = conteos.get(u_id, 0)
            if conteo > 100000: # Umbral de "Usuario de Sistema"
                pesados.append(u_id)
            else:
                livianos.append(u_id)

        session.flush()

        print(f"Clasificación terminada para versión #{id_version}: {len(livianos)} livianos, {len(pesados)} pesados.")
        storage.update_progress(job_id, 10)

        # 2. LANZAMIENTO DE LIVIANOS (Carril Rápido - 3 CPUs)
        num_cpus_pool = min(len(livianos), 3)

        shards_livianos = np.array_split(livianos, num_cpus_pool) if len(livianos) > 0 else []      
        shards_pesados =  len(pesados)
        total_shards = len(shards_livianos) + shards_pesados
        idx_shard = 0        

        # 3) Autenticación a ARM con Managed Identity
        managed_identity_client_id = os.getenv("AZURE_CLIENT_ID")
        cred  = DefaultAzureCredential(managed_identity_client_id=managed_identity_client_id)
        token = cred.get_token("https://management.azure.com/.default").token

        # 4) Endpoint REST oficial para iniciar la ejecución del Job (START)        
        subscription_id = os.getenv("SUBSCRIPTION_ID")
        resource_group  = os.getenv("RESOURCE_GROUP")
        job_name        = os.getenv("CONFLICT_CONTAINER_NAME")
        ARM_BASE        = "https://management.azure.com"
        url = (f"{ARM_BASE}/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.App/jobs/{job_name}/start?api-version=2025-07-01")
        
        
        
        def normalize_limit_date(value):
            """
            Devuelve SIEMPRE un string 'YYYY-MM-DD'.
            Acepta: None, date, datetime, string RFC1123, string 'YYYY-MM-DD', string 'YYYY-MM-DD HH:MM:SS'
            """

            # ✅ Caso None → devolver None o lo que tú quieras
            if value is None:
                return None
            
            # ✅ Si es date
            if isinstance(value, date) and not isinstance(value, datetime):
                return value.strftime("%Y-%m-%d")

            # ✅ Si es datetime
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d")

            # ✅ Si es string RFC1123 → convertir
            try:
                # Ej: "Tue, 06 Jan 2026 00:00:00 GMT"
                dt = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z")
                return dt.strftime("%Y-%m-%d")
            except:
                pass

            # ✅ Si ya es "YYYY-MM-DD", devolverlo tal cual
            try:
                dt = datetime.strptime(value, "%Y-%m-%d")
                return dt.strftime("%Y-%m-%d")
            except:
                pass

            # ✅ Si viene "YYYY-MM-DD HH:MM:SS"
            try:
                dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                return dt.strftime("%Y-%m-%d")
            except:
                pass

            raise ValueError(f"Formato no soportado: {value}")
        
        limit_date_str = normalize_limit_date(fechaCorte)


        
        for shard in shards_livianos:            
            idx_shard += 1
            input_json = {
                "id_job": job_id,
                "id_version": id_version,
                "id_user": user_id,
                "user_ids": shard.tolist(),
                "idx_shard": idx_shard,
                "total_shards": total_shards,
                "total_users": len(all_users),
                "type": "liviano",
                "limit_date": limit_date_str
            }
            
            # Enviamos INPUT_JSON como env var (tu runner la lee con os.getenv('INPUT_JSON'))
            body_start = {            
                "containers": [
                    {
                    "name": "runner",
                    "image": "crsodqa.azurecr.io/aca-conflicts:latest",
                    "resources": {
                            "cpu": 1.0,
                            "memory": "2Gi"
                    },
                    "env": [
                        { "name": "APP_ENV", "value": "production" },
                        { "name": "INPUT_JSON", "value": json.dumps(input_json) },
                        { "name": "DB_CONNECTION", "secretRef": "db-connection-secret"},
                        { "name": "PATH_PEM", "value": "/app/certs/mysql-ca-cert" },
                        { "name": "AZUREWEBJOBSTORAGE", "secretRef": "storage-connection-secret"},
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
                azure_execution_id = resp.json().get("name")  # execution name de Azure
                job_names.append(azure_execution_id)

        if len(pesados) > 0:
            idx_shard += 1
            input_json = {
                "id_job": job_id,
                "id_version": id_version,
                "id_user": user_id,
                "user_ids": pesados,
                "idx_shard": idx_shard,
                "total_shards": total_shards,
                "total_users": len(all_users),
                "type": "pesado",
                "limit_date": limit_date_str
            }
            
            # Enviamos INPUT_JSON como env var (tu runner la lee con os.getenv('INPUT_JSON'))
            body_start = {            
                "containers": [
                    {
                    "name": "runner",
                    "image": "crsodqa.azurecr.io/aca-conflicts:latest",
                    "resources": {
                            "cpu": 1.0,
                            "memory": "2Gi"
                    },
                    "env": [
                        { "name": "APP_ENV", "value": "production" },
                        { "name": "INPUT_JSON", "value": json.dumps(input_json) },
                        { "name": "DB_CONNECTION", "secretRef": "db-connection-secret"},
                        { "name": "PATH_PEM", "value": "/app/certs/mysql-ca-cert" },
                        { "name": "AZUREWEBJOBSTORAGE", "secretRef": "storage-connection-secret"},
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
                azure_execution_id = resp.json().get("name")  # execution name de Azure
                job_names.append(azure_execution_id)               
        
        return jsonify({
                "jobId": job_id,                   # tu ID de tracking para el progreso
                "azureExecutionIds": job_names  # los execution names de los Jobs en Azure
            }), 202
    except Exception as e:
        storage.update_job_with_errors(job_id, [e])
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
    
