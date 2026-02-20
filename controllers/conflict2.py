from collections import defaultdict
from datetime import datetime
import os
import sys
import time
from fnmatch import fnmatch
from pathlib import Path
from flask import Blueprint, request, current_app, session, abort, jsonify
from validator import rules, validate
from config import config
from db.database import SessionLocal
from models.conflicto import Conflicto
from models.proceso import Proceso
from models.riesgoactividadtransaccion import RiesgoActividadTransaccion
from repository.activity_repository import ActivityRepository
from repository.app_user_repository import AppUserRepository
from repository.conflict_repository import ConflictRepository
from repository.log_repository import LogRepository
from repository.mapping.version import Version
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

from repository.version_user_object_repository import VersionUserObjectRepository
from repository.version_user_repository import VersionUserRepository
from repository.version_user_role_repository import VersionUserRoleRepository
from repository.version_user_transaction_repository import VersionUserTransactionRepository
from utils.customValidation import white_space_rule
from security.tokenValidation import token_valid
from security.roleValidation import role_valid
from utils.config import ROLE_SYSADMIN, ROLE_PROJADMIN, ROLE_PROJEDIT, ROLE_CUSTOMER, NO_FOUND_TOKEN, HTTP_ERROR_DICT
from utils.log import SaveStorage, GetIpAddress
from utils.response_handler import BaseResponse
from utils.helper import Helper

conflict2 = Blueprint('conflict2', __name__)

comodin = "*"

rules_analize_conflicts = {
  'token': [rules.Required(), white_space_rule],
  'idVersion': [rules.Required(), rules.Integer, rules.Min(1)]
}
@conflict2.route('/analizeConflicts', methods = ['POST'], )
def analize_conflicts():
  try:
    current_app.logger.info('SOD: Análisis de conflictos - Inicio')

    data = request.json
    db_session = SessionLocal()                         

    if validate(data, rules_analize_conflicts):
      if 'token' in data:
        #token_valid(current_app, session, abort, data['token'])
        token_data = session['tokenData']

        allowed_roles = [ROLE_SYSADMIN, ROLE_PROJADMIN, ROLE_PROJEDIT, ROLE_CUSTOMER]
        #role_valid(current_app, abort, token_data['roles'], allowed_roles)
    
        
        status = "Error"
        title = "Error"
        message = ""
        time_start = time.perf_counter()
        user_counter = 0
        batch_counter = 0
        batch_conflicts = []
        conflict_count = 0
        
        log_file = Path('/home/sodedwinartola/public_html/public/datos.txt')

        # Get app user 
        app_user = AppUserRepository().find_user_app(1)
        app_user = app_user[0]

        # Obtiene la version
        version = VersionRepository().find_version_by_id(data['idVersion'])
        
        process_id = version[0]['PROCESS_ID']  
        version_id = version[0]['VERSION_ID']  

        # Obtiene todos los campos del proceso
        process = ProcessRepository().find_process_by_id(process_id)

        #print({ 'process': process.name })  

        # Obtiene Campos y datos organizacionales
        fields = ['$BUKRS', '$WERKS']
        org_levels = OrganizationalLevelRepository().get_active_by_process_fields(process_id, fields)
        org_fields = OrganizationalFieldRepository().get_active_fields_by_process(process_id)
        
        # Riesgos y actividades
        rule_id = process[0]['RULE_ID']    

        # Obtiene todos los riesgos activos por regla
        risks = RiskRepository().get_active_by_rule(rule_id)

        # Pre-carga de actividades por riesgo
        risk_activities_transactions = {}
        for risk in risks:
            risk_activities_transactions[risk['RISK_ID']] = RiskActivityTransactionRepository().get_active_group_activity_by_risk(risk['RISK_ID'])

        # Configuración del sistema
        transaction_field = config.TRANSACTION_FIELD
        transaction_object = config.TRANSACTION_OBJECT 

        sap_system_id = config.SYSTEMS["SAP"]
        fiori_system_id = config.SYSTEMS["FIORI"]
        
        # Objetos y campos SAP
        sap_process_obj = SapProcessObjectRepository().get_active_by_process_name(process_id, transaction_object)
        sap_process_field = SapProcessFieldRepository().get_active_by_process_name(process_id, transaction_field)
        
        # Transacciones de la regla
        systems = config.SYSTEMS["SAP"]
        rule_transactions = TransactionRepository().get_active_by_rule_system_level(rule_id, systems)

        # Preparación de datos de usuarios
        extra_user_transactions = {}
        extra_user_roles = {}
        extra_user_auths = {}

        # Version.completo = 1
        if version[0]['COMPLETE'] == 1:
            users = UserTransactionRepository().get_active_group_by_process(process_id)
        else:
            
            # Usuarios asociados a la version
            version_users = VersionUserRepository().get_active_by_version(version_id)

            if len(version_users) > 0:

              user_filters = []
             
              for version_user in version_users:
                  user_id = version_user['USER_ID']
                  user_filters.append(user_id)
                  
                  # Transacciones extras
                  version_user_transactions = VersionUserTransactionRepository().get_active_by_version_user(version_user['VERSION_USER_ID'])
                  if len(version_user_transactions) > 0:
                    for version_user_transaction in version_user_transactions:
                        extra_user_transactions.setdefault(user_id, []).append(version_user_transaction['TRANSACTION_ID'])
                  
                  # Roles extras
                  version_user_roles = VersionUserRoleRepository().get_active_by_version_user(version_user['VERSION_USER_ID'])
                  if len(version_user_roles) > 0:
                    for version_user_role in version_user_roles:
                        role_id = version_user_role['SAP_ROLE_ID']
                        extra_user_roles.setdefault(user_id, []).append(role_id)
                                        
                    if sap_process_obj and sap_process_field:
                      # Get authorized transactions for the role
                      role_transactions = SapRoleObjectAuthorizationRepository().get_active_by_process_role_object_id_field_id(
                          process_id,
                          role_id,
                          sap_process_obj['SAP_PROC_OBJ_ID'],
                          sap_process_field['SAP_PROC_FIELD_ID']
                      )
                      
                      for role_transaction in role_transactions:
                          
                          transaction_code = role_transaction['FROM_VALUE']
                          
                          # Case 1: Wildcard transaction (*) Todos los sistemas
                          if transaction_code == comodin:
                              
                              for rule_transaction in rule_transactions:
                                  # Get transaction by rule id
                                  transaction = TransactionRepository().find(rule_transaction['TRANSACTION_ID'])
                                  if transaction['TRANSACTION_ID'] not in extra_user_transactions.get(user_id, []):
                                      extra_user_transactions.setdefault(user_id, []).append(transaction['TRANSACTION_ID'])
                          
                          # Case 2: Pattern transaction (like FI*)
                          elif comodin in transaction_code:
                              matching_transactions = [
                                  item for item in rule_transactions 
                                  if fnmatch.fnmatch(item.code, transaction_code)
                              ]
                              for match in matching_transactions:
                                  transaction = TransactionRepository().find(match.id)
                                  if transaction.id not in extra_user_transactions.get(user_id, []):
                                      extra_user_transactions.setdefault(user_id, []).append(transaction['TRANSACTION_ID'])
                          
                          # Case 3: Exact transaction
                          else:
                              exact_matches = [
                                  item for item in rule_transactions 
                                  if item.code == transaction_code
                              ]
                              if exact_matches:
                                  transaction = TransactionRepository().find(exact_matches[0].id)
                                  if transaction.id not in extra_user_transactions.get(user_id, []):
                                      extra_user_transactions.setdefault(user_id, []).append(transaction['TRANSACTION_ID'])
                  
                                   
                  # Autorizaciones extras
                  user_auths = VersionUserObjectRepository().get_active_by_version_user(version_user['VERSION_USER_ID'])

                  for user_auth in user_auths:
                      extra_user_auths.setdefault(user_id, []).append({
                          'object_id': user_auth['SAP_PROC_OBJ_ID'],
                          'field_id': user_auth['SAP_PROC_FLD_ID'],
                          'from': user_auth['FROM_VALUE'],
                          'to': user_auth['TO_VALUE']
                      })
              
              # Obtener usuario transacciones
              users = UserTransactionRepository().get_active_group_by_process_user(process_id, user_filters)        

        for user in users:
          start_time = time.time()
          batch_counter += 1
          user_counter += 1

          #if user_counter > 400:
            #continue

          user_id = user['USER_ID']  #Se obtiene el id_usuario del usuario_transaction
          #user_code = user.user_code # Se obtiene el idUsuario asociado al usuario_transaction
                    
          # Obtener transacciones del usuario con el id: user_id
          user_transactions = UserTransactionRepository().get_active_by_process_user(process_id, user_id)

          user_transaction_ids = [t['TRANSACTION_ID'] for t in user_transactions]

          # Agregar transacciones extras si existen (Caso 2)
          if user_id in extra_user_transactions:
              user_transaction_ids.extend(extra_user_transactions[user_id])
            
          # Registrar progreso
          # log_text = f"Usuario: {user_counter} - {user.user.username}"
          # with log_file.open('a') as f:
          #     f.write(log_text + "\n")

          risk_counter = 0
          for risk in risks:
              risk_counter += 1
              risk_id = risk['RISK_ID']
              #risk_name = risk.code
              
              # Filtrar por riesgo específico (opcional)
              #if risk_name != 'RTR_RA05':
              #   continue
                  
              total_activities = len(risk_activities_transactions.get(risk_id, []))
              activity_counter = 0
              risk_activity_transactions = []
              
              for risk_activity in risk_activities_transactions.get(risk_id, []):
                activity_id = risk_activity['ACTIVITY_ID']
                records = RiskActivityTransactionRepository().get_active_by_risk_activity_in_transactions(
                    risk_id, activity_id, user_transaction_ids
                )
                risk_activity_transactions.extend(records)
                
                if records:
                    activity_counter += 1

              if total_activities == activity_counter:
                activities = defaultdict(lambda: {"TRANSACTIONS": [], "CONDITION": False})
                fiori_activities = defaultdict(lambda: {"TRANSACTIONS": {}})
                risk_data = []
                
                for rat in risk_activity_transactions:
                    risk_id = rat['RISK_ID']
                    activity_id = rat['ACTIVITY_ID']
                    
                    # Inicializar entrada de actividad si no existe
                    if activity_id not in activities:
                        activities[activity_id] = {"TRANSACTIONS": [], "CONDITION": False}
                    
                    transaction_id = rat['TRANSACTION_ID']
                    activities[activity_id]["TRANSACTIONS"].append(transaction_id)
                    
                    # Manejar transacciones Fiori
                    if rat['SYSTEM_ID'] == fiori_system_id:
                        fiori_activities[activity_id]["TRANSACTIONS"][transaction_id] = transaction_id
                        
                    risk_data.append({
                        "ID": rat['RISK_ACT_TXN_ID'],
                        "RISK_ID": risk_id,
                        "ACTIVITY_ID": activity_id,
                        "TRANSACTION_ID": transaction_id
                    })
                
                    # Buscar autorizaciones
                    auth_data = find_object_authorization_by_profile(
                        org_levels,
                        process_id,
                        rule_id,
                        user_id,
                        activities,
                        fiori_activities,
                        extra_user_roles.get(user_id, []),
                        extra_user_auths.get(user_id, []),
                        org_fields)
                    
                    if auth_data["CONDITION"]:
                        for activity_id, activity_info in auth_data["ACTIVITY"].items():
                            for transaction_id in activity_info["TRANSACTION"]:
                                # 1. Filtrar transacciones de riesgo (equivalente a array_filter)
                                matching_transactions = [
                                    t for t in risk_data 
                                    if t["ACTIVITY_ID"] == activity_id 
                                    and t["TRANSACTION_ID"] == transaction_id
                                ]

                                if matching_transactions:
                                    # 2. Obtener transacción (equivalente a find() en Doctrine)
                                    transaction = TransactionRepository().get_transaction_by_id(transaction_id)
                                    if not transaction:  # Equivalente a find() null
                                        continue
                                        
                                    transaction = transaction[0]  # Primer elemento si es lista
                                    
                                    # 3. Verificar sistema primero (como en PHP)
                                    if transaction['SYSTEM_ID'] == sap_system_id:
                                        # Procesar perfiles SAP (equivalente a $DataPerfiles)
                                        profiles = activity_info.get("TRANSACTIONPROFILES", {}).get(transaction_id, [])
                                        for profile in profiles:
                                            conflict_data = {
                                                "IdVersion": version_id,
                                                "IdUsuario": user_id,
                                                "IdSapPerfil": profile.get("IdSapPerfil"),
                                                "IdSapAutorizacion": profile.get("IdSapAutorizacion"),
                                                "IdSapRol": profile.get("IdSapRol"),
                                                "IdRiesgoActividadTransaccion": matching_transactions[0]["ID"],
                                                "IdRiesgo": matching_transactions[0]["RISK_ID"],
                                                "IdActividad": matching_transactions[0]["ACTIVITY_ID"],
                                                "IdTransaccion": transaction_id,
                                                "IdSapObjetoProceso": profile.get("IdObjeto"),
                                                "IdSapCampoProceso": profile.get("IdCampo"),
                                                "Desde": profile.get("Desde", ""),
                                                "Hasta": profile.get("Hasta", ""),
                                                "IdAppUserCreacion": app_user['APP_USER_ID'],
                                                "IdAppUserActualizacion": app_user['APP_USER_ID'],
                                                "FechaCreacion": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                "FechaActualizacion": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                "Estado": 1
                                            }
                                            batch_conflicts.append(conflict_data)
                                            
                                    elif transaction['SYSTEM_ID'] == fiori_system_id:
                                        # Procesar roles Fiori (equivalente a $DataRoles)
                                        role_data = UserTransactionRoleRepository().get_active_by_process_user_transaction(
                                            process_id, user_id, transaction_id
                                        )
                                        
                                        for role in (role_data or []):
                                            conflict_data = {
                                                "IdVersion": version_id,
                                                "IdUsuario": user_id,
                                                "IdSapPerfil": None,
                                                "IdSapAutorizacion": None,
                                                "IdSapRol": role.get('sap_role_id'),
                                                "IdRiesgoActividadTransaccion": matching_transactions[0]["ID"],
                                                "IdRiesgo": matching_transactions[0]["RISK_ID"],
                                                "IdActividad": matching_transactions[0]["ACTIVITY_ID"],
                                                "IdTransaccion": transaction_id,
                                                "IdSapObjetoProceso": None,
                                                "IdSapCampoProceso": None,
                                                "Desde": "",
                                                "Hasta": "",
                                                "IdAppUserCreacion": app_user['APP_USER_ID'],
                                                "IdAppUserActualizacion": app_user['APP_USER_ID'],
                                                "FechaCreacion": datetime.now().strftime('%Y-%m-%d %H:%M<:%S'),
                                                "FechaActualizacion": datetime.now().strftime('%Y-%m-%d %H:%M<:%S'),
                                                "Estado": 1
                                            }
                                            batch_conflicts.append(conflict_data)
                                    
                                    # Insertar por lotes (equivalente a flush() cada 100)
                                    if len(batch_conflicts) >= 100:
                                        db_session.bulk_insert_mappings(Conflicto, batch_conflicts)
                                        conflict_count += len(batch_conflicts)
                                        batch_conflicts.clear()

        if batch_conflicts:
            db_session.bulk_insert_mappings(Conflicto, batch_conflicts)
            conflict_count += len(batch_conflicts)
            batch_conflicts.clear()

        #db_session.commit()

        time_end = time.perf_counter()
        total_time = round(time_end - time_start,2)

        conflicts = db_session.query(Conflicto.IdUsuario, RiesgoActividadTransaccion.IdRiesgo)\
                                        .join(RiesgoActividadTransaccion, RiesgoActividadTransaccion.Id == Conflicto.IdRiesgoActividadTransaccion)\
                                        .filter(Conflicto.IdVersion == version_id)\
                                        .group_by(Conflicto.IdUsuario, RiesgoActividadTransaccion.IdRiesgo)\
                                        .order_by(Conflicto.Id).all()
        conflict_count = len(conflicts)
        
        ProcessRepository().update_process_stats(
            process_id, 
            total_time, 
            conflict_count
        )

        VersionRepository().update_version_stats(
            version_id,
            total_time,
            conflict_count
        )
        
        return jsonify({
            'status': 'Success',
            'message': 'Se completó el análisis de conflictos',
            'data': {
                'conflict_count': conflict_count,
                'user_count': user_counter,
                'time': total_time
            }
        }), 200
      else:
        SaveStorage(session['tokendata'], GetIpAddress(), 200, "list_documents_by_activity", "document", NO_FOUND_TOKEN)
    else:
      abort(400)
    
    current_app.logger.info(f'SOD: Análisis de conflictos - Fin')
    # return jsonify({'status': 'Success', 'message': 'Se completó el análisis de conflictos', 'data': data }), 200
  except Exception as e:
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    print(f"Error at {fname}:{exc_tb.tb_lineno}: {e}")
    abort(HTTP_ERROR_DICT[type(e).__name__])


def find_object_authorization_by_profile(
    org_levels,
    process_id,
    rule_id,
    user_id,
    activities,
    fiori_activities,
    extra_user_roles,
    extra_user_auths,
    org_fields
):
    try:
        current_time = int(time.time())
        max_date_sap = config.MAX_DATE_SAP
        max_date_py = config.MAX_DATE_PHP
        result_profiles = {}
        profile_auth_object_field = {} ##Esta como varible global 

        # Get all user profiles for the process
        # SELECT * FROM `sapusuarioperfil`WHERE `IdProceso`=112 AND `IdUsuario`=17263 GROUP BY `IdSapPerfil`
        user_profiles = SapUserProfileRepository().get_active_group_user_profile_by_process_user(process_id, user_id)
        
        #backup_activities = activities
        profile_ids = [profile['PROFILE_ID'] for profile in user_profiles]

        #activities = backup_activities
        result_profiles = {"CONDITION": False, "ACTIVITY": {}}

        conditional_logic = {}

        for activity_id, activity_data in activities.items():
            transaction_ids = [int(t_id) for t_id in activity_data["TRANSACTIONS"]]
            
            result_profiles["ACTIVITY"][activity_id] = {
                "CONDITION": False,
                "TRANSACTION": [],
                "TRANSACTIONPROFILES": {},
                "TRANSACTIONOBJECTS": defaultdict( lambda: defaultdict(dict)),
                "ROLES": [],
                "BURKS": [],
                "WERKS": []
            }
            
            object_fields = {}

            # Process Fiori transactions
            for t_id in activity_data["TRANSACTIONS"]:
                if t_id in fiori_activities.get(activity_id, {}).get("TRANSACTIONS", {}):
                    obj_code = '1'
                    field_code = '1'
                    obj_id = 1
                    field_id = 1
                    from_val = '*'
                    to_val = '*'
                    
                    if t_id not in object_fields:
                        object_fields[t_id] = {
                            "OBJECTS": {},
                            "CONDITION": True,
                            "PROFILE": []
                        }
                    
                    if obj_code not in object_fields[t_id]["OBJECTS"]:
                        object_fields[t_id]["OBJECTS"][obj_code] = {
                            "FIELDS": {},
                            "CONDITION": True,
                            "OBJECT_ID": obj_id
                        }
                    
                    if field_code not in object_fields[t_id]["OBJECTS"][obj_code]["FIELDS"]:
                        object_fields[t_id]["OBJECTS"][obj_code]["FIELDS"][field_code] = {
                            "VALUES": [],
                            "CONDITION": True,
                            "FIELD_ID": field_id,
                            "AUTHORIZATION": []
                        }
                    
                    object_fields[t_id]["OBJECTS"][obj_code]["FIELDS"][field_code]["VALUES"].append({
                        "FROM_VALUE": from_val,
                        "TO_VALUE": to_val,
                        "CONDITION": True
                    })
            
            sap_object_fields = SapObjectFieldRepository().get_active_by_rule_activity_transaction( rule_id, activity_id, transaction_ids)

            for obj_field in sap_object_fields or []:
                t_id = obj_field["TRANSACTION_ID"]
                obj_id = obj_field["OBJECT_ID"]
                obj_code = obj_field["OBJECT_NAME"]
                field_id = obj_field["FIELD_ID"]
                field_code = obj_field["FIELD_NAME"]
                from_val = obj_field["FROM_VALUE"]
                to_val = obj_field["TO_VALUE"]
                conditional = obj_field["IS_CONDITIONAL"] or "OR"

                #Se agrega el id de la actividad
                if activity_id not in conditional_logic:
                    conditional_logic[activity_id] = {}
                
                if t_id not in conditional_logic[activity_id]:
                    conditional_logic[activity_id][t_id] = {}

                if obj_code not in conditional_logic[activity_id][t_id]:
                    conditional_logic[activity_id][t_id][obj_code] = {}

                if field_code not in conditional_logic[activity_id][t_id][obj_code]:
                    conditional_logic[activity_id][t_id][obj_code][field_code] = {}
                
                conditional_logic[activity_id][t_id][obj_code][field_code][conditional] = \
                    conditional_logic[activity_id][t_id][obj_code][field_code].get(conditional, 0) + 1

                if t_id not in object_fields:
                    object_fields[t_id] = {
                        "OBJECTS": {},
                        "CONDITION": False,
                        "PROFILE": []
                    }
                
                if obj_code not in object_fields[t_id]["OBJECTS"]:
                    object_fields[t_id]["OBJECTS"][obj_code] = {
                        "FIELDS": {},
                        "CONDITION": False,
                        "OBJECT_ID": obj_id
                    }
                
                if field_code not in object_fields[t_id]["OBJECTS"][obj_code]["FIELDS"]:
                    object_fields[t_id]["OBJECTS"][obj_code]["FIELDS"][field_code] = {
                        "VALUES": [],
                        "CONDITION": False,
                        "FIELD_ID": field_id
                    }
                
                object_fields[t_id]["OBJECTS"][obj_code]["FIELDS"][field_code]["VALUES"].append({
                    "FROM_VALUE": from_val,
                    "TO_VALUE": to_val,
                    "CONDITION": False
                })
            
            if object_fields:
                for t_id, objects in object_fields.items():
                    for obj_code, fields in objects["OBJECTS"].items():
                        
                        # 1: 25689
                        obj_id = fields["OBJECT_ID"]
                        
                        for field_code, values in fields["FIELDS"].items():
                            # 1: 8752 
                            field_id = values["FIELD_ID"]
                            is_org_field = False
                            
                            # Check if this is an organizational field
                            # 1: org_field = empty
                            org_field = next((f for f in org_fields if f["FIELD"] == field_code), None)
                            process_obj_id = None
                            process_field_id = None
                            
                            if org_field:
                                is_org_field = True
                                sap_process_obj = SapProcessObjectRepository().get_active_by_process_name(process_id, obj_code)

                                if sap_process_obj:
                                    process_obj_id = sap_process_obj[0]['SAP_PROC_OBJ_ID']
                                
                                sap_process_field = SapProcessFieldRepository().get_active_by_process_name( process_id, field_code)

                                if sap_process_field:
                                    process_field_id = sap_process_field[0]['SAP_PROC_FIELD_ID']
                            
                            field_condition = False

                            profile_auths = SapUserProfileRepository().get_active_group_profile_auth_role_by_process_user(
                                process_id, user_id, obj_code
                            )
                            
                            # Handle extra roles
                            new_extra_roles = []
                            
                            if extra_user_roles:
                                for extra_role in extra_user_roles:
                                    if not any(auth["ROLE_ID"] == extra_role for auth in profile_auths):
                                        for auth in profile_auths:
                                            new_extra_roles.append({
                                                'PROFILE_ID': auth['PROFILE_ID'],
                                                'AUTHORIZATION_ID': auth['AUTHORIZATION_ID'],
                                                'ROLE_ID': extra_role,
                                                'EXTRA': True
                                            })
                            
                            if new_extra_roles:
                                profile_auths.extend(new_extra_roles)

                            # Process authorizations
                            for profile_auth in profile_auths:
                                profile_id = profile_auth['PROFILE_ID']
                                auth_id = profile_auth['AUTHORIZATION_ID']
                                is_extra = profile_auth.get('EXTRA', False)
                                role_valid = True
                                
                                if profile_auth['ROLE_ID'] and not is_extra:
                                    role_data = SapUserRolRepository().get_active_group_user_role_by_process_user_role(
                                        process_id, user_id, profile_auth['ROLE_ID']
                                    )
                                    
                                    if role_data:
                                        for role in role_data:
                                            start_date = int(role['START_DATE'].timestamp())
                                            #end_date = int(role['END_DATE'].timestamp())
                                            end_date = int(datetime(2038, 1, 1, 0, 0).timestamp())
                                            if end_date == max_date_sap:
                                                end_date = int(max_date_py)
                                            
                                            if not (start_date <= current_time <= end_date):
                                                role_valid = False
                                            else:
                                                role_valid = True
                                                break
                                
                                if role_valid:
                                    role_id = profile_auth['ROLE_ID'] or config.DEFAULT_ROL_ID
                                    
                                    if not is_extra:
                                        field_values = SapObjectAuthorizationRepository().get_active_by_process_auth_object_field(
                                            process_id, auth_id, obj_code, field_code
                                        ) or []
                                        
                                        if is_org_field:
                                            # Add organizational level values
                                            org_values = OrganizationalLevelRepository().get_active_by_process_role_field(
                                                process_id, role_id, field_code
                                            )
                                            field_values.extend([{
                                                'OBJECT_ID': process_obj_id,
                                                'FIELD_ID': process_field_id,
                                                'FROM_VALUE': val['FROM_VALUE'],
                                                'TO_VALUE': val['TO_VALUE']
                                            } for val in org_values])
                                            
                                            # Add role object authorization values
                                            role_values = SapRoleObjectAuthorizationRepository().get_active_by_process_role_object_field(
                                                process_id, role_id, obj_code, field_code
                                            )
                                            field_values.extend([{
                                                'OBJECT_ID': val['ID_OBJETO'],
                                                'FIELD_ID': val['ID_CAMPO'],
                                                'FROM_VALUE': val['DESDE'],
                                                'TO_VALUE': val['HASTA']
                                            } for val in role_values])
                                    else:
                                        field_values = SapRoleObjectAuthorizationRepository().get_active_by_process_role_object_field(
                                            process_id, role_id, obj_code, field_code
                                        )
                                        if is_org_field:
                                            org_values = OrganizationalLevelRepository().get_active_by_process_role_field(
                                                process_id, role_id, field_code
                                            )
                                            field_values.extend([{
                                                'OBJECT_ID': obj_id,
                                                'FIELD_ID': field_id,
                                                'FROM_VALUE': val['FROM_VALUE'],
                                                'TO_VALUE': val['TO_VALUE']
                                            } for val in org_values])
                                    
                                    # Store field values
                                    for val in field_values or []:
                                        if profile_id not in profile_auth_object_field:
                                            profile_auth_object_field[profile_id] = {}
                                        if auth_id not in profile_auth_object_field[profile_id]:
                                            profile_auth_object_field[profile_id][auth_id] = {}
                                        if obj_code not in profile_auth_object_field[profile_id][auth_id]:
                                            profile_auth_object_field[profile_id][auth_id][obj_code] = {}
                                        if field_code not in profile_auth_object_field[profile_id][auth_id][obj_code]:
                                            profile_auth_object_field[profile_id][auth_id][obj_code][field_code] = []
                                        #print(val)
                                        profile_auth_object_field[profile_id][auth_id][obj_code][field_code].append({
                                            "OBJECT_ID": val["OBJECT_ID"],
                                            "FIELD_ID": val["FIELD_ID"],
                                            "FROM_VALUE": val["FROM_VALUE"],
                                            "TO_VALUE": val["TO_VALUE"],
                                            'EXTRA': is_extra
                                        })
                                    
                                    # Add extra authorizations
                                    if extra_user_auths:
                                        for extra_auth in extra_user_auths:
                                            if profile_id not in profile_auth_object_field:
                                                profile_auth_object_field[profile_id] = {}
                                            if auth_id not in profile_auth_object_field[profile_id]:
                                                profile_auth_object_field[profile_id][auth_id] = {}
                                            if obj_code not in profile_auth_object_field[profile_id][auth_id]:
                                                profile_auth_object_field[profile_id][auth_id][obj_code] = {}
                                            if field_code not in profile_auth_object_field[profile_id][auth_id][obj_code]:
                                                profile_auth_object_field[profile_id][auth_id][obj_code][field_code] = []
                                            
                                            profile_auth_object_field[profile_id][auth_id][obj_code][field_code].append({
                                                "OBJECT_ID": extra_auth['OBJECT_ID'],
                                                "FIELD_ID": extra_auth['FIELD_ID'],
                                                "FROM_VALUE": extra_auth["FROM_VALUE"],
                                                "TO_VALUE": extra_auth["TO_VALUE"],
                                                'EXTRA': True
                                            })
                                    
                                
                                    # Process authorization checks
                                    if profile_id in profile_auth_object_field and \
                                        auth_id in profile_auth_object_field[profile_id] and \
                                        obj_code in profile_auth_object_field[profile_id][auth_id] and \
                                        field_code in profile_auth_object_field[profile_id][auth_id][obj_code]:
                                        
                                        for field_val in profile_auth_object_field[profile_id][auth_id][obj_code][field_code]:
                                            object_id = field_val["OBJECT_ID"]
                                            field_id = field_val["FIELD_ID"]
                                            profile_from = field_val["FROM_VALUE"].strip()
                                            profile_to = field_val["TO_VALUE"].strip()
                                            
                                            for value in values["VALUES"]:
                                                val_from = value["FROM_VALUE"].strip()
                                                val_to = value["TO_VALUE"].strip()
                                                
                                                # Check authorization match
                                                results = Helper.bol_campo_find_object_authorization(
                                                    field_condition,
                                                    val_from,
                                                    profile_from,
                                                    val_to,
                                                    profile_to,
                                                    comodin,
                                                    result_profiles,
                                                    activity_id,
                                                    t_id,
                                                    profile_id,
                                                    auth_id,
                                                    role_id,
                                                    object_id,
                                                    obj_code,
                                                    field_id,
                                                    field_code
                                                )

                                                field_condition = results["BolCampo"]
                                                result_profiles = results["aResultPerfiles"]

                                                if field_condition:
                                                    
                                                    object_fields[t_id]["OBJECTS"][obj_code]["FIELDS"][field_code]["CONDITION"] = True
                                                    
                                                    if "AUTHORIZATION" not in object_fields[t_id]["OBJECTS"][obj_code]["FIELDS"][field_code]:
                                                        object_fields[t_id]["OBJECTS"][obj_code]["FIELDS"][field_code]["AUTHORIZATION"] = []

                                                    object_fields[t_id]["OBJECTS"][obj_code]["FIELDS"][field_code]["AUTHORIZATION"].append({
                                                        'ID': auth_id,
                                                        'ROLE_ID': role_id
                                                    })
                                                    field_condition = False
                                    
                                    # Clean up extra values
                                    if is_extra:
                                        if profile_id in profile_auth_object_field and \
                                            auth_id in profile_auth_object_field[profile_id] and \
                                            obj_code in profile_auth_object_field[profile_id][auth_id] and \
                                            field_code in profile_auth_object_field[profile_id][auth_id][obj_code]:
                                            del profile_auth_object_field[profile_id][auth_id][obj_code][field_code]
                                    else:
                                        # Remove extra values
                                        if profile_id in profile_auth_object_field and \
                                            auth_id in profile_auth_object_field[profile_id] and \
                                            obj_code in profile_auth_object_field[profile_id][auth_id] and \
                                            field_code in profile_auth_object_field[profile_id][auth_id][obj_code]:
                                            profile_auth_object_field[profile_id][auth_id][obj_code][field_code] = [
                                                val for val in profile_auth_object_field[profile_id][auth_id][obj_code][field_code] 
                                                if not val.get('EXTRA', False)
                                            ]
                                    
                                    # Track roles
                                    if role_id not in result_profiles["ACTIVITY"][activity_id]["ROLES"]:
                                        result_profiles["ACTIVITY"][activity_id]["ROLES"].append(role_id)


                        # Check field conditions
                        true_fields = 0
                        total_fields = len(fields["FIELDS"])
                        
                        # Collect valid authorizations
                        auths = {}
                        valid_auths = []
                        invalid_auths = []
                        
                        for field_code, field_data in fields["FIELDS"].items():
                            if field_data["CONDITION"]:
                                for auth in field_data["AUTHORIZATION"]:
                                    auths[auth['ID']] = auth['ID']
                        
                        # Validate authorizations across all fields
                        for auth_id in auths:
                            valid_count = 0
                            for field_code, field_data in fields["FIELDS"].items():
                                if field_data["CONDITION"]:
                                    if any(auth['ID'] == auth_id for auth in field_data["AUTHORIZATION"]):
                                        valid_count += 1
                            
                            if valid_count == total_fields:
                                valid_auths.append(auth_id)
                            else:
                                invalid_auths.append(auth_id)                

                        # Handle invalid authorizations
                        if not valid_auths:
                            for field_code in fields["FIELDS"]:
                                object_fields[t_id]["OBJECTS"][obj_code]["FIELDS"][field_code]["CONDITION"] = False
                        
                        for invalid_auth in invalid_auths:
                            if t_id==2518 and invalid_auth == 405277 and obj_code == 'I_INGRP':
                                pass

                        # Remove invalid authorizations from results (PHP-like exact version)
                        for invalid_auth in invalid_auths:
                            if t_id in result_profiles["ACTIVITY"][activity_id]["TRANSACTIONPROFILES"]:
                                # 1. Encontrar los perfiles que SÍ coinciden (como array_filter en PHP)
                                matching_profiles = [
                                    (idx, p) for idx, p in enumerate(
                                        result_profiles["ACTIVITY"][activity_id]["TRANSACTIONPROFILES"][t_id]
                                    )
                                    if (p["IdSapAutorizacion"] == invalid_auth and
                                        p["Objeto"] == obj_code)
                                ]
                                
                                # 2. Eliminar los que coinciden (como unset en PHP)
                                for idx, _ in sorted(matching_profiles, key=lambda x: x[0], reverse=True):
                                    del result_profiles["ACTIVITY"][activity_id]["TRANSACTIONPROFILES"][t_id][idx]
                        
                        # # Remove invalid authorizations from results 
                        # for invalid_auth in invalid_auths:
                        #     if t_id in result_profiles["ACTIVITY"][activity_id]["TRANSACTIONPROFILES"]:
                        #         result_profiles["ACTIVITY"][activity_id]["TRANSACTIONPROFILES"][t_id] = [
                        #             p for p in result_profiles["ACTIVITY"][activity_id]["TRANSACTIONPROFILES"][t_id]
                        #             if not (
                        #                 p["IdTransaccion"] == t_id and
                        #                 p["IdSapAutorizacion"] == invalid_auth and
                        #                 p["Objeto"] == obj_code
                        #             )
                        #         ]

                        try:
                            aux = result_profiles["ACTIVITY"][activity_id]["TRANSACTIONPROFILES"][t_id]
                            if len(aux) > 1:
                                pass
                        except:
                            pass
                        
                        # Count valid fields
                        true_fields = 0
                        for field, value in fields["FIELDS"].items():
                            condition = object_fields[t_id]["OBJECTS"][obj_code]["FIELDS"][field_code] = True
                            if condition is True:
                                true_fields += 1                        

                        
                        # Update object condition
                        if total_fields == true_fields:
                            object_fields[t_id]["OBJECTS"][obj_code]["CONDITION"] = True
                        
                                
                        result_profiles["ACTIVITY"][activity_id]["TRANSACTIONOBJECTS"][t_id][obj_code][field_code] = object_fields[t_id]["OBJECTS"][obj_code]["CONDITION"]
                    

                # Check object conditions
                try:
                    total_objects = len(objects["OBJECTS"])                
                    true_objects = 0
                    for obj, value in objects["OBJECTS"].items():
                        condition = object_fields[t_id]["OBJECTS"][obj]["CONDITION"]
                        if condition is True:
                            true_objects += 1
                except:
                    true_objects = 0            
                    total_objects = 0
                
                if total_objects == true_objects and total_objects != 0:
                    object_fields[t_id]["CONDITION"] = True
                    result_profiles["ACTIVITY"][activity_id]["TRANSACTION"].append(t_id)
            
            total_transactions = [
                val for val in object_fields.values()
                if val.get("CONDITION")
            ]

            if len(total_transactions) > 0:
                activities[activity_id]["CONDITION"] = True
                result_profiles["ACTIVITY"][activity_id]["CONDITION"] = True


        # Final condition check
        total_activities = len(activities)
        valid_activities = sum(1 for a in activities.values() if a["CONDITION"])

        profile_auth_object_field = profile_auth_object_field

        if total_activities == valid_activities:
            result_profiles["CONDITION"] = True

        # Additional organizational checks
        if result_profiles["CONDITION"] and False:
            result_profiles = Helper.add_activity_role_field(
                result_profiles, sap_org_levels, '$BUKRS', "Bukrs"
            )
            if not Helper.check_activity_role_field(result_profiles, "Bukrs", comodin):
                result_profiles = Helper.add_activity_role_field(
                    result_profiles, sap_org_levels, '$WERKS', "Werks"
                )
                if not Helper.check_activity_role_field(result_profiles, "Werks", comodin):
                    result_profiles["CONDITION"] = False

        return result_profiles
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(f"Error at {fname}:{exc_tb.tb_lineno}: {e}")
        LogRepository().insert_log(str(e))
        return {"CONDITION": False, "ERROR": str(e)}