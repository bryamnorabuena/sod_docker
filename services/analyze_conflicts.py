from datetime import datetime
import fnmatch
import json
import os
import sys
from sqlalchemy.orm import sessionmaker
from config import config
from db.database import SessionLocal
from models import *
from repository.activity_repository import ActivityRepository
from repository.app_user_repository import AppUserRepository
from repository.conflict_repository import ConflictRepository
from repository.process_repository import ProcessRepository
from repository.risk_activity_transaction_repository import RiskActivityTransactionRepository
from repository.risk_repository import RiskRepository
from repository.sap_authorization_repository import SapAuthorizationRepository
from repository.sap_object_authorization_repository import SapObjectAuthorizationRepository
from repository.sap_object_field_repository import SapObjectFieldRepository
from repository.sap_organizational_field_repository import OrganizationalFieldRepository
from repository.sap_organizational_level_repository import OrganizationalLevelRepository
from repository.sap_process_field_repository import SapProcessFieldRepository
from repository.sap_process_object_repository import SapProcessObjectRepository
from repository.sap_profile_repository import SapProfileRepository
from repository.sap_role_object_authorization_repository import SapRoleObjectAuthorizationRepository
from repository.sap_role_repository import SapRoleRepository
from repository.sap_user_profile_repository import SapUserProfileRepository
from repository.sap_user_rol_repository import SapUserRolRepository
from repository.transaction_repository import TransactionRepository
from repository.user_transaction_repository import UserTransactionRepository
from repository.user_transaction_role_repository import UserTransactionRoleRepository
from repository.version_repository import VersionRepository
from repository.log_repository import LogRepository
from repository.version_user_object_repository import VersionUserObjectRepository
from repository.version_user_repository import VersionUserRepository
from repository.version_user_role_repository import VersionUserRoleRepository
from repository.version_user_transaction_repository import VersionUserTransactionRepository
from utils.helper import Helper

class ProcessService:
    def __init__(self, db_session):
        self.db_session = db_session
        self.comodin = "*"
        self.aPerfilAutorizacionesObjetoCampo = {}
        
    def process_execute(self, version_id):
        try:
            start_time = datetime.now()
            batch_count = 0
            user_count = 0

            # Obtener datos básicos
            version = self.db_session.query(Version).get(version_id)
            if not version:
                raise Exception(f"No se encontró la versión con ID {version_id}")
                
            process_id = version.IdProceso            
            process = self.db_session.query(Proceso).get(process_id)
            
            # Campos organizacionales
            campos = ['$BUKRS', '$WERKS']
            sap_nivel_organizacionales = self.db_session.query(SapNivelOrganizacional)\
                .filter(SapNivelOrganizacional.IdProceso==process_id, SapNivelOrganizacional.NivelOrganizacional.in_(campos))\
                .all()
                
            campos_organizacionales = self.db_session.query(SapCampoOrganizacional)\
                .filter_by(IdProceso=process_id)\
                .all()
                
            # Riesgos y actividades
            rule_id = process.IdRegla
            risks = self.db_session.query(Riesgo)\
                .filter_by(IdRegla=rule_id, Estado=1)\
                .all()
                
            risk_activities = {}
            for risk in risks:
                risk_id = risk.Id
                activities = self.db_session.query(RiesgoActividadTransaccion)\
                    .filter_by(IdRiesgo=risk_id, Estado=1)\
                    .group_by(RiesgoActividadTransaccion.IdActividad)\
                    .all()
                risk_activities[risk_id] = activities
                
            # Configuraciones
            campo_transaccion = config.TRANSACTION_FIELD
            id_sistema_sap = config.SYSTEMS["SAP"]
            id_sistema_fiori = config.SYSTEMS["FIORI"]
            
            sap_objeto_proceso = self.db_session.query(SapObjetoProceso)\
                .filter_by(IdProceso=process_id, Nombre=campo_transaccion, Estado=1)\
                .first()
                
            campo_field_transaccion = "TRANSACTION_FIELD_FIELD"  # Debería venir de configuración
            sap_campo_proceso = self.db_session.query(SapCampoProceso)\
                .filter_by(IdProceso=process_id, Nombre=campo_field_transaccion, Estado=1)\
                .first()
                
            sistemas = {"sap": id_sistema_sap}  # Debería venir de configuración
            
            # Transacciones de la regla
            rule_transactions = self.db_session.query(Transaccion)\
                .filter_by(IdRegla=rule_id, IdSistema=sistemas['sap'], Estado=1)\
                .all()
                
            # Preparar datos extras
            extra_user_transactions = {}
            extra_user_roles = {}
            extra_user_auths = {}
            
            # Obtener usuarios según si es versión completa o no
            if version.Completo:
                users = self.db_session.query(UsuarioTransaccion)\
                    .filter_by(IdProceso=process_id, Estado=1)\
                    .group_by(UsuarioTransaccion.IdUsuario)\
                    .all()
            else:
                user_filters = []
                version_users = self.db_session.query(VersionUsuario)\
                    .filter_by(IdVersion=version_id, Estado=1)\
                    .all()
                    
                for version_user in version_users:
                    user_id = version_user.IdUsuario
                    user_filters.append(user_id)
                    
                    # Transacciones extras
                    version_user_transactions = self.db_session.query(VersionUsuarioTransaccion)\
                        .filter_by(IdVersionUsuario=version_user.Id, Estado=1)\
                        .all()
                        
                    if version_user_transactions:
                        extra_user_transactions.setdefault(user_id, [])
                        for vut in version_user_transactions:
                            extra_user_transactions[user_id].append(vut.IdTransaccion)
                            
                    # Roles extras
                    version_user_roles = self.db_session.query(VersionUsuarioRol)\
                        .filter_by(IdVersionUsuario=version_user.Id, Estado=1)\
                        .all()
                        
                    if version_user_roles:
                        extra_user_roles.setdefault(user_id, [])
                        for vur in version_user_roles:
                            role_id = vur.IdSapRol
                            extra_user_roles[user_id].append(role_id)
                            
                            # Buscar transacciones de roles
                            if sap_objeto_proceso and sap_campo_proceso:
                                role_transactions = self.db_session.query(SapRolObjetoAutorizacion)\
                                    .filter_by(
                                        IdProceso=process_id,
                                        IdSapRol=role_id,
                                        IdSapObjetoProceso=sap_objeto_proceso.Id,
                                        IdSapCampoProceso=sap_campo_proceso.Id,
                                        Estado=1
                                    )\
                                    .all()
                                    
                                for role_trans in role_transactions:
                                    transaccion = role_trans.Desde
                                    
                                    if transaccion == self.comodin:  # SAP ALL
                                        for rt in rule_transactions:
                                            if rt.Id not in extra_user_transactions.get(user_id, []):
                                                extra_user_transactions.setdefault(user_id, []).append(rt.Id)
                                                
                                    elif self.comodin in transaccion:  # Patrón (ej: FI*)
                                        matching = [t for t in rule_transactions 
                                                   if fnmatch.fnmatch(t.Codigo, transaccion)]
                                        for match in matching:
                                            if match.Id not in extra_user_transactions.get(user_id, []):
                                                extra_user_transactions.setdefault(user_id, []).append(match.Id)
                                                
                                    else:  # Transacción exacta
                                        exact = [t for t in rule_transactions 
                                               if t.Codigo == transaccion]
                                        if exact:
                                            if exact[0].Id not in extra_user_transactions.get(user_id, []):
                                                extra_user_transactions.setdefault(user_id, []).append(exact[0].Id)
                                                
                    # Autorizaciones extras
                    user_auths = self.db_session.query(VersionUsuarioObjeto)\
                        .filter_by(IdVersionUsuario=version_user.Id, Estado=1)\
                        .all()
                        
                    for auth in user_auths:
                        extra_user_auths.setdefault(user_id, []).append({
                            'id_objeto': auth.IdSapObjetoProceso,
                            'id_campo': auth.IdSapCampoProceso,
                            'desde': auth.Desde,
                            'hasta': auth.Hasta
                        })
                
                # Obtener usuarios con transacciones
                users = self.db_session.query(UsuarioTransaccion)\
                    .filter_by(IdProceso=process_id, Estado=1)\
                    .filter(UsuarioTransaccion.IdUsuario.in_(user_filters))\
                    .group_by(UsuarioTransaccion.IdUsuario)\
                    .all()
            
            # Procesar cada usuario
            for user_trans in users:
                user_start = datetime.now()
                batch_count += 1
                user_count += 1
                
                user_id = user_trans.IdUsuario
                user = self.db_session.query(Usuario).get(user_id)
                user_code = user.Usuario
                
                # Obtener transacciones del usuario
                user_transactions = self.db_session.query(UsuarioTransaccion)\
                    .filter_by(IdProceso=process_id, IdUsuario=user_id, Estado=1)\
                    .all()
                    
                user_trans_ids = [ut.IdTransaccion for ut in user_transactions]
                
                # Agregar transacciones extras si existen
                if user_id in extra_user_transactions:
                    user_trans_ids.extend(extra_user_transactions[user_id])
                
                # Procesar cada riesgo
                for risk in risks:
                    risk_id = risk.Id
                    risk_code = risk.Codigo
                    
                    total_activities = len(risk_activities.get(risk_id, []))
                    activity_count = 0
                    risk_activity_trans = []
                    
                    # Verificar actividades del riesgo
                    for activity in risk_activities.get(risk_id, []):
                        activity_id = activity.IdActividad
                        records = self.db_session.query(RiesgoActividadTransaccion)\
                            .filter_by(
                                IdRiesgo=risk_id,
                                IdActividad=activity_id,
                                Estado=1
                            )\
                            .filter(RiesgoActividadTransaccion.IdTransaccion.in_(user_trans_ids))\
                            .all()
                            
                        if records:
                            activity_count += 1
                            risk_activity_trans.extend(records)
                    
                    # Si todas las actividades tienen transacciones
                    if total_activities == activity_count:
                        activities_data = {}
                        activities_fiori = {}
                        risks_data = []
                        
                        for rat in risk_activity_trans:
                            risk_id = rat.IdRiesgo
                            activity_id = rat.IdActividad
                            trans_id = rat.IdTransaccion
                            
                            if activity_id not in activities_data:
                                activities_data[activity_id] = {
                                    "transacciones": [],
                                    "condition": False
                                }
                            activities_data[activity_id]["transacciones"].append(trans_id)
                            
                            # Verificar si es transacción Fiori
                            trans = self.db_session.query(Transaccion).get(rat.IdTransaccion)
                            if trans.IdSistema == id_sistema_fiori:
                                if activity_id not in activities_fiori:
                                    activities_fiori[activity_id] = {"transacciones": {}}
                                activities_fiori[activity_id]["transacciones"][trans_id] = trans_id
                            
                            risks_data.append({
                                "id": rat.Id,
                                "id_riesgo": risk_id,
                                "id_actividad": activity_id,
                                "id_transaccion": trans_id
                            })
                        
                        # Buscar autorizaciones por perfil
                        auth_result = self.find_object_authorization_by_profile(
                            sap_nivel_organizacionales,
                            process_id,
                            rule_id,
                            user_id,
                            activities_data,
                            activities_fiori,
                            extra_user_roles.get(user_id, []),
                            extra_user_auths.get(user_id, []),
                            campos_organizacionales
                        )
                        
                        if auth_result["condition"] == True:
                            for activity_id, activity_data in auth_result["actividad"].items():
                                for trans_id in activity_data["transaccion"]:
                                    # Filtrar riesgos para esta actividad y transacción
                                    filtered_risks = [
                                        r for r in risks_data 
                                        if r["id_actividad"] == activity_id and r["id_transaccion"] == trans_id
                                    ]
                                    
                                    if filtered_risks:
                                        transaction = self.db_session.query(Transaccion).get(trans_id)
                                        
                                        # Para transacciones SAP
                                        if transaction.Id_sistema == id_sistema_sap:
                                            profiles_data = activity_data["transaccion_perfiles"].get(trans_id, [])
                                            
                                            for profile_data in profiles_data:
                                                conflict = conflict(
                                                    IdVersion=version_id,
                                                    IdUsuario=user_id,
                                                    IdSapPerfil=profile_data["id_sap_perfil"],
                                                    IdSapAutorizacion=profile_data["id_sap_autorizacion"],
                                                    IdSapRol=profile_data["id_sap_rol"],
                                                    IdRiesgoActividadTransaccion=filtered_risks[0]["id"],
                                                    IdRiesgo=filtered_risks[0]["id_riesgo"],
                                                    IdActividad=filtered_risks[0]["id_actividad"],
                                                    IdTransaccion=filtered_risks[0]["id_transaccion"],
                                                    IdSapObjetoProceso=profile_data["id_objeto"],
                                                    IdSapCampoProceso=profile_data["id_campo"],
                                                    Desde=profile_data["desde"],
                                                    Hasta=profile_data["hasta"],
                                                    IdAppUserCreacion=1,  # Usuario por defecto
                                                    IdAppUserActualizacion=1,
                                                    FechaCreacion=datetime.now().timestamp(),
                                                    FEchaActualizacion=datetime.now().timestamp(),
                                                    Estado=1
                                                )
                                                self.db_session.add(conflict)
                                                
                                                if batch_count == 100:
                                                    self.db_session.commit()
                                                    batch_count = 0
                                        
                                        # Para transacciones Fiori
                                        elif transaction.Id_sistema == id_sistema_fiori:
                                            data_roles = self.db_session.query(UsuarioTransaccionRol)\
                                                .filter_by(
                                                    IdProceso=process_id,
                                                    IdUsuario=user_id,
                                                    IdTransaccion=trans_id,
                                                    Estado=1
                                                )\
                                                .all()
                                                
                                            if data_roles:
                                                for role in data_roles:
                                                    conflict = Conflicto(
                                                        IdVersion=version_id,
                                                        IdUsuario=user_id,
                                                        IdSapPerfil=None,
                                                        IdSapAutorizacion=None,
                                                        IdSapRol=role.Id_sap_rol,
                                                        IdRiesgoActividadTransaccion=filtered_risks[0]["id"],
                                                        IdRiesgo=filtered_risks[0]["id_riesgo"],
                                                        IdActividad=filtered_risks[0]["id_actividad"],
                                                        IdTransaccion=filtered_risks[0]["id_transaccion"],
                                                        IdSapObjetoProceso=None,
                                                        IdSapCampoProceso=None,
                                                        Desde="",
                                                        Hasta="",
                                                        IdAppUserCreacion=1,
                                                        IdAppUserActualizacion=1,
                                                        FechaCreacion=datetime.now().timestamp(),
                                                        FEchaActualizacion=datetime.now().timestamp(),
                                                        Estado=1
                                                    )
                                                    self.db_session.add(conflict)
                                                    
                                                    if batch_count == 100:
                                                        self.db_session.commit()
                                                        batch_count = 0
                
                # Finalizar procesamiento del usuario
                self.db_session.commit()
                user_time = (datetime.now() - user_start).total_seconds()
                print(f"Usuario {user_count}: {user_code} procesado en {user_time:.2f}s")
            
            # Finalizar proceso
            total_time = (datetime.now() - start_time).total_seconds()
            
            # Actualizar estadísticas
            conflict_count = self.db_session.query(Conflicto)\
                .filter_by(id_version=version_id, Estado=1)\
                .count()
                
            process.tiempo = total_time
            process.cantidad = conflict_count
            process.procesado = True
            
            version.tiempo = version.tiempo + total_time if version.tiempo else total_time
            version.cantidad = version.cantidad + conflict_count if version.cantidad else conflict_count
            version.procesado = True
            
            #self.db_session.commit()
            
            return {
                "status": "success",
                "message": f"Procesamiento completado con {conflict_count} conflictos encontrados",
                "user_count": user_count,
                "conflict_count": conflict_count,
                "execution_time": total_time
            }
            
        except Exception as e:
            self.db_session.rollback()
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(f"Error at {fname}:{exc_tb.tb_lineno}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def find_object_authorization_by_profile(self, sap_nivel_organizacionales, process_id, rule_id, user_id, 
                                      activities_data, activities_fiori, extra_roles, extra_auths, 
                                      campos_organizacionales):
        try:    
            aux = []
            now = datetime.now().timestamp()
            max_date_sap = datetime.strptime(config.MAX_DATE_SAP, '%Y-%m-%d %H:%M:%S')
            max_date_php = datetime.strptime(config.MAX_DATE_PHP, '%Y-%m-%d %H:%M:%S')
            
            result_profiles = {
                "condition": False,
                "actividad": {}
            }
            
            # Mantener referencia a aPerfilAutorizacionesObjetoCampo
            aPerfilAutorizacionesObjetoCampo = self.aPerfilAutorizacionesObjetoCampo
            
            # 1. Obtener información agrupada por perfil
            sap_perfiles_usuario = SapUserProfileRepository().get_active_group_user_profile_by_process_user(process_id, user_id)
            
            backup_activities = activities_data.copy()
            profile_ids = [profile["PROFILE_ID"] for profile in sap_perfiles_usuario]
            
            # Restaurar actividades originales
            activities_data = backup_activities.copy()
            result_profiles = {"condition": False, "actividad": {}}
            
            aCondicional = {}
            
            # Procesar cada actividad
            for activity_id, activity in activities_data.items():
                # Convertir transacciones a IDs enteros
                trans_ids = [int(t) for t in activity["transacciones"]]
                
                result_profiles["actividad"][activity_id] = {
                    "condition": False,
                    "transaccion": [],
                    "transaccion_perfiles": {},
                    "roles": {},
                    "bukrs": [],
                    "werks": []
                }
                
                aObjetosCampos = {}
                
                # Procesar transacciones Fiori
                for trans_id in activity["transacciones"]:
                    if (activity_id in activities_fiori and 
                        "transacciones" in activities_fiori[activity_id] and 
                        trans_id in activities_fiori[activity_id]["transacciones"]):
                        
                        codigo_objeto = '1'
                        codigo_campo = '1'
                        id_objeto = 1
                        id_campo = 1
                        desde = '*'
                        hasta = '*'
                        
                        if trans_id not in aObjetosCampos:
                            aObjetosCampos[trans_id] = {
                                "objetos": {},
                                "condition": True,
                                "perfil": []
                            }
                        
                        if codigo_objeto not in aObjetosCampos[trans_id]["objetos"]:
                            aObjetosCampos[trans_id]["objetos"][codigo_objeto] = {
                                "campos": {},
                                "condition": True,
                                "id_objeto": id_objeto
                            }
                        
                        if codigo_campo not in aObjetosCampos[trans_id]["objetos"][codigo_objeto]["campos"]:
                            aObjetosCampos[trans_id]["objetos"][codigo_objeto]["campos"][codigo_campo] = {
                                "valores": [],
                                "condition": True,
                                "id_campo": id_campo,
                                "autorizacion": []
                            }
                        
                        valores = {
                            "desde": desde,
                            "hasta": hasta,
                            "condition": True
                        }
                        aObjetosCampos[trans_id]["objetos"][codigo_objeto]["campos"][codigo_campo]["valores"].append(valores)
                
                # Obtener información de autorización de objetos de la matriz SOD
                sap_objeto_campos = SapObjectFieldRepository().get_active_by_rule_activity_transaction(rule_id,activity_id,activity["transacciones"])
                
                aCondicional = {}
                
                for sap_objeto_campo in sap_objeto_campos:
                    trans_id = sap_objeto_campo["TRANSACTION_ID"]
                    id_objeto = sap_objeto_campo["OBJECT_ID"]
                    codigo_objeto = sap_objeto_campo["OBJECT_NAME"]
                    id_campo = sap_objeto_campo["FIELD_ID"]
                    codigo_campo = sap_objeto_campo["FIELD_NAME"]
                    desde = sap_objeto_campo["FROM_VALUE"]
                    hasta = sap_objeto_campo["TO_VALUE"]
                    condicional = sap_objeto_campo["IS_CONDITIONAL"] or "OR"
                    
                    # Contar condiciones
                    if activity_id not in aCondicional:
                        aCondicional[activity_id] = {}
                    if trans_id not in aCondicional[activity_id]:
                        aCondicional[activity_id][trans_id] = {}
                    if codigo_objeto not in aCondicional[activity_id][trans_id]:
                        aCondicional[activity_id][trans_id][codigo_objeto] = {}
                    if codigo_campo not in aCondicional[activity_id][trans_id][codigo_objeto]:
                        aCondicional[activity_id][trans_id][codigo_objeto][codigo_campo] = {}
                    
                    aCondicional[activity_id][trans_id][codigo_objeto][codigo_campo][condicional] = \
                        aCondicional[activity_id][trans_id][codigo_objeto][codigo_campo].get(condicional, 0) + 1
                    
                    # Estructurar datos de objetos y campos
                    if trans_id not in aObjetosCampos:
                        aObjetosCampos[trans_id] = {
                            "objetos": {},
                            "condition": False,
                            "perfil": []
                        }
                    
                    if codigo_objeto not in aObjetosCampos[trans_id]["objetos"]:
                        aObjetosCampos[trans_id]["objetos"][codigo_objeto] = {
                            "campos": {},
                            "condition": False,
                            "id_objeto": id_objeto
                        }
                    
                    if codigo_campo not in aObjetosCampos[trans_id]["objetos"][codigo_objeto]["campos"]:
                        aObjetosCampos[trans_id]["objetos"][codigo_objeto]["campos"][codigo_campo] = {
                            "valores": [],
                            "condition": False,
                            "id_campo": id_campo
                        }
                    
                    valores = {
                        "desde": desde,
                        "hasta": hasta,
                        "condition": False
                    }
                    aObjetosCampos[trans_id]["objetos"][codigo_objeto]["campos"][codigo_campo]["valores"].append(valores)
                
                if aObjetosCampos:
                    for trans_id, objetos in aObjetosCampos.items():
                        for objeto, campos in objetos["objetos"].items():
                            id_objeto = campos["id_objeto"]
                            
                            for campo, valores in campos["campos"].items():
                                id_campo = valores["id_campo"]
                                bol_campo_organizacional = False
                                
                                # Verificar si es campo organizacional
                                campo_organizacional = [c for c in campos_organizacionales if c.Campo == campo]
                                
                                id_sap_objeto_proceso_of_risk = None
                                id_sap_campo_proceso_of_risk = None
                                
                                if campo_organizacional:
                                    bol_campo_organizacional = True
                                    sap_objeto_proceso = SapProcessObjectRepository().get_active_by_process_name(process_id, objeto)
                                    if sap_objeto_proceso:
                                        id_sap_objeto_proceso_of_risk = sap_objeto_proceso[0]["SAP_PROC_OBJ_ID"]
                                    
                                    sap_campo_proceso = SapProcessFieldRepository().get_active_by_process_name(process_id, campo)
                                    
                                    if sap_campo_proceso:
                                        id_sap_campo_proceso_of_risk = sap_campo_proceso[0]["SAP_PROC_FIELD_ID"]
                                
                                bol_campo = False
                                
                                # Obtener autorizaciones de perfiles
                                sap_perfiles_autorizaciones = SapUserProfileRepository().get_active_group_profile_auth_role_by_process_user(process_id, user_id, objeto)
                                
                                # Agregar roles extras si existen
                                roles_extras_new = []
                                if extra_roles:
                                    for rol_extra in extra_roles:
                                        exists = [r for r in sap_perfiles_autorizaciones 
                                                if r["ROLE_ID"] == rol_extra]
                                        
                                        if not exists:
                                            for sap_perfil_autorizacion in sap_perfiles_autorizaciones:
                                                roles_extras_new.append({
                                                    "id_perfil": sap_perfil_autorizacion["PROFILE_ID"],
                                                    "id_autorizacion": sap_perfil_autorizacion["AUTHORIZATION_ID"],
                                                    "id_rol": rol_extra,
                                                    "extra": True
                                                })
                                
                                if roles_extras_new:
                                    sap_perfiles_autorizaciones.extend(roles_extras_new)
                                
                                # Procesar autorizaciones
                                for sap_perfil_autorizacion in sap_perfiles_autorizaciones:
                                    id_perfil = sap_perfil_autorizacion["PROFILE_ID"]
                                    id_sap_autorizacion = sap_perfil_autorizacion["AUTHORIZATION_ID"]
                                    bol_rol = True
                                    is_extra = "extra" in sap_perfil_autorizacion
                                    
                                    # Verificar validez del rol
                                    if sap_perfil_autorizacion["ROLE_ID"] and not is_extra:
                                        dato_roles = SapUserRolRepository().get_active_group_user_role_by_process_user_role(process_id, user_id, sap_perfil_autorizacion["ROLE_ID"])
                                        
                                        if dato_roles:
                                            for dato_rol in dato_roles:
                                                try:
                                                    fecha_inicio = int(dato_rol['START_DATE'].timestamp())
                                                except (AttributeError, OSError):
                                                    fecha_inicio = 0

                                                try:
                                                    fecha_fin = int(dato_rol['END_DATE'].timestamp())
                                                except (AttributeError, OSError):
                                                    fecha_fin = int(max_date_php.timestamp())
                                                
                                                if fecha_fin == max_date_sap:
                                                    fecha_fin = max_date_php
                                                
                                                if not (fecha_inicio <= now <= fecha_fin):
                                                    bol_rol = False
                                                else:
                                                    bol_rol = True
                                                    break
                                    
                                    if bol_rol:
                                        id_sap_rol = sap_perfil_autorizacion["ROLE_ID"] or config.DEFAULT_ROL_ID
                                        
                                        # Inicializar estructura si no existe
                                        if (id_perfil not in aPerfilAutorizacionesObjetoCampo or 
                                            id_sap_autorizacion not in aPerfilAutorizacionesObjetoCampo[id_perfil] or
                                            objeto not in aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion] or
                                            campo not in aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto]):
                                            
                                            campo_valores = []
                                            
                                            if not is_extra:
                                                # Obtener autorizaciones normales
                                                campo_valores = SapObjectAuthorizationRepository().get_active_by_process_auth_object_field(process_id, id_sap_autorizacion, objeto, campo)
                                                if campo_valores is None:
                                                    campo_valores = []
                                                
                                                if bol_campo_organizacional:
                                                    # Buscar en autorización de objetos
                                                    add_campo_valores = OrganizationalLevelRepository().get_active_by_process_role_field(process_id, id_sap_rol, campo)
                                                    
                                                    for add_campo_valor in add_campo_valores:
                                                        campo_valores.append({
                                                            "id_objeto": id_sap_objeto_proceso_of_risk,
                                                            "id_campo": id_sap_campo_proceso_of_risk,
                                                            "desde": add_campo_valor["FROM_VALUE"],
                                                            "hasta": add_campo_valor["TO_VALUE"]
                                                        })
                                                    
                                                    # Buscar en autorización de roles
                                                    rol_campo_valores = SapRoleObjectAuthorizationRepository().get_active_by_process_role_object_field(process_id, id_sap_rol, objeto, campo)
                                                    
                                                    for rol_campo_valor in rol_campo_valores:
                                                        campo_valores.append({
                                                            "id_objeto": rol_campo_valor["id_objeto"],
                                                            "id_campo": rol_campo_valor["id_campo"],
                                                            "desde": rol_campo_valor["desde"],
                                                            "hasta": rol_campo_valor["hasta"]
                                                        })
                                            else:
                                                # Obtener autorizaciones extras
                                                campo_valores = SapRoleObjectAuthorizationRepository().get_active_by_process_role_object_field(process_id, id_sap_rol, objeto, campo)
                                                if campo_valores is None:
                                                    campo_valores = []
                                                
                                                if bol_campo_organizacional:
                                                    add_campo_valores = OrganizationalLevelRepository().get_active_by_process_role_field(process_id, id_sap_rol, campo)
                                                    
                                                    for add_campo_valor in add_campo_valores:
                                                        campo_valores.append({
                                                            "id_objeto": id_sap_objeto_proceso_of_risk,
                                                            "id_campo": id_sap_campo_proceso_of_risk,
                                                            "desde": add_campo_valor["FROM_VALUE"],
                                                            "hasta": add_campo_valor["TO_VALUE"]
                                                        })
                                            
                                            # Inicializar estructura
                                            if id_perfil not in aPerfilAutorizacionesObjetoCampo:
                                                aPerfilAutorizacionesObjetoCampo[id_perfil] = {}
                                            if id_sap_autorizacion not in aPerfilAutorizacionesObjetoCampo[id_perfil]:
                                                aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion] = {}
                                            if objeto not in aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion]:
                                                aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto] = {}
                                            if campo not in aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto]:
                                                aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto][campo] = []
                                            
                                            # Agregar valores
                                            if campo_valores:
                                                for campo_valor in campo_valores:
                                                    aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto][campo].append({
                                                        "ID_OBJETO": campo_valor["id_objeto"],
                                                        "ID_CAMPO": campo_valor["id_campo"],
                                                        "DESDE": campo_valor["desde"],
                                                        "HASTA": campo_valor["hasta"],
                                                        "EXTRA": is_extra
                                                    })
                                            else:
                                                campo_valores = []
                                            
                                            # Agregar autorizaciones extras si existen
                                            if extra_auths:
                                                for auth_extra in extra_auths:
                                                    aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto][campo].append({
                                                        "ID_OBJETO": auth_extra["id_objeto"],
                                                        "ID_CAMPO": auth_extra["id_campo"],
                                                        "DESDE": auth_extra["desde"],
                                                        "HASTA": auth_extra["hasta"],
                                                        "EXTRA": True
                                                    })
                                        else:
                                            # Para autorizaciones extras existentes
                                            campo_valores = []
                                            if is_extra:
                                                campo_valores = SapRoleObjectAuthorizationRepository().get_active_by_process_role_object_field(process_id, id_sap_rol, objeto, campo)
                                                
                                                if bol_campo_organizacional:
                                                    add_campo_valores = OrganizationalLevelRepository().get_active_by_process_role_field(process_id, id_sap_rol, campo)
                                                    
                                                    for add_campo_valor in add_campo_valores:
                                                        campo_valores.append({
                                                            "id_objeto": id_objeto,
                                                            "id_campo": id_campo,
                                                            "desde": add_campo_valor["desde"],
                                                            "hasta": add_campo_valor["hasta"]
                                                        })
                                            
                                            for campo_valor in campo_valores:
                                                aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto][campo].append({
                                                    "ID_OBJETO": campo_valor["id_objeto"],
                                                    "ID_CAMPO": campo_valor["id_campo"],
                                                    "DESDE": campo_valor["desde"],
                                                    "HASTA": campo_valor["hasta"],
                                                    "EXTRA": is_extra
                                                })
                                            
                                            if extra_auths:
                                                for auth_extra in extra_auths:
                                                    aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto][campo].append({
                                                        "ID_OBJETO": auth_extra["id_objeto"],
                                                        "ID_CAMPO": auth_extra["id_campo"],
                                                        "DESDE": auth_extra["desde"],
                                                        "HASTA": auth_extra["hasta"],
                                                        "EXTRA": True
                                                    })
                                        
                                        # Comparar autorizaciones
                                        if (id_perfil in aPerfilAutorizacionesObjetoCampo and 
                                            id_sap_autorizacion in aPerfilAutorizacionesObjetoCampo[id_perfil] and
                                            objeto in aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion] and
                                            campo in aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto]):
                                            
                                            for campo_valor in aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto][campo]:
                                                id_sap_objeto_proceso = campo_valor["ID_OBJETO"]
                                                id_sap_campo_proceso = campo_valor["ID_CAMPO"]
                                                desde_perfil = campo_valor["DESDE"].strip()
                                                hasta_perfil = campo_valor["HASTA"].strip()
                                                
                                                for valor in valores["valores"]:
                                                    desde = valor["desde"].strip()
                                                    hasta = valor["hasta"].strip()
                                                    
                                                    # Llamar al helper de comparación
                                                    results = Helper.bol_campo_find_object_authorization(
                                                        bol_campo, desde, desde_perfil, hasta, hasta_perfil, 
                                                        self.comodin, result_profiles, activity_id, trans_id, 
                                                        id_perfil, id_sap_autorizacion, id_sap_rol, 
                                                        id_sap_objeto_proceso, objeto, id_sap_campo_proceso, campo)                                                    
                                                    
                                                    bol_campo = results["BolCampo"]
                                                    result_profiles = results["aResultPerfiles"]
                                                    
                                                    if bol_campo:                                                       
                                                        aObjetosCampos[trans_id]["objetos"][objeto]["campos"][campo]["condition"] = bol_campo                                                            
                                                        aObjetosCampos[trans_id]["objetos"][objeto]["campos"][campo]["autorizacion"] = []
                                                        aObjetosCampos[trans_id]["objetos"][objeto]["campos"][campo]["autorizacion"].append({
                                                            "ID": id_sap_autorizacion,
                                                            "ID_ROL": id_sap_rol
                                                        })
                                                        bol_campo = False
                                        
                                        # Limpiar autorizaciones extras
                                        if is_extra:
                                            if (id_perfil in aPerfilAutorizacionesObjetoCampo and 
                                                id_sap_autorizacion in aPerfilAutorizacionesObjetoCampo[id_perfil] and
                                                objeto in aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion] and
                                                campo in aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto]):
                                                del aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto][campo]
                                        else:
                                            # Eliminar solo las extras
                                            if (id_perfil in aPerfilAutorizacionesObjetoCampo and 
                                                id_sap_autorizacion in aPerfilAutorizacionesObjetoCampo[id_perfil] and
                                                objeto in aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion] and
                                                campo in aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto]):
                                                
                                                aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto][campo] = [
                                                    cv for cv in aPerfilAutorizacionesObjetoCampo[id_perfil][id_sap_autorizacion][objeto][campo] 
                                                    if not (cv["EXTRA"] or False)
                                                ]
                                        
                                        # Registrar rol
                                        if id_sap_rol not in result_profiles["actividad"][activity_id]["roles"]:
                                            result_profiles["actividad"][activity_id]["roles"][id_sap_rol] = id_sap_rol
                        
                        # Verificar condiciones de campos
                        campos_true = 0
                        total_campos = len(campos["campos"])
                        
                        # Validar autorizaciones
                        autorizaciones = {}
                        autorizaciones_validas = []
                        autorizaciones_invalidas = []
                        
                        for campo, valores in campos["campos"].items():
                            if valores["condition"]:
                                for auth in valores["autorizacion"]:
                                    autorizaciones[auth["ID"]] = auth["ID"]
                        
                        # Verificar autorizaciones completas
                        for auth_id in autorizaciones:
                            auth_count = 0
                            
                            for campo, valores in campos["campos"].items():
                                condicion = aObjetosCampos[trans_id]["objetos"][objeto]["campos"][campo]["condition"]
                                if condicion:
                                    rAutorizaciones = aObjetosCampos[trans_id]["objetos"][objeto]["campos"][campo]["autorizacion"]
                                    matching = [a for a in rAutorizaciones if a["ID"] == auth_id]
                                    if matching:
                                        auth_count += 1
                            
                            if auth_count == total_campos:
                                autorizaciones_validas.append(auth_id)
                            else:
                                autorizaciones_invalidas.append(auth_id)
                        
                        # Si no hay autorizaciones válidas, resetear campos
                        if not autorizaciones_validas:
                            for campo, valores in campos["campos"].items():
                                aObjetosCampos[trans_id]["objetos"][objeto]["campos"][campo]["condition"] = False
                        
                        # Eliminar autorizaciones inválidas
                        if autorizaciones_invalidas:
                            if trans_id in result_profiles["actividad"][activity_id]["transaccion_perfiles"]:
                                for auth_invalida in autorizaciones_invalidas:
                                    result_profiles["actividad"][activity_id]["transaccion_perfiles"][trans_id] = [
                                        p for p in result_profiles["actividad"][activity_id]["transaccion_perfiles"][trans_id]
                                        if not (p["IdTransaccion"] == trans_id and 
                                            p["IdSapAutorizacion"] == auth_invalida and 
                                            p["Objeto"] == objeto)
                                    ]
                        
                        # Contar campos válidos
                        total_campos = len(campos["campos"])
                        campos_true = 0
                        for campo, valores in campos["campos"].items():
                            condicion = aObjetosCampos[trans_id]["objetos"][objeto]["campos"][campo]["condition"]
                            if condicion is True:
                                campos_true += 1
                        
                        # Si todos los campos son válidos, marcar objeto como válido
                        if campos_true == total_campos:
                            aObjetosCampos[trans_id]["objetos"][objeto]["condition"] = True
                        
                        # Registrar condición en resultados
                        result_profiles["actividad"][activity_id]["transaccion_objeto"] = {}
                        result_profiles["actividad"][activity_id]["transaccion_objeto"][trans_id] = {}
                        result_profiles["actividad"][activity_id]["transaccion_objeto"][trans_id][objeto] = {} 
                        result_profiles["actividad"][activity_id]["transaccion_objeto"][trans_id][objeto][campo] = \
                            aObjetosCampos[trans_id]["objetos"][objeto]["condition"]
                    
                    # Verificar condiciones de objetos
                    objetos_true = 0
                    for objeto in objetos["objetos"]:
                        condicion = aObjetosCampos[trans_id]["objetos"][objeto]["condition"]
                        if condicion is True:
                            objetos_true += 1
                    total_objetos = len(objetos["objetos"])
                    
                    # Si todos los objetos son válidos, marcar transacción como válida
                    if objetos_true == total_objetos:
                        aObjetosCampos[trans_id]["condition"] = True
                        result_profiles["actividad"][activity_id]["transaccion"].append(trans_id)
                
                # Verificar condiciones de transacciones
                transacciones_validas = [t for t in aObjetosCampos.values() if t["condition"]]
                
                if transacciones_validas:
                    activities_data[activity_id]["condition"] = True
                    result_profiles["actividad"][activity_id]["condition"] = True
            
            # Verificar condiciones finales
            total_actividades = len(activities_data)
            actividades_validas = [a for a in activities_data.values() if a["condition"]]
            
            # Actualizar variable de instancia
            self.aPerfilAutorizacionesObjetoCampo = aPerfilAutorizacionesObjetoCampo
            
            # Si todas las actividades son válidas, marcar como condición cumplida
            if total_actividades == len(actividades_validas):
                result_profiles["condition"] = True
            
            # Lógica adicional (comentada en el original)
            if result_profiles["condition"] and False:
                result_profiles = self.add_actividad_rol_campo(
                    result_profiles, sap_nivel_organizacionales, '$BUKRS', "Bukrs")
                
                if not self.bol_actividad_rol_campo(result_profiles, "Bukrs", self.comodin):
                    result_profiles = self.add_actividad_rol_campo(
                        result_profiles, sap_nivel_organizacionales, '$WERKS', "Werks")
                    
                    if not self.bol_actividad_rol_campo(result_profiles, "Werks", self.comodin):
                        result_profiles["condition"] = False
            
            return result_profiles
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(f"Error at {fname}:{exc_tb.tb_lineno}: {e}")
            raise Exception(str(e))
