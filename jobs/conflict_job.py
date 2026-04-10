import os, sys, json, requests, io, time
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

import numpy as np

from fnmatch import fnmatch
from collections import OrderedDict
from collections import defaultdict
from models.sapcampoproceso import SapCampoProceso
from models.sapobjetoproceso import SapObjetoProceso
from models.saprolobjetoautorizacion import SapRolObjetoAutorizacion
from models.sapusuariorol import SapUsuarioRol
from utils.helper import Helper
from sqlalchemy import and_, desc, insert, or_, select, func
from sqlalchemy.orm import aliased
from datetime import datetime, timedelta, timezone
from models import usuariotransaccionrol
from models import sapobjeto
from models import sapcampo
from models.actividad import Actividad
from models.appuser import AppUser
from models.conflicto import Conflicto
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
from models.transaccion import Transaccion as transaccion
from models.usuario import Usuario
from models.usuariotransaccion import UsuarioTransaccion
from models.version import Version
from models.versionusuario import VersionUsuario
from models.versionusuarioobjeto import VersionUsuarioObjeto
from models.versionusuariorol import VersionUsuarioRol
from models.versionusuariotransaccion import VersionUsuarioTransaccion
from models.transaccion import Transaccion as Transaccion
from utils import storage
from config import config
from flask import json
from multiprocessing import Pool, Lock
from db.database import SessionLocal

from utils.helper2 import Helper2

# Este Lock es global para EL CONTENEDOR. 
# Si otro análisis corre en el mismo contenedor, respetará este semáforo.
lock_pesados = Lock()
comodin = '*'
TZ_LIMA = timezone(timedelta(hours=-5), name="America/Lima")

def worker_pesado(usuario_id, id_version, id_job, id_user, all_users, idx_shard, total_shards, limit_date):
    """Maneja la fila de usuarios pesados."""
    print(f"--- Usuario Pesado {usuario_id} en espera de turno ---")
    with lock_pesados:
        # Solo un usuario pesado entra aquí a la vez
        print(f"--- Iniciando procesamiento de Pesado: {usuario_id} ---")
        return process_execute([usuario_id], id_version, id_job, id_user, all_users, idx_shard, total_shards, limit_date)

def main():
    try:
        raw = os.getenv("INPUT_JSON")  # El Job recibe un JSON con toda la info, pero aquí nos enfocamos en lo esencial
        data = json.loads(raw)

        id_job = data["id_job"]
        id_version = data["id_version"]
        id_user = data["id_user"]
        only_user_ids = data.get("user_ids", []) 
        total_users = data["total_users"]   
        total_shards = data["total_shards"]
        idx_shard = data.get("idx_shard", 0)    
        type_execution = data["type"]
        limit_date = data.get("limit_date")

        if type_execution == "liviano":
            print(f"Ejecutando SHARD #{idx_shard} en modo LIVIANO: procesamiento paralelo sin bloqueo.")
            process_execute(only_user_ids, id_version, id_job, id_user, total_users, idx_shard, total_shards, limit_date)
        else:
            for user_id in only_user_ids:
                print(f"Ejecutando SHARD #{idx_shard} en modo PESADO para Usuario {user_id}: procesamiento secuencial con bloqueo.")
                worker_pesado(user_id, id_version, id_job, id_user, total_users, idx_shard, total_shards, limit_date)

        print(f"SHARD #{idx_shard} ha completado su ejecución.")
    except Exception as e:
        print(f"Error en el Job: {str(e)}")
        storage.update_job_with_errors(id_job, [str(e)])

def FindObjectAuthorizationByPerfil(
    SapNivelOrganizacionales,
    aActividades,
    aActividadesFiori,
    RolesExtras,
    AutorizacionesExtras,
    CamposOrganizacionales,
    cache,
    limit_date
    ):

    try:        
        now_ts = int(limit_date.timestamp())
        
        max_date_sap = config.MAX_DATE_SAP
        max_date_php = config.MAX_DATE_PHP

        aResultPerfiles = {}
        aPerfilAutorizacionesObjetoCampo = {} 

        DatoRoles_General = cache["DatoRoles_General"]
        AddCampoValores_General = cache["AddCampoValores_General"]
        RolCampoValores_General = cache["RolCampoValores_General"]
        SapObjetoProceso_General = cache["SapObjetoProceso_General"]
        SapCampoProceso_General = cache["SapCampoProceso_General"]
        CampoValores_Extra_General = cache["CampoValores_Extra_General"]
        SapObjetoCampos_General = cache["SapObjetoCampos_General"]
        Objetos_Lista_General = cache["Objetos_Lista_General"]
        PerfilesAutorizaciones_General = cache["PerfilesAutorizaciones_General"]
        CampoValores_General = cache["CampoValores_General"]
        Roles_Transaccion_General = cache["Roles_Transacciones"]

        aResultPerfiles = {"CONDITION": False, "Actividad": {}}

        
        idx_SapObjetoProceso_por_nombre = {}
        for row in SapObjetoProceso_General:
            idx_SapObjetoProceso_por_nombre.setdefault(row["nombre"], row)

        idx_SapCampoProceso_por_nombre = {}
        for row in SapCampoProceso_General:
            idx_SapCampoProceso_por_nombre.setdefault(row["nombre"], row)

        
        idx_SapObjetoCampos_por_actividad = {
            act: lista for act, lista in SapObjetoCampos_General.items()
        }

        
        DatoRoles_by_idrol = defaultdict(list)
        for row in DatoRoles_General:
            idrol = row["id_rol"] if isinstance(row, dict) else row.id_rol
            DatoRoles_by_idrol[idrol].append(row)

        
        max_date_sap_ts = int(datetime.strptime(max_date_sap, "%Y-%m-%d %H:%M:%S")
                            .replace(tzinfo=timezone.utc).timestamp())

        if isinstance(max_date_php, str):
            max_date_php_ts = int(datetime.fromisoformat(max_date_php).timestamp())
        else:
            max_date_php_ts = int(max_date_php)

        for IdActividad, aTransacciones in aActividades.items():        
            aResultPerfiles["Actividad"].setdefault(
                IdActividad,
                {"CONDITION": False, "Transaccion": [], "TransaccionPerfiles": {}, "Roles": {}, "Bukrs": {}, "Werks": {}},
            )

            aObjetosCampos = {}
            
            for id_transaccion in aTransacciones["TRANSACCIONES"]:                
                if (
                    IdActividad in aActividadesFiori
                    and "TRANSACCIONES" in aActividadesFiori[IdActividad]
                    and id_transaccion in aActividadesFiori[IdActividad]["TRANSACCIONES"]
                ):
                    codigo_objeto = "1"
                    codigo_campo = "1"
                    id_objeto = 1
                    id_campo = 1
                    desde = "*"
                    hasta = "*"

                    if id_transaccion not in aObjetosCampos:
                        aObjetosCampos[id_transaccion] = {"OBJETOS": {}, "CONDITION": True, "PERFIL": {}}

                    if codigo_objeto not in aObjetosCampos[id_transaccion]["OBJETOS"]:
                        aObjetosCampos[id_transaccion]["OBJETOS"][codigo_objeto] = {
                            "CAMPOS": {},
                            "CONDITION": True,
                            "ID_OBJETO": id_objeto,
                        }

                    if codigo_campo not in aObjetosCampos[id_transaccion]["OBJETOS"][codigo_objeto]["CAMPOS"]:
                        aObjetosCampos[id_transaccion]["OBJETOS"][codigo_objeto]["CAMPOS"][codigo_campo] = {
                            "VALORES": [],
                            "CONDITION": True,
                            "ID_CAMPO": id_campo,
                            "AUTORIZACION": [],
                        }

                    valores = {"DESDE": desde, "HASTA": hasta, "CONDITION": True}
                    aObjetosCampos[id_transaccion]["OBJETOS"][codigo_objeto]["CAMPOS"][codigo_campo]["VALORES"].append(
                        valores
                    )

            # GET INFORMATION OBJECT AUTHORIZATION OF MATRIZ SOD - TAB PERMISSIONS
            #SapObjetoCampos = SapObjetoCampos_General[IdActividad] if IdActividad in SapObjetoCampos_General else []
            SapObjetoCampos = idx_SapObjetoCampos_por_actividad.get(IdActividad, [])

            obj_lista = list(dict.fromkeys([x["nombre_objeto"] for x in SapObjetoCampos]))
            cam_lista = list(dict.fromkeys([x["nombre_campo"] for x in SapObjetoCampos]))
            
            Objetos_Lista = Objetos_Lista_General[IdActividad] if IdActividad in Objetos_Lista_General else []

            result_aux = [x for x in PerfilesAutorizaciones_General if "PerfilesAutorizaciones_General" in cache and x["nombre_objeto"] in Objetos_Lista] if "PerfilesAutorizaciones_General" in cache else []
            
            SapPerfilesAutorizaciones_activity = defaultdict(list) 
            aut_lista = list(dict.fromkeys([x["id_autorizacion"] for x in result_aux]))

            for row in result_aux:
                SapPerfilesAutorizaciones_activity[row["nombre_objeto"]].append(row)
            
            cvpa = cache.setdefault("CampoValoresPorAutorizacion", {})  # conserva estructura
            cvpa.clear()  # aseguramos que no arrastre actividad anterior

            if "CampoValores_General" in cache:
                campo_vals_all = cache["CampoValores_General"]          # NO sombrear
                campo_vals_filtered = [
                    x for x in campo_vals_all
                    if x["id_autorizacion"] in aut_lista
                    and x["objeto"] in obj_lista
                    and x["campo"] in cam_lista
                ]
            else:
                campo_vals_filtered = []

            for row in campo_vals_filtered:
                cvpa.setdefault(row["id_autorizacion"], {}) \
                    .setdefault(row["objeto"], {}) \
                    .setdefault(row["campo"], []) \
                    .append(row)  # mismo orden


            
            aCondicional = {}
            for SapObjetoCampo in SapObjetoCampos:
                id_transaccion = SapObjetoCampo["id_transaccion"]
                id_objeto = SapObjetoCampo["id_objeto"]
                codigo_objeto = SapObjetoCampo["nombre_objeto"]
                id_campo = SapObjetoCampo["id_campo"]
                codigo_campo = SapObjetoCampo["nombre_campo"]
                desde = SapObjetoCampo["desde"]
                hasta = SapObjetoCampo["hasta"]
                condicional = SapObjetoCampo.get("condicional", "")
                if condicional == "":
                    condicional = "OR"

                if id_transaccion not in aTransacciones['TRANSACCIONES']:
                    continue
            
                aCondicional.setdefault(IdActividad, {}).setdefault(id_transaccion, {}).setdefault(
                    codigo_objeto, {}
                ).setdefault(codigo_campo, {}).setdefault(condicional, 0)
                aCondicional[IdActividad][id_transaccion][codigo_objeto][codigo_campo][condicional] += 1

                if id_transaccion not in aObjetosCampos:
                    aObjetosCampos[id_transaccion] = {"OBJETOS": {}, "CONDITION": False, "PERFIL": {}}

                if codigo_objeto not in aObjetosCampos[id_transaccion]["OBJETOS"]:
                    aObjetosCampos[id_transaccion]["OBJETOS"][codigo_objeto] = {
                        "CAMPOS": {},
                        "CONDITION": False,
                        "ID_OBJETO": id_objeto,
                    }

                if codigo_campo not in aObjetosCampos[id_transaccion]["OBJETOS"][codigo_objeto]["CAMPOS"]:
                    aObjetosCampos[id_transaccion]["OBJETOS"][codigo_objeto]["CAMPOS"][codigo_campo] = {
                        "VALORES": [],
                        "CONDITION": False,
                        "ID_CAMPO": id_campo,
                    }

                valores = {"DESDE": desde, "HASTA": hasta, "CONDITION": False}
                aObjetosCampos[id_transaccion]["OBJETOS"][codigo_objeto]["CAMPOS"][codigo_campo]["VALORES"].append(
                    valores
                )

            # Ciclo: Transaccion -> Objeto -> Campo
            if len(aObjetosCampos) > 0:
                for Transaccion, Objetos in aObjetosCampos.items():
                    aPerfilAutorizacionesObjetoCampo = {}
                    RolesValidosParaTransaccion = Roles_Transaccion_General.get(Transaccion, set())
                    
                    for Objeto, Campos in Objetos["OBJETOS"].items():
                        ID_OBJETO = Campos["ID_OBJETO"]
                        for Campo, Valores in Campos["CAMPOS"].items():
                            ID_CAMPO = Valores["ID_CAMPO"]

                            # Detectar si el campo es organizacional
                            BolCampoOrganizacional = False                        
                            #oCampoOrganizacionales = [Obj for Obj in CamposOrganizacionales if Obj.Campo == Campo]
                            oCampoOrganizacionales = CamposOrganizacionales.get(Campo, [])
                            IdSapObjetoProcesoOFRisk = None
                            IdSapCampoProcesoOFRisk = None

                            if len(oCampoOrganizacionales) > 0:
                                BolCampoOrganizacional = True          

                                row_obj = idx_SapObjetoProceso_por_nombre.get(Objeto)
                                if row_obj:
                                    IdSapObjetoProcesoOFRisk = row_obj["id"]

                                row_campo = idx_SapCampoProceso_por_nombre.get(Campo)
                                if row_campo:
                                    IdSapCampoProcesoOFRisk = row_campo["id"]


                            BolCampo = False                                                
                            
                            for ObjetoSap, SapPerfilesAutorizaciones in SapPerfilesAutorizaciones_activity.items():
                                if ObjetoSap != Objeto:
                                    continue                            

                                # Añadir RolesExtras cuando no existan                                
                                if RolesExtras:
                                    existing_ids = {row.get("id_rol") for row in SapPerfilesAutorizaciones if "id_rol" in row}
                                    roles_extras_new = []
                                    for RolExtra in RolesExtras:
                                        if RolExtra not in existing_ids:
                                            for spa in SapPerfilesAutorizaciones:  # MISMO orden base
                                                roles_extras_new.append({
                                                    "id_perfil": spa["id_perfil"],
                                                    "id_autorizacion": spa["id_autorizacion"],
                                                    "id_rol": RolExtra,
                                                    "extra": True,
                                                })
                                    if roles_extras_new:
                                        SapPerfilesAutorizaciones.extend(roles_extras_new)

                                # HOME AUTORIZACIONES
                                for SapPerfilesAutorizacion in SapPerfilesAutorizaciones:
                                    if (
                                        SapPerfilesAutorizacion.get("id_rol")
                                        and SapPerfilesAutorizacion["id_rol"] not in RolesValidosParaTransaccion
                                    ):
                                        continue

                                    IdPerfil = SapPerfilesAutorizacion["id_perfil"]
                                    IdSapAutorizacion = SapPerfilesAutorizacion["id_autorizacion"]
                                    BolRol = True
                                    isExtra = ("extra" in SapPerfilesAutorizacion)

                                    if SapPerfilesAutorizacion.get("id_rol") and not isExtra:
                                        DatoRoles = DatoRoles_by_idrol.get(SapPerfilesAutorizacion["id_rol"], [])

                                        if len(DatoRoles) > 0:
                                            for DatoRol in DatoRoles:
                                                FechaInicio = int(DatoRol["fechainicio"].replace(tzinfo=timezone.utc).timestamp())
                                                FechaFin = int(DatoRol["fechafin"].replace(tzinfo=timezone.utc).timestamp())
                                                
                                                if FechaFin == max_date_sap_ts:
                                                    FechaFin = max_date_php_ts


                                                if not (FechaInicio <= now_ts and FechaFin >= now_ts):
                                                    BolRol = False
                                                else:
                                                    BolRol = True
                                                    break

                                    if BolRol:
                                        IdSapRol = (
                                            config.DEFAULT_ROL_ID
                                            if not SapPerfilesAutorizacion.get("id_rol")
                                            else SapPerfilesAutorizacion["id_rol"]
                                        )

                                        key_exists = (
                                            aPerfilAutorizacionesObjetoCampo
                                            .get(IdPerfil, {})
                                            .get(IdSapAutorizacion, {})
                                            .get(Objeto, {})
                                            .get(Campo)
                                            is not None
                                        )

                                        if not key_exists:
                                            CampoValores = []

                                            if not isExtra:
                                                # from Sapobjetoautorizacion                                            
                                                #CampoValores = [x for x in CampoValores_General if x["id_autorizacion"] == IdSapAutorizacion and x["objeto"] == Objeto and x["campo"] == Campo]
                                                CampoValores = cache["CampoValoresPorAutorizacion"].get(IdSapAutorizacion, {}).get(Objeto, {}).get(Campo, [])

                                                if BolCampoOrganizacional:
                                                    #get_active_by_proceso_rol_campo                                                
                                                    #AddCampoValores = [x for x in AddCampoValores_General if x["nivel_organizacional"] == f"${Campo}" and x["id_rol"] == IdSapRol]
                                                    AddCampoValores = AddCampoValores_General.get(f"${Campo}", {}).get(IdSapRol, [])
                                                    for AddCampoValor in AddCampoValores:
                                                        CampoValores.append(
                                                            {
                                                                "id_objeto": IdSapObjetoProcesoOFRisk,
                                                                "id_campo": IdSapCampoProcesoOFRisk,
                                                                "desde": AddCampoValor["desde"],
                                                                "hasta": AddCampoValor["hasta"],
                                                            }
                                                        )
                                                    
                                                    #get_active_by_proceso_rol_objeto_campo                                                
                                                    RolCampoValores = RolCampoValores_General.get(IdSapRol, {}).get(Objeto, {}).get(Campo, [])
                                                    #RolCampoValores = [x for x in RolCampoValores_General if x["id_rol"] == IdSapRol and x["objeto"] == Objeto and x["campo"] == Campo]
                                                    
                                                    for RolCampoValor in RolCampoValores:
                                                        CampoValores.append(
                                                            {
                                                                "id_objeto": RolCampoValor["id_objeto"],
                                                                "id_campo": RolCampoValor["id_campo"],
                                                                "desde": RolCampoValor["desde"],
                                                                "hasta": RolCampoValor["hasta"],
                                                            }
                                                        )
                                            else:                                            
                                                CampoValores = [x for x in CampoValores_Extra_General if x["id_rol"] == IdSapRol and x["objeto"] == Objeto and x["campo"] == Campo]
                                                if BolCampoOrganizacional:
                                                    #get_active_by_proceso_rol_campo                                                
                                                    AddCampoValores = [x for x in AddCampoValores_General if x["nivel_organizacional"] == f"${Campo}" and x["id_rol"] == IdSapRol]
                                                    for AddCampoValor in AddCampoValores:
                                                        CampoValores.append(
                                                            {
                                                                "id_objeto": IdSapObjetoProcesoOFRisk,
                                                                "id_campo": IdSapCampoProcesoOFRisk,
                                                                "desde": AddCampoValor["desde"],
                                                                "hasta": AddCampoValor["hasta"],
                                                            }
                                                        )

                                            for CampoValor in CampoValores:
                                                aPerfilAutorizacionesObjetoCampo.setdefault(IdPerfil, {}) \
                                                    .setdefault(IdSapAutorizacion, {}) \
                                                    .setdefault(Objeto, {}) \
                                                    .setdefault(Campo, []) \
                                                    .append(
                                                        {
                                                            "ID_OBJETO": CampoValor["id_objeto"],
                                                            "ID_CAMPO": CampoValor["id_campo"],
                                                            "DESDE": CampoValor["desde"],
                                                            "HASTA": CampoValor["hasta"],
                                                            "EXTRA": isExtra,
                                                        }
                                                    )

                                            if len(AutorizacionesExtras) > 0:
                                                for AutorizacionesExtra in AutorizacionesExtras:                                                    
                                                    p_perfil = aPerfilAutorizacionesObjetoCampo.setdefault(IdPerfil, {})
                                                    p_auto   = p_perfil.setdefault(IdSapAutorizacion, {})
                                                    p_obj    = p_auto.setdefault(Objeto, {})
                                                    p_campo  = p_obj.setdefault(Campo, [])
                                                    p_campo.append(
                                                        {
                                                            "ID_OBJETO": AutorizacionesExtra["id_objeto"],
                                                            "ID_CAMPO": AutorizacionesExtra["id_campo"],
                                                            "DESDE": AutorizacionesExtra["desde"],
                                                            "HASTA": AutorizacionesExtra["hasta"],
                                                            "EXTRA": True,
                                                        }
                                                    )

                                                    # aPerfilAutorizacionesObjetoCampo \
                                                    #     .setdefault(IdPerfil, {}) \
                                                    #     .setdefault(IdSapAutorizacion, {}) \
                                                    #     .setdefault(Objeto, {}) \
                                                    #     .setdefault(Campo, []) \
                                                    #     .append(
                                                    #         {
                                                    #             "ID_OBJETO": AutorizacionesExtra["id_objeto"],
                                                    #             "ID_CAMPO": AutorizacionesExtra["id_campo"],
                                                    #             "DESDE": AutorizacionesExtra["desde"],
                                                    #             "HASTA": AutorizacionesExtra["hasta"],
                                                    #             "EXTRA": True,
                                                    #         }
                                                    #     )
                                        else:
                                            CampoValores = []
                                            if isExtra:
                                                #get_active_by_proceso_rol_objeto_campo                                            
                                                CampoValores = [x for x in CampoValores_Extra_General if x["id_rol"] == IdSapRol and x["objeto"] == Objeto and x["campo"] == Campo]

                                                if BolCampoOrganizacional:
                                                    #get_active_by_proceso_rol_campo                                                
                                                    AddCampoValores = [x for x in AddCampoValores_General if x["nivel_organizacional"] == f"${Campo}" and x["id_rol"] == IdSapRol]
                                                    
                                                    for AddCampoValor in AddCampoValores:
                                                        CampoValores.append(
                                                            {
                                                                "id_objeto": ID_OBJETO,
                                                                "id_campo": ID_CAMPO,
                                                                "desde": AddCampoValor["desde"],
                                                                "hasta": AddCampoValor["hasta"],
                                                            }
                                                        )

                                            for CampoValor in CampoValores:
                                                aPerfilAutorizacionesObjetoCampo[IdPerfil][IdSapAutorizacion][Objeto][Campo] \
                                                    .append(
                                                        {
                                                            "ID_OBJETO": CampoValor["id_objeto"],
                                                            "ID_CAMPO": CampoValor["id_campo"],
                                                            "DESDE": CampoValor["desde"],
                                                            "HASTA": CampoValor["hasta"],
                                                            "EXTRA": isExtra,
                                                        }
                                                    )

                                            if len(AutorizacionesExtras) > 0:
                                                for AutorizacionesExtra in AutorizacionesExtras:
                                                    aPerfilAutorizacionesObjetoCampo[IdPerfil][IdSapAutorizacion][Objeto][Campo] \
                                                        .append(
                                                            {
                                                                "ID_OBJETO": AutorizacionesExtra["id_objeto"],
                                                                "ID_CAMPO": AutorizacionesExtra["id_campo"],
                                                                "DESDE": AutorizacionesExtra["desde"],
                                                                "HASTA": AutorizacionesExtra["hasta"],
                                                                "EXTRA": True,
                                                            }
                                                        )

                                        # Evaluación de matches contra valores del perfil
                                        if (
                                            IdPerfil in aPerfilAutorizacionesObjetoCampo
                                            and IdSapAutorizacion in aPerfilAutorizacionesObjetoCampo[IdPerfil]
                                            and Objeto in aPerfilAutorizacionesObjetoCampo[IdPerfil][IdSapAutorizacion]
                                            and Campo in aPerfilAutorizacionesObjetoCampo[IdPerfil][IdSapAutorizacion][Objeto]
                                        ):
                                            for CampoValor in aPerfilAutorizacionesObjetoCampo[IdPerfil][IdSapAutorizacion][Objeto][Campo]:
                                                IdSapObjetoProceso = CampoValor["ID_OBJETO"]
                                                IdSapCampoProceso = CampoValor["ID_CAMPO"]
                                                desde_perfil = str(CampoValor["DESDE"]).strip()
                                                hasta_perfil = str(CampoValor["HASTA"]).strip()

                                                for Valor in Valores["VALORES"]:
                                                    desde = str(Valor["DESDE"]).strip()
                                                    hasta = str(Valor["HASTA"]).strip()

                                                    Results = Helper2.BolCampoFindObjectAuthorization(
                                                        BolCampo,
                                                        desde,
                                                        desde_perfil,
                                                        hasta,
                                                        hasta_perfil,
                                                        comodin,
                                                        aResultPerfiles,
                                                        IdActividad,
                                                        Transaccion,
                                                        IdPerfil,
                                                        IdSapAutorizacion,
                                                        IdSapRol,
                                                        IdSapObjetoProceso,
                                                        Objeto,
                                                        IdSapCampoProceso,
                                                        Campo,
                                                    )
                                                    BolCampo = Results["BolCampo"]

                                                    # FIDELIDAD: replica el efecto lateral del PHP:
                                                    if desde == "PC00_M99_TLEA30":
                                                        # Asignación (no comparación) en PHP => cambiamos la variable
                                                        desde_perfil = "PC00_*"
                                                        # (las líneas de echo en PHP están comentadas)

                                                    aResultPerfiles = Results["aResultPerfiles"]

                                                    if BolCampo:
                                                        aObjetosCampos[Transaccion]["OBJETOS"][Objeto]["CAMPOS"][Campo]["CONDITION"] = BolCampo
                                                        aObjetosCampos[Transaccion]["OBJETOS"][Objeto]["CAMPOS"][Campo] \
                                                            .setdefault("AUTORIZACION", []) \
                                                            .append({"ID": IdSapAutorizacion, "ID_ROL": IdSapRol})
                                                        BolCampo = False

                                        # Limpieza de extras según el PHP
                                        if isExtra:
                                            try:
                                                del aPerfilAutorizacionesObjetoCampo[IdPerfil][IdSapAutorizacion][Objeto][Campo]
                                            except Exception:
                                                pass
                                        else:
                                            if (
                                                IdPerfil in aPerfilAutorizacionesObjetoCampo
                                                and IdSapAutorizacion in aPerfilAutorizacionesObjetoCampo[IdPerfil]
                                                and Objeto in aPerfilAutorizacionesObjetoCampo[IdPerfil][IdSapAutorizacion]
                                                and Campo in aPerfilAutorizacionesObjetoCampo[IdPerfil][IdSapAutorizacion][Objeto]
                                            ):
                                                to_remove = []
                                                for idx, subArray in enumerate(aPerfilAutorizacionesObjetoCampo[IdPerfil][IdSapAutorizacion][Objeto][Campo]):
                                                    if subArray.get("EXTRA") is True:
                                                        to_remove.append(idx)
                                                # eliminar en reversa para mantener índices
                                                for idx in reversed(to_remove):
                                                    del aPerfilAutorizacionesObjetoCampo[IdPerfil][IdSapAutorizacion][Objeto][Campo][idx]

                                        # Registrar Rol
                                        if IdSapRol not in aResultPerfiles["Actividad"][IdActividad]["Roles"]:
                                            aResultPerfiles["Actividad"][IdActividad]["Roles"][IdSapRol] = IdSapRol

                                # END AUTORIZACIONES (por campo)

                        # Recolectar autorizaciones válidas vs inválidas por objeto
                        int_campos_true = 0

                        Autorizaciones = {}                        

                        
                        Autorizaciones = OrderedDict()
                        auth_ids_por_campo = {}

                        # locals de #8:
                        obj_trans   = aObjetosCampos[Transaccion]
                        obj_campo_nodos = obj_trans["OBJETOS"][Objeto]["CAMPOS"]
                        
                        for Campo2, nodo in obj_campo_nodos.items():
                            if nodo["CONDITION"]:
                                ids = {a["ID"] for a in nodo.get("AUTORIZACION", [])}
                                auth_ids_por_campo[Campo2] = ids
                                for aid in ids:
                                    if aid not in Autorizaciones:
                                        Autorizaciones[aid] = aid

                        AutorizacionesValidas = []
                        AutorizacionesInvalidas = []
                        cantidad_campos = len(obj_campo_nodos)

                        for Autorizacion in Autorizaciones.values():
                            IntAutorizacion = 0                            
                            for Campo2, nodo in obj_campo_nodos.items():
                                    if nodo["CONDITION"] and Autorizacion in auth_ids_por_campo.get(Campo2, set()):
                                        IntAutorizacion += 1
                            if IntAutorizacion == cantidad_campos:
                                AutorizacionesValidas.append(Autorizacion)
                            else:
                                AutorizacionesInvalidas.append(Autorizacion)

                        if len(AutorizacionesValidas) == 0:
                            for Campo2, Valores2 in Campos["CAMPOS"].items():
                                aObjetosCampos[Transaccion]["OBJETOS"][Objeto]["CAMPOS"][Campo2]["CONDITION"] = False

                        if len(AutorizacionesInvalidas) > 0:
                            for AutorizacionesInvalida in AutorizacionesInvalidas:
                                # limpiar TransaccionPerfiles
                                if Transaccion in aResultPerfiles["Actividad"][IdActividad]["TransaccionPerfiles"]:                                    
                                    arr = aResultPerfiles["Actividad"][IdActividad]["TransaccionPerfiles"][Transaccion]
                                    arr[:] = [x for x in arr if not (
                                        x["IdTransaccion"] == Transaccion and
                                        x["IdSapAutorizacion"] == AutorizacionesInvalida and
                                        x["Objeto"] == Objeto
                                    )]


                        # conteo de campos verdaderos
                        for Campo2, Valores2 in Campos["CAMPOS"].items():
                            condicion = aObjetosCampos[Transaccion]["OBJETOS"][Objeto]["CAMPOS"][Campo2]["CONDITION"]
                            if condicion:
                                int_campos_true += 1

                        if cantidad_campos == int_campos_true:
                            aObjetosCampos[Transaccion]["OBJETOS"][Objeto]["CONDITION"] = True

                        aResultPerfiles["Actividad"][IdActividad].setdefault("TransaccionObjeto", {}).setdefault(
                            Transaccion, {}
                        )[Objeto] = {}
                        # En el PHP guardan por [Objeto][Campo]; aquí preservamos el último estado por campo
                        for Campo2 in Campos["CAMPOS"].keys():
                            aResultPerfiles["Actividad"][IdActividad]["TransaccionObjeto"][Transaccion][Objeto][
                                Campo2
                            ] = aObjetosCampos[Transaccion]["OBJETOS"][Objeto]["CONDITION"]

                    # condición por transacción
                    int_objetos_true = 0
                    cantidad_objetos = len(Objetos["OBJETOS"])
                    for Objeto2, Valores2 in Objetos["OBJETOS"].items():
                        condicion = aObjetosCampos[Transaccion]["OBJETOS"][Objeto2]["CONDITION"]
                        if condicion:
                            int_objetos_true += 1

                    if cantidad_objetos == int_objetos_true:
                        aObjetosCampos[Transaccion]["CONDITION"] = True
                        aResultPerfiles["Actividad"][IdActividad]["Transaccion"].append(Transaccion)

            # Actividad CONDITION
            cantidad_transacciones = [Obj for Obj in aObjetosCampos.values() if Obj.get("CONDITION")]
            if len(cantidad_transacciones) > 0:
                aActividades[IdActividad]["CONDITION"] = True
                aResultPerfiles["Actividad"][IdActividad]["CONDITION"] = True

        total_actividades = len(aActividades)
        cantidad_actividades = [Obj for Obj in aActividades.values() if Obj.get("CONDITION")]
        aPerfilAutorizacionesObjetoCampo = aPerfilAutorizacionesObjetoCampo
        if total_actividades == len(cantidad_actividades):
            aResultPerfiles["CONDITION"] = True

        # Bloque final (en PHP está apagado con && false)
        if aResultPerfiles.get("CONDITION") and False:
            aResultPerfiles = self.helper.AddActividadRolCampo(aResultPerfiles, SapNivelOrganizacionales, "$BUKRS", "Bukrs")
            if not self.helper.BolActividadRolCampo(aResultPerfiles, "Bukrs", self.comodin):
                aResultPerfiles = self.helper.AddActividadRolCampo(aResultPerfiles, SapNivelOrganizacionales, "$WERKS", "Werks")
                if not self.helper.BolActividadRolCampo(aResultPerfiles, "Werks", self.comodin):
                    aResultPerfiles["CONDITION"] = False

        return aResultPerfiles
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        message = f"Exception: {e} in {fname}:{exc_tb.tb_lineno}"
        print(message)
        raise
 
def process_execute(only_user_ids,id_version, job_id, user_id, total_users, idx_shard, total_shards, limit_date):
    if len(only_user_ids) == 0:
        return
    
    time_start = time.perf_counter()
    now_dt = parse_limit_date(limit_date)

    conflictosLista = []
    limiteConflicto = 3000
    IntBatch  = 0
    IntUsuario = 0
    batchConflicto = 0
    progress = 10    

    print(f"Inicio de Análisis: {str(now_dt)}")

    try:
        session = SessionLocal()
        
        myuser = session.query(AppUser).filter(AppUser.Id == user_id).first()

        version = session.query(Version).filter(Version.Id == id_version).first()
        proceso = session.query(Proceso).filter(Proceso.Id == version.IdProceso).first()

        Campos = ["$BUKRS", "$WERKS"]

        sopr = aliased(sapobjetoproceso)
        scpr = aliased(sapcampoproceso)
        sno = aliased(SapNivelOrganizacional)
        sur = aliased(SapUsuarioRol)
        
        SapNivelOrganizacionales = session.query(SapNivelOrganizacional.IdSapRol.label("id_rol"),
                                                    SapNivelOrganizacional.NivelOrganizacional.label("nivelorganizacional"),
                                                    SapNivelOrganizacional.Desde.label("desde"),
                                                    SapNivelOrganizacional.Hasta.label("hasta")).filter(
                                                        SapNivelOrganizacional.IdMatrizSap == proceso.IdMatrizSap,
                                                        SapNivelOrganizacional.NivelOrganizacional.in_(Campos),
                                                        SapNivelOrganizacional.Desde != '').order_by(SapNivelOrganizacional.Desde).all()
        
        CamposOrganizacionales = session.query(SapCampoOrganizacional).filter(SapCampoOrganizacional.IdMatrizSap == proceso.IdMatrizSap).all() 

        CamposOrganizacionalesIndex = defaultdict(list)
        for obj in CamposOrganizacionales:
            CamposOrganizacionalesIndex[obj.Campo].append(obj) 
        
        CamposOrganizacionales = CamposOrganizacionalesIndex
                      
        IdRegla = proceso.IdRegla
        Riesgos = session.query(Riesgo).filter(and_(Riesgo.IdRegla == IdRegla)).order_by(desc(Riesgo.Id)).all()

        print(f"Cantidad de Riesgos: {len(Riesgos)}")

        
        riesgo_ids = [r.Id for r in Riesgos]
        rows = (
            session.query(
                RiesgoActividadTransaccion.IdRiesgo.label("id_riesgo"),
                RiesgoActividadTransaccion.IdActividad.label("id_actividad")
            )
            .filter(RiesgoActividadTransaccion.IdRiesgo.in_(riesgo_ids))
            .distinct()
        ).all()

        RiesgosActividad = defaultdict(list)
        actividad_ids = []

        for row in rows:
            RiesgosActividad[row.id_riesgo].append(row)
            actividad_ids.append(row.id_actividad)


        IdSistemaSap = config.SYSTEMS['SAP']
        IdSistemaFiori = config.SYSTEMS['FIORI']

        stmt = (
            select(sno.Desde.label("desde"),
            sno.Hasta.label("hasta"),
            sno.NivelOrganizacional.label("nivel_organizacional"),
            sno.IdSapRol.label("id_rol"))
            .where(and_(sno.IdMatrizSap == proceso.IdMatrizSap,
                sno.Desde != '',
                sno.Estado == 1))
            .order_by(sno.Desde)
        )
        AddCampoValores_General = session.execute(stmt).mappings().all()

        stmt = (
            select(
                sopr.Id.label("id"),
                sopr.IdMatrizSap.label("idmatrizsap"),
                sopr.Nombre.label("nombre"),
                sopr.Descripcion.label("descripcion")
            )                                
            .where(sopr.IdMatrizSap == proceso.IdMatrizSap)
            .order_by(desc(sopr.Id))                                
        )
        #SapObjetoProceso_General = session.execute(stmt).mappings().all()
        SapObjetoProceso_General = [dict(r) for r in session.execute(stmt).mappings().all()]

        stmt = (
            select(
                scpr.Id.label("id"),
                scpr.IdMatrizSap.label("idmatrizsap"),
                scpr.Nombre.label("nombre"),
                scpr.Descripcion.label("descripcion")
            )                                
            .where(scpr.IdMatrizSap == proceso.IdMatrizSap)
            .order_by(desc(scpr.Id))                                
        )
        #SapCampoProceso_General = session.execute(stmt).mappings().all()
        SapCampoProceso_General = [dict(r) for r in session.execute(stmt).mappings().all()]

        riat = aliased(RiesgoActividadTransaccion)
        ri = aliased(Riesgo)
        Registros_General = session.query(riat).join(ri, riat.IdRiesgo == ri.Id).filter(ri.IdRegla == IdRegla).all()
        Transacciones_General = session.query(Transaccion).filter(Transaccion.IdRegla == IdRegla).all()        
        TransaccionesById = {
            t.Id: t
            for t in Transacciones_General
        }

        transacciones_ids = [t.Id for t in Transacciones_General]
        transacciones_codigo_id = {
            t.Codigo: t.Id
            for t in Transacciones_General
        }

        
        index_riat = defaultdict(list)

        for x in Registros_General:
            index_riat[(x.IdRiesgo, x.IdActividad)].append(x)        


        # PREFETCH GENERAL
        
        _global = prefetch_global_data(session, IdRegla, proceso, only_user_ids,actividad_ids, transacciones_ids, transacciones_codigo_id)


        UsuariosTransaccionesExtras = {}
        UsuariosRolesExtras = {}
        UsuariosAutorizacionesExtras = {}

        print("Obteniendo usuarios ....")

        
        Usuarios = [
            uid for (uid,) in session.query(
                        SapUsuario.IdUsuario
                    ).filter(
                        SapUsuario.IdMatrizSap == proceso.IdMatrizSap,
                        or_(
                            SapUsuario.FechaInicio == None,
                            SapUsuario.FechaInicio <= now_dt
                        ),
                        SapUsuario.FechaFin >= now_dt,
                        SapUsuario.Uflag.in_([0, 128]),
                        SapUsuario.IdUsuario.in_(only_user_ids)                    
                    ).order_by(SapUsuario.IdUsuario).distinct().all()
        ]

        
        print(f"Usuarios a analizar: {len(Usuarios)}")

        total_shards = 1 if total_shards == 0 else total_shards

        progress_per_user = round(round(85 / len(Usuarios) if len(Usuarios) > 0 else 0, 2)/total_shards, 2)
        for usuario in Usuarios:
            IntBatch += 1
            IntUsuario += 1
            time_start_user = time.perf_counter()

            data_storage = storage.get_status(job_id)
            progress = data_storage.get("progress", 0) if data_storage else 0
            if progress < 100:
                progress += progress_per_user
                print(f"Avance en SHARD #{idx_shard}: {progress:.2f}% - Procesando usuario {IntUsuario}/{len(Usuarios)}")
                storage.update_progress(job_id, progress)                

            IdUsuario = usuario

            print(f"Usuario en análisis: {str(IdUsuario)}")

            TransaccionesUsuario = session.query(UsuarioTransaccion).where(
                and_(
                    UsuarioTransaccion.IdProceso == proceso.Id,
                    UsuarioTransaccion.IdUsuario == IdUsuario,
                    UsuarioTransaccion.Estado == 1
                )
            ).order_by(UsuarioTransaccion.Id).all()
            aTransaccionesUsuario = [tu.IdTransaccion for tu in TransaccionesUsuario]
            if IdUsuario in UsuariosTransaccionesExtras:
                aTransaccionesUsuario.extend(UsuariosTransaccionesExtras[IdUsuario])
            aTransaccionesUsuario = list(set(aTransaccionesUsuario))

            aTrans_set = set(aTransaccionesUsuario)

            # Construir aActividades para este usuario (similar a lo que se hace después)
            aActividades_usuario = {}
            aActividadesIds = []
            for riesgo in Riesgos:
                IdRiesgo = riesgo.Id
                TotalActividades = len(RiesgosActividad[IdRiesgo])
                IntActividad = 0
                for Actividad in RiesgosActividad[IdRiesgo]:
                    IdActividad = Actividad.id_actividad
                    aActividadesIds.append(IdActividad)

                    bucket = index_riat.get((IdRiesgo, IdActividad), [])
                    Registros = [x for x in bucket if x.IdTransaccion in aTrans_set]

                    #Registros = [x for x in Registros_General if x.IdRiesgo == IdRiesgo and x.IdActividad == IdActividad and x.IdTransaccion in aTransaccionesUsuario]
                    # Registros = session.query(RiesgoActividadTransaccion).filter(
                    #     RiesgoActividadTransaccion.IdRiesgo == IdRiesgo,
                    #     RiesgoActividadTransaccion.IdActividad == IdActividad,
                    #     RiesgoActividadTransaccion.IdTransaccion.in_(aTransaccionesUsuario)
                    # ).all()
                    if len(Registros) > 0:
                        IntActividad += 1
                        for Registro in Registros:
                            if IdActividad not in aActividades_usuario:
                                aActividades_usuario[IdActividad] = {"TRANSACCIONES": [], "CONDITION": False}
                            aActividades_usuario[IdActividad]["TRANSACCIONES"].append(Registro.IdTransaccion)

            # LLAMADA AL PREFETCH OPTIMIZADO PARA ESTE USUARIO
            cache_usuario = prefetch_data_for_user_optimized_v2(
                session,
                IdUsuario,
                proceso,
                IdRegla,
                aActividades_usuario,
                aActividadesIds,
                aTransaccionesUsuario,
                SapObjetoProceso_General,
                SapCampoProceso_General,
                _global
            )


            # Creamos el cache final que se pasará a FindObjectAuthorizationByPerfil_optimized
            cache_final = {
                # Datos globales
                "SapObjetoProceso_General": SapObjetoProceso_General,
                "SapCampoProceso_General": SapCampoProceso_General,
                "AddCampoValores_General": AddCampoValores_General,  # global indexado
                # Datos específicos del usuario (sobrescriben si es necesario)
                **cache_usuario,
                "Roles_Transacciones": _global.get("roles_por_transaccion", defaultdict(set))
            }            

            for riesgo in Riesgos:
                IdRiesgo = riesgo.Id

                TotalActividades = len(RiesgosActividad[IdRiesgo])
                IntActividad = 0
                Riesgoactividadtransacciones = []

                for Actividad in RiesgosActividad[IdRiesgo]:
                    IdActividad = Actividad.id_actividad

                    bucket = index_riat.get((IdRiesgo, IdActividad), [])
                    Registros = [x for x in bucket if x.IdTransaccion in aTrans_set]
                    #Registros = [x for x in Registros_General if x.IdRiesgo == IdRiesgo and x.IdActividad == IdActividad and x.IdTransaccion in aTransaccionesUsuario]
                    # Registros = session.query(RiesgoActividadTransaccion).filter(
                    #         RiesgoActividadTransaccion.IdRiesgo == IdRiesgo,
                    #         RiesgoActividadTransaccion.IdActividad == IdActividad,
                    #         RiesgoActividadTransaccion.IdTransaccion.in_(aTransaccionesUsuario)
                    #     ).all()
                    for Registro in Registros:
                        Riesgoactividadtransacciones.append(Registro)
                    if len(Registros) > 0:
                        IntActividad += 1

                if TotalActividades == IntActividad:
                    aActividades = {}
                    aActividadesFiori = {}
                    aRiesgos = []

                    for RAT in Riesgoactividadtransacciones:                      
                        _IdRiesgo = RAT.IdRiesgo
                        _IdActividad = RAT.IdActividad
                        if _IdActividad not in aActividades:
                            aActividades[_IdActividad] = {"TRANSACCIONES": [], "CONDITION": False}

                        IdTransaccion = RAT.IdTransaccion
                        aActividades[_IdActividad]["TRANSACCIONES"].append(IdTransaccion)

                        TransaccionObj = TransaccionesById.get(IdTransaccion)

                        if TransaccionObj and TransaccionObj.IdSistema == IdSistemaFiori:
                            if _IdActividad not in aActividadesFiori:
                                aActividadesFiori[_IdActividad] = {"TRANSACCIONES": {}}
                            aActividadesFiori[_IdActividad]["TRANSACCIONES"][IdTransaccion] = IdTransaccion

                        aRiesgos.append({
                            "ID":  RAT.Id,
                            "ID_RIESGO": _IdRiesgo,
                            "ID_ACTIVIDAD": _IdActividad,
                            "ID_TRANSACCION": IdTransaccion
                        })                    

                    # Buscar autorizaciones por perfil (método externo)
                    aFind = FindObjectAuthorizationByPerfil(
                        SapNivelOrganizacionales,
                        aActividades,
                        aActividadesFiori,
                        UsuariosRolesExtras.get(IdUsuario, []),
                        UsuariosAutorizacionesExtras.get(IdUsuario, []),
                        CamposOrganizacionales,
                        cache_final,
                        now_dt
                    )                    


                    if aFind.get("CONDITION"):
                        # Por cada actividad/transacción detectada
                        print(f"Usuario {str(IdUsuario)} con conflictos")
                        now_cnf = datetime.now(TZ_LIMA)

                        for IdSapActividad, aFindTransacciones in aFind["Actividad"].items():
                            for IdSapTransaccion in aFindTransacciones["Transaccion"]:
                                # Buscar el registro RAT correspondiente
                                aRiesgoactividadtransacciones = [
                                    obj for obj in aRiesgos
                                    if obj["ID_ACTIVIDAD"] == IdSapActividad and obj["ID_TRANSACCION"] == IdSapTransaccion
                                ]
                                if len(aRiesgoactividadtransacciones) > 0:
                                    osTransaccion = session.get(Transaccion, IdSapTransaccion)

                                    # SAP ECC/S4 (no FIORI)
                                    if osTransaccion.IdSistema == IdSistemaSap:
                                        DataPerfiles = aFind["Actividad"][aRiesgoactividadtransacciones[0]["ID_ACTIVIDAD"]]["TransaccionPerfiles"][aRiesgoactividadtransacciones[0]["ID_TRANSACCION"]]
                                        for DataPerfil in DataPerfiles:
                                            conflictosLista.append(
                                                {
                                                    "IdVersion": version.Id,
                                                    "IdUsuario": IdUsuario,
                                                    "IdSapPerfil": DataPerfil["IdSapPerfil"],
                                                    "IdSapAutorizacion": DataPerfil["IdSapAutorizacion"],
                                                    "IdSapRol": DataPerfil["IdSapRol"],
                                                    "IdRiesgoActividadTransaccion": aRiesgoactividadtransacciones[0]["ID"],
                                                    "IdRiesgo": aRiesgoactividadtransacciones[0]["ID_RIESGO"],
                                                    "IdActividad": aRiesgoactividadtransacciones[0]["ID_ACTIVIDAD"],
                                                    "IdTransaccion": aRiesgoactividadtransacciones[0]["ID_TRANSACCION"],
                                                    "IdSapObjetoProceso": DataPerfil["IdObjeto"],
                                                    "IdSapCampoProceso": DataPerfil["IdCampo"],
                                                    "Desde": DataPerfil["Desde"],
                                                    "Hasta": DataPerfil["Hasta"],
                                                    "IdAppUserCreacion": myuser.Id,
                                                    "IdAppUserActualizacion": myuser.Id,
                                                    "FechaCreacion": now_cnf,
                                                    "FechaActualizacion": now_cnf,
                                                    "Estado": 1
                                                }
                                            )

                                            batchConflicto += 1
                                            if batchConflicto == limiteConflicto:
                                                session.execute(insert(Conflicto), conflictosLista)
                                                session.commit() 
                                                conflictosLista.clear()

                                    # FIORI (roles)
                                    elif osTransaccion.IdSistema == IdSistemaFiori:
                                        DataRoles = (
                                            session.query(usuariotransaccionrol.UsuarioTransaccionRol)
                                                .filter(
                                                    usuariotransaccionrol.UsuarioTransaccionRol.IdProceso == proceso.Id,
                                                    usuariotransaccionrol.UsuarioTransaccionRol.IdUsuario == IdUsuario,
                                                    usuariotransaccionrol.UsuarioTransaccionRol.IdTransaccion == IdSapTransaccion,
                                                    # Si hay un flag de activo/estado en tu tabla:
                                                    getattr(usuariotransaccionrol.UsuarioTransaccionRol, "activo", True) == True
                                                )
                                                .all()
                                        )
                                        if len(DataRoles) > 0:
                                            for DataRol in DataRoles:
                                                conflictosLista.append(
                                                    {
                                                        "IdVersion": version.Id,
                                                        "IdUsuario": IdUsuario,
                                                        "IdSapPerfil": None,
                                                        "IdSapAutorizacion": None,
                                                        "IdSapRol": DataRol.IdSapRol,
                                                        "IdRiesgoActividadTransaccion": aRiesgoactividadtransacciones[0]["ID"],
                                                        "IdRiesgo": aRiesgoactividadtransacciones[0]["ID_RIESGO"],
                                                        "IdActividad": aRiesgoactividadtransacciones[0]["ID_ACTIVIDAD"],
                                                        "IdTransaccion": aRiesgoactividadtransacciones[0]["ID_TRANSACCION"],
                                                        "IdSapObjetoProceso": None,
                                                        "IdSapCampoProceso": None,
                                                        "Desde": "",
                                                        "Hasta": "",
                                                        "IdAppUserCreacion": myuser.Id,
                                                        "IdAppUserActualizacion": myuser.Id,
                                                        "FechaCreacion": now_cnf,
                                                        "FechaActualizacion": now_cnf,
                                                        "Estado": 1
                                                    }
                                                )

                                                batchConflicto += 1
                                                if batchConflicto == limiteConflicto:
                                                    session.execute(insert(Conflicto), conflictosLista)
                                                    session.commit()
                                                    conflictosLista.clear()

                                    if conflictosLista:
                                        print("INSERTADOS")
                                        session.execute(insert(Conflicto), conflictosLista)
                                        session.commit()
                                        conflictosLista.clear()
            time_end_user = time.perf_counter()
            totalTimeUser = time_end_user - time_start_user
            print(f"VERSIÓN #{id_version} - Fin de Análisis para usuario {str(IdUsuario)}: Tiempo total: {totalTimeUser:.2f} segundos")
            
        session.flush()
        time_end = time.perf_counter()
        totalTime = time_end - time_start                        
        print(f"Fin de Análisis para SHARD #{idx_shard}: Tiempo total: {totalTime:.2f} segundos")        
        return True                
    except Exception as e:
        session.rollback()
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        message = f"Exception en SHARD #{idx_shard} de la versión #{id_version}: {e} line {fname}:{exc_tb.tb_lineno}"
        storage.update_job_with_errors(job_id, [message])
        print(message)
    finally:
        data_storage = storage.get_status(job_id)
        progress = data_storage.get("progress", 0) if data_storage else 0
        if progress >= 85:            
            cantidad = session.query(Conflicto.IdUsuario,RiesgoActividadTransaccion.IdRiesgo
                                    ).join(RiesgoActividadTransaccion, Conflicto.IdRiesgoActividadTransaccion == RiesgoActividadTransaccion.Id
                                    ).filter(Conflicto.IdVersion == id_version
                                    ).group_by(Conflicto.IdUsuario,RiesgoActividadTransaccion.IdRiesgo
                                    ).count()
            
            versionObj = session.get(Version, id_version)  
            procesoObj = session.get(Proceso, versionObj.IdProceso)

            versionObj.Tiempo = totalTime
            procesoObj.Tiempo = totalTime

            versionObj.Cantidad = cantidad
            procesoObj.Cantidad = cantidad

            versionObj.Procesado = True
            procesoObj.Procesado = True

            session.commit()
            
            storage.update_progress(job_id, 100)
            storage.complete_job(job_id)

            print("Análisis Completo.")

        session.close()

def prefetch_data_for_user_optimized_v2(session, IdUsuario, proceso, IdRegla, aActividades,
                                     aActividadesIds, aTransaccionesUsuario,
                                     SapObjetoProceso_General, SapCampoProceso_General,
                                     g):
    """
    MISMO OUTPUT QUE TU FUNCIÓN ORIGINAL
    PERO USANDO SOLO DATOS GLOBALMENTE PRECARGADOS EN 'g'
    """
    # 1) Roles
    DatoRoles_General = g["roles_by_user"][IdUsuario]
    roles_usuario = g["roles_ids_by_user"][IdUsuario]

    # 2) RolCampoValores
    RolCampoValoresIndex = g["RolCampoValoresIndex"]

    # 3) AddCampoValores
    AddCampoValoresIndex = g["AddCampoValoresIndex"]

    # 4) Extra valores
    CampoValores_Extra_General = [
        x for x in g["CampoValores_Extra_General"]
        if x["id_rol"] in roles_usuario
    ]

    # 5) SapObjetoCampos (ya indexado)
    sap_objeto_campos_index = g["sap_objeto_campos_index"]
    sap_objeto_campos_index_v2 = g["SapObjetoCampos_General"]

    # 6) PerfilesAutorizaciones
    perfiles_aut = g["perfiles_by_user"][IdUsuario]

    perfiles_autorizaciones_index = defaultdict(list)
    for r in perfiles_aut:
        perfiles_autorizaciones_index[r["nombre_objeto"]].append(r)

    autorizaciones_ids = list(g["autorizaciones_ids_by_user"][IdUsuario])

    # 7) CampoValores por Autorización
    campo_valores_index = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    if autorizaciones_ids:
        soa = aliased(SapObjetoAutorizacion)
        sopr = aliased(sapobjetoproceso)
        scpr = aliased(sapcampoproceso)

        stmt = (
            select(
                soa.IdSapAutorizacion.label("id_autorizacion"),
                sopr.Nombre.label("objeto"),
                scpr.Nombre.label("campo"),
                soa.IdSapObjetoProceso.label("id_objeto"),
                soa.IdSapCampoProceso.label("id_campo"),
                soa.Desde.label("desde"),
                soa.Hasta.label("hasta")
            )
            .join(sopr, soa.IdSapObjetoProceso == sopr.Id)
            .join(scpr, soa.IdSapCampoProceso == scpr.Id)
            .where(
                and_(
                    soa.IdMatrizSap == proceso.IdMatrizSap,
                    soa.IdSapAutorizacion.in_(autorizaciones_ids),
                    soa.Desde != '',
                    soa.Estado == 1
                )
            )
        )

        rows = session.execute(stmt).mappings().all()

        for r in rows:
            campo_valores_index[r["id_autorizacion"]][r["objeto"]][r["campo"]].append(r)
    else:
        campo_valores_index = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    # 8) Objetos Lista
    objetos_lista_index = defaultdict(list)
    for act, rows in sap_objeto_campos_index_v2.items():
        for r in rows:
            objetos_lista_index[act].append(r["nombre_objeto"])

    # 9) PerfilesAutorizaciones_General (misma salida)
    PerfilesAutorizaciones_General = perfiles_aut

    # 10) CampoValores_General (misma salida)
    CampoValores_General = []
    for aut in autorizaciones_ids:
        if aut in campo_valores_index:
            for obj in campo_valores_index[aut]:
                for cam in campo_valores_index[aut][obj]:
                    CampoValores_General.extend(campo_valores_index[aut][obj][cam])

    return {
        "DatoRoles_General": DatoRoles_General,
        "roles_usuario": roles_usuario,
        "RolCampoValores_General": RolCampoValoresIndex,
        "CampoValores_Extra_General": CampoValores_Extra_General,
        "AddCampoValores_General": AddCampoValoresIndex,
        "SapObjetoProceso_General": SapObjetoProceso_General,
        "SapCampoProceso_General": SapCampoProceso_General,
        "sap_objeto_campos_index": sap_objeto_campos_index,
        "perfiles_autorizaciones_index": perfiles_autorizaciones_index,
        "campo_valores_index": campo_valores_index,
        "SapObjetoCampos_General": sap_objeto_campos_index_v2,
        "Objetos_Lista_General": objetos_lista_index,
        "PerfilesAutorizaciones_General": PerfilesAutorizaciones_General,
        "CampoValores_General": CampoValores_General
    }
   
def prefetch_global_data(session, IdRegla, proceso, all_users, aActividadesIds, aTransaccionesUsuario, aTransaccionesNombresUsuario):
    """
    Corre una sola vez por Job.
    Devuelve TODOS los datos pre-cargados e indexados para evitar consultas por usuario.
    """

    # -----------------------------------------------------------
    # 1. SapObjetoCampos (antes 1 query por usuario → ahora 1 query global)
    # -----------------------------------------------------------
    soc = aliased(sapobjetocampo)
    t = aliased(transaccion)
    so = aliased(SapObjeto)
    sc = aliased(SapCampo)

    stmt_soc = (
        select(
            soc.IdActividad.label("id_actividad"),
            soc.IdTransaccion.label("id_transaccion"),
            t.Codigo.label("codigo"),
            soc.IdSapObjeto.label("id_objeto"),
            so.Nombre.label("nombre_objeto"),
            soc.IdSapCampo.label("id_campo"),
            sc.Nombre.label("nombre_campo"),
            soc.Desde.label("desde"),
            soc.Hasta.label("hasta"),
            soc.Condicional.label("condicional")
        )
        .join(t, t.Id == soc.IdTransaccion)
        .join(so, so.Id == soc.IdSapObjeto)
        .join(sc, sc.Id == soc.IdSapCampo)
        .where(
            and_(
                soc.IdRegla == IdRegla,
                soc.IdActividad.in_(aActividadesIds),
                soc.IdTransaccion.in_(aTransaccionesUsuario)
            )
        )
        .distinct()
    )

    soc_rows = session.execute(stmt_soc).mappings().all()

    # Índice O(1)
    sap_objeto_campos_index = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )
    sap_objeto_campos_index_v2 = defaultdict(list)
    objetos_unicos = set()
    campos_unicos = set()

    for r in soc_rows:
        act = r["id_actividad"]
        tran = r["id_transaccion"]
        obj = r["nombre_objeto"]
        cam = r["nombre_campo"]

        sap_objeto_campos_index[act][tran][obj][cam].append(r)
        sap_objeto_campos_index_v2[act].append(r)

        objetos_unicos.add(obj)
        campos_unicos.add(cam)

    # -----------------------------------------------------------
    # 2. Roles por usuario (antes 2 queries por usuario)
    # -----------------------------------------------------------
    sur = aliased(SapUsuarioRol)

    stmt_roles = (
        select(
            sur.IdUsuario.label("id_usuario"),
            sur.IdSapRol.label("id_rol"),
            sur.FechaInicio.label("fechainicio"),
            sur.FechaFin.label("fechafin")
        )
        .where(
            and_(
                sur.IdMatrizSap == proceso.IdMatrizSap,
                sur.Estado == 1,
                sur.IdUsuario.in_(all_users)
            )
        )
    )

    roles_rows = session.execute(stmt_roles).mappings().all()

    roles_by_user = defaultdict(list)
    roles_ids_by_user = defaultdict(list)
    roles_ids = []

    for r in roles_rows:
        roles_by_user[r["id_usuario"]].append(r)
        roles_ids_by_user[r["id_usuario"]].append(r["id_rol"])
        roles_ids.append(r["id_rol"])

    # -----------------------------------------------------------
    # 3. RolCampoValores (antes 1 query por usuario)
    # -----------------------------------------------------------
    sroa = aliased(SapRolObjetoAutorizacion)
    sopr = aliased(sapobjetoproceso)
    scpr = aliased(sapcampoproceso)
    sur = aliased(SapUsuarioRol)

    stmt_rolcampo = (
        select(
            sroa.IdSapRol.label("id_rol"),
            sopr.Nombre.label("objeto"),
            scpr.Nombre.label("campo"),
            sroa.IdSapObjetoProceso.label("id_objeto"),
            sroa.IdSapCampoProceso.label("id_campo"),
            sroa.Desde.label("desde"),
            sroa.Hasta.label("hasta")
        )
        .join(sopr, sroa.IdSapObjetoProceso == sopr.Id)
        .join(scpr, sroa.IdSapCampoProceso == scpr.Id)        
        .where(
            and_(
                sroa.IdMatrizSap == proceso.IdMatrizSap,
                sroa.Desde != '',
                sroa.IdSapRol.in_(roles_ids)
            )
        )
    )

    rolcampo_rows = session.execute(stmt_rolcampo).mappings().all()

    RolCampoValoresIndex = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    RolesByTransactionIndex = defaultdict(set)

    for r in rolcampo_rows:
        RolCampoValoresIndex[r["id_rol"]][r["objeto"]][r["campo"]].append(r)
        
        if r["objeto"] == "S_TCODE":
            cod = r["desde"]

            IdTransaccion = aTransaccionesNombresUsuario.get(cod)
            if IdTransaccion:
                RolesByTransactionIndex[IdTransaccion].add(r["id_rol"])


    # -----------------------------------------------------------
    # 4. AddCampoValores (antes 1 query por usuario)
    # -----------------------------------------------------------
    sno = aliased(SapNivelOrganizacional)

    stmt_add = (
        select(
            sno.IdSapRol.label("id_rol"),
            sno.NivelOrganizacional.label("nivel_organizacional"),
            sno.Desde.label("desde"),
            sno.Hasta.label("hasta")
        )
        .where(
            and_(
                sno.IdMatrizSap == proceso.IdMatrizSap,
                sno.Estado == 1,
                sno.Desde != ''
            )
        )
    )

    add_rows = session.execute(stmt_add).mappings().all()

    AddCampoValoresIndex = defaultdict(lambda: defaultdict(list))

    for r in add_rows:
        AddCampoValoresIndex[r["nivel_organizacional"]][r["id_rol"]].append(r)

    # -----------------------------------------------------------
    # 5. CampoValores Extra (antes 1 query por usuario)
    # -----------------------------------------------------------
    stmt_extra = (
        select(
            sroa.IdSapRol.label("id_rol"),
            sopr.Nombre.label("objeto"),
            scpr.Nombre.label("campo"),
            sroa.IdSapObjetoProceso.label("id_objeto"),
            sroa.IdSapCampoProceso.label("id_campo"),
            sroa.Desde.label("desde"),
            sroa.Hasta.label("hasta")
        )
        .join(sopr, sroa.IdSapObjetoProceso == sopr.Id)
        .join(scpr, sroa.IdSapCampoProceso == scpr.Id)
        .where(
            and_(
                sroa.IdMatrizSap == proceso.IdMatrizSap,
                sroa.Desde != '',
                sroa.IdSapRol.in_(roles_ids)
            )
        )
    )

    CampoValores_Extra_General = session.execute(stmt_extra).mappings().all()

    # -----------------------------------------------------------
    # 6. PerfilesAutorizaciones General (1 sola vez)
    # -----------------------------------------------------------
    sup = aliased(SapUsuarioPerfil)
    spoa = aliased(SapPerfilObjetoAutorizacion)

    stmt_perfiles_aut = (
        select(
            sup.IdUsuario.label("id_usuario"),
            sup.IdSapPerfil.label("id_perfil"),
            spoa.IdSapAutorizacion.label("id_autorizacion"),
            sroa.IdSapRol.label("id_rol"),
            sopr.Nombre.label("nombre_objeto")
        )
        .join(spoa, spoa.IdSapPerfil == sup.IdSapPerfil)
        .outerjoin(sroa, sroa.IdSapAutorizacion == spoa.IdSapAutorizacion)
        .join(sopr, sopr.Id == spoa.IdSapObjetoProceso)
        .where(
            and_(
                sup.IdMatrizSap == proceso.IdMatrizSap,
                sup.IdUsuario.in_(all_users),
            )
        )
        .distinct()
    )

    perfiles_rows = session.execute(stmt_perfiles_aut).mappings().all()

    perfiles_by_user = defaultdict(list)
    autorizaciones_ids_by_user = defaultdict(set)

    for r in perfiles_rows:
        perfiles_by_user[r["id_usuario"]].append(r)
        if r["id_autorizacion"]:
            autorizaciones_ids_by_user[r["id_usuario"]].add(r["id_autorizacion"])

    return {
        "sap_objeto_campos_index": sap_objeto_campos_index,
        "SapObjetoCampos_General": sap_objeto_campos_index_v2,
        "roles_by_user": roles_by_user,
        "roles_ids_by_user": roles_ids_by_user,
        "RolCampoValoresIndex": RolCampoValoresIndex,
        "AddCampoValoresIndex": AddCampoValoresIndex,
        "CampoValores_Extra_General": CampoValores_Extra_General,
        "perfiles_by_user": perfiles_by_user,
        "autorizaciones_ids_by_user": autorizaciones_ids_by_user,
        "objetos_unicos": objetos_unicos,
        "campos_unicos": campos_unicos,
        "roles_por_transaccion": RolesByTransactionIndex
    }

def parse_limit_date(value: str | None) -> datetime:
    """
    Convierte un string a datetime en timezone Lima.
    Si value es None → devuelve datetime.now(Lima).
    Si el formato no coincide → levanta ValueError.
    """
    if not value:
        return datetime.now(TZ_LIMA)

    # Si viene como: "2026-03-27 00:00:00"
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=TZ_LIMA)
    except ValueError:
        pass

    # Si viene como "2026-03-27"
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.replace(tzinfo=TZ_LIMA)
    except ValueError:
        pass

    raise ValueError(f"Formato de fecha inválido: {value}")

if __name__ == "__main__":   
    main()

