import os, sys, json, requests, io, time
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

import numpy as np

from fnmatch import fnmatch
from collections import defaultdict
from models.sapcampoproceso import SapCampoProceso
from models.sapobjetoproceso import SapObjetoProceso
from models.saprolobjetoautorizacion import SapRolObjetoAutorizacion
from models.sapusuariorol import SapUsuarioRol
from utils.helper import Helper
from sqlalchemy import and_, desc, insert, select
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

# Este Lock es global para EL CONTENEDOR. 
# Si otro análisis corre en el mismo contenedor, respetará este semáforo.
lock_pesados = Lock()
comodin = '*'

def worker_pesado(usuario_id, id_version, id_job, id_user, all_users, idx_shard):
    """Maneja la fila de usuarios pesados."""
    print(f"--- Usuario Pesado {usuario_id} en espera de turno ---")
    with lock_pesados:
        # Solo un usuario pesado entra aquí a la vez
        print(f"--- Iniciando procesamiento de Pesado: {usuario_id} ---")
        return process_execute([usuario_id], id_version, id_job, id_user, len(all_users), idx_shard)
    
def clasificar_usuario(session, id_usuario, proceso):
    """Cuenta los registros asociados a un usuario para clasificarlo."""
    sur = aliased(SapUsuarioRol)
    sopr = aliased(SapObjetoProceso)
    scpr = aliased(SapCampoProceso)
    sroa = aliased(SapRolObjetoAutorizacion)

    stmt = (
        select(sur.IdSapRol).where(sur.IdUsuario == id_usuario).distinct()
    )    
    rows = session.execute(stmt).mappings().all()
    roles_usuario = [x["IdSapRol"] for x in rows]
    
    # Aquí va la lógica de conteo que vimos en la foto
    stmt = (
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
                sroa.IdSapRol.in_(roles_usuario),
                sroa.Desde != ''
            )
        )
        .order_by(sroa.Desde)
    )
    conteo = session.execute(stmt).mappings().count()
    
    return conteo

def main():
    raw = os.getenv("INPUT_JSON")  # El Job recibe un JSON con toda la info, pero aquí nos enfocamos en lo esencial
    data = json.loads(raw)

    id_job = data["id_job"]
    id_version = data["id_version"]
    id_user = data["id_user"]

    # 1. Identificación Inicial (Discriminador)
    # Hacemos un pre-check rápido de cuántos registros tiene cada uno
    pesados = []
    livianos = []
    
    session = SessionLocal()
    version = session.get(Version, id_version)
    
    if version is None:
        print(f"Error: No se encontró la versión con id {id_version}")
        storage.update_job_with_errors(id_job, [f"No se encontró la versión con id {id_version}"])
        session.close()
        return
    
    proceso = session.get(Proceso, version.IdProceso)

    if version.Completo:     
        # Lista real de usuarios
        now_dt = datetime.now()
        all_users = [
            uid for (uid,) in session.query(
                    UsuarioTransaccion.IdUsuario
                ).join(SapUsuario, and_(SapUsuario.IdUsuario == UsuarioTransaccion.IdUsuario, SapUsuario.IdMatrizSap == proceso.IdMatrizSap)
                ).filter(and_(UsuarioTransaccion.IdProceso == proceso.Id,
                    SapUsuario.FechaInicio <= now_dt,
                    SapUsuario.FechaFin >= now_dt,
                    SapUsuario.Uflag.in_([0,128]))
                    ).group_by(UsuarioTransaccion.IdUsuario
                    ).order_by(UsuarioTransaccion.IdUsuario).distinct().all()
        ]
    else:
        all_users = [
            uid for (uid,) in session.query(
                VersionUsuario.IdUsuario
                ).filter(VersionUsuario.IdVersion == version.Id
            ).distinct().all()
        ]
        session.close()

    for u_id in all_users:
      # Tu lógica de conteo que vimos en la foto
      conteo = clasificar_usuario(session, u_id, proceso)
      if conteo > 100000: # Umbral de "Usuario de Sistema"
          pesados.append(u_id)
      else:
          livianos.append(u_id)

    print(f"Clasificación terminada: {len(livianos)} livianos, {len(pesados)} pesados.")

    # 2. LANZAMIENTO DE LIVIANOS (Carril Rápido - 3 CPUs)
    num_cpus_pool = min(len(livianos), 3)

    shards_livianos = np.array_split(livianos, num_cpus_pool) if len(livianos) > 0 else []
    idx_shard = 0
    args_livianos = [(list(shard), id_version, id_job, id_user,len(all_users),idx_shard:=idx_shard+1)  for shard in shards_livianos]
    
    with Pool(processes=3) as pool:
        # Ejecutan en paralelo sin bloquearse entre ellos
        pool.starmap(process_execute, args_livianos)

    # 3. LANZAMIENTO DE PESADOS (Carril Controlado - 1 CPU a la vez)
    # Los procesamos uno por uno para proteger los 8GB de RAM
    for p_id in pesados:
        worker_pesado(p_id, id_version, id_job, id_user, len(all_users), idx_shard)


def prefetch_data_user(session, IdUsuario, proceso):
    time_start = time.perf_counter()

    sup = aliased(SapUsuarioPerfil)    
    soc = aliased(sapobjetocampo)
    t = aliased(transaccion)
    so = aliased(SapObjeto)
    sc = aliased(SapCampo)
    sopr = aliased(sapobjetoproceso)
    scpr = aliased(sapcampoproceso)
    sup = aliased(SapUsuarioPerfil)
    spoa = aliased(SapPerfilObjetoAutorizacion)
    sroa = aliased(SapRolObjetoAutorizacion)
    sur = aliased(SapUsuarioRol)
    soa = aliased(SapObjetoAutorizacion)
    sno = aliased(SapNivelOrganizacional)
    
     # GET INFORMATION GROUP BY PERFIL -- ALL PERFIL
    stmt = (
        select(
            sup.IdSapPerfil.label("id_perfil")
        )
        .where(and_(sup.IdMatrizSap == proceso.IdMatrizSap, sup.IdUsuario == IdUsuario))
        .group_by(sup.IdSapPerfil)
        .order_by(sup.IdSapPerfil)
    )
    SapPerfilesUsuario = session.execute(stmt).mappings().all()  

    stmt = (
        select(
        sur.IdSapRol.label("id_rol"),
        sur.IdUsuario.label("id_usuario"),
        sur.FechaInicio.label("fechainicio"),
        sur.FechaFin.label("fechafin")                                    
        )
        .where(and_(sur.IdMatrizSap == proceso.IdMatrizSap,
        sur.IdUsuario == IdUsuario,
        sur.Estado == 1))
        .order_by(desc(sur.IdSapRol))
        )
    DatoRoles_General = session.execute(stmt).mappings().all()                      

    stmt = (
        select(sur.IdSapRol).where(sur.IdUsuario == IdUsuario).distinct()
    )    
    rows = session.execute(stmt).mappings().all()
    roles_usuario = [x["IdSapRol"] for x in rows]

    stmt = (
        select(sroa.IdSapObjetoProceso.label("id_objeto"),
            sroa.IdSapCampoProceso.label("id_campo"),
            sroa.Desde.label("desde"),
            sroa.Hasta.label("hasta"),
            sroa.IdSapRol.label("id_rol"),
            sopr.Nombre.label("objeto"),
            scpr.Nombre.label("campo"))
        .join(sopr, sroa.IdSapObjetoProceso == sopr.Id)
        .join(scpr, sroa.IdSapCampoProceso == scpr.Id)
        .where(and_(sroa.IdMatrizSap == proceso.IdMatrizSap,
            sroa.IdSapRol.in_(roles_usuario),
            sroa.Desde != '')
            )
        .order_by(sroa.Desde)
    )
    RolCampoValores_General = session.execute(stmt).mappings().all()

    stmt = (
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
                sroa.IdSapRol.in_(roles_usuario),
                sroa.Desde != ''
            )
        )
        .order_by(sroa.Desde)
    )
    CampoValores_Extra_General = session.execute(stmt).mappings().all()

    time_end = time.perf_counter()
    totalTime = time_end - time_start
    print(f"Tiempo Carga Datos Usuario con Id {IdUsuario}: {totalTime:.2f} segundos")

    return SapPerfilesUsuario, DatoRoles_General, roles_usuario, RolCampoValores_General, CampoValores_Extra_General

def FindObjectAuthorizationByPerfil_optimized(
    session,
    SapNivelOrganizacionales,
    IdMatrizSap,
    IdRegla,
    IdUsuario,
    aActividades,
    aActividadesFiori,
    RolesExtras,
    AutorizacionesExtras,
    CamposOrganizacionales,
    cache
    ):

    try:
    
        now_ts = int(datetime.now().timestamp())    
        
        max_date_sap = config.MAX_DATE_SAP
        max_date_php = config.MAX_DATE_PHP

        aResultPerfiles = {}
        aPerfilAutorizacionesObjetoCampo = {}

        sup = aliased(SapUsuarioPerfil)    
        soc = aliased(sapobjetocampo)
        t = aliased(transaccion)
        so = aliased(SapObjeto)
        sc = aliased(SapCampo)
        sopr = aliased(sapobjetoproceso)
        scpr = aliased(sapcampoproceso)
        sup = aliased(SapUsuarioPerfil)
        spoa = aliased(SapPerfilObjetoAutorizacion)
        sroa = aliased(SapRolObjetoAutorizacion)
        sur = aliased(SapUsuarioRol)
        soa = aliased(SapObjetoAutorizacion)
        sno = aliased(SapNivelOrganizacional)    

        SapPerfilesUsuario = cache["SapPerfilesUsuario"]
        DatoRoles_General = cache["DatoRoles_General"]
        AddCampoValores_General = cache["AddCampoValores_General"]
        RolCampoValores_General = cache["RolCampoValores_General"]
        SapObjetoProceso_General = cache["SapObjetoProceso_General"]
        SapCampoProceso_General = cache["SapCampoProceso_General"]
        CampoValores_Extra_General = cache["CampoValores_Extra_General"]
        
            
        aPerfilesId = []
        for SapPerfilUsuario in SapPerfilesUsuario:
            aPerfilesId.append(SapPerfilUsuario["id_perfil"])

        aResultPerfiles = {"CONDITION": False, "Actividad": {}}

        for IdActividad, aTransacciones in aActividades.items():        
            #joined = ",".join(str(entry) for entry in aTransacciones["TRANSACCIONES"])
            #aIdTransacciones = list(map(int, joined.split(","))) if joined else []
            aIdTransacciones = aTransacciones["TRANSACCIONES"]

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
            # get_active_by_regla_actividad_transaccion        

            stmt =(
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
                ).join(t, t.Id == soc.IdTransaccion)
                .join(so, so.Id == soc.IdSapObjeto)
                .join(sc, sc.Id == soc.IdSapCampo)
                .where(and_(soc.IdRegla == IdRegla,soc.IdActividad == IdActividad,
                    soc.IdTransaccion.in_(aIdTransacciones)))
                .order_by(soc.IdTransaccion,soc.IdSapObjeto,soc.IdSapCampo)
                .distinct()
            )
            SapObjetoCampos = session.execute(stmt).mappings().all()

            obj_lista = list(dict.fromkeys([x["nombre_objeto"] for x in SapObjetoCampos]))
            cam_lista = list(dict.fromkeys([x["nombre_campo"] for x in SapObjetoCampos]))

            subq_objetos = (
                select(so.Nombre)
                .join(soc, soc.IdSapObjeto == so.Id)
                .join(t, t.Id == soc.IdTransaccion)
                .where(
                    and_(
                        soc.IdRegla == IdRegla,
                        soc.IdActividad == IdActividad,
                        soc.IdTransaccion.in_(aIdTransacciones),
                    )
                )
                .distinct()
            )
            Objetos_Lista = session.execute(subq_objetos).scalars().all()

            stmt = (
                select(
                    sup.IdSapPerfil.label("id_perfil"),
                    spoa.IdSapAutorizacion.label("id_autorizacion"),
                    sroa.IdSapRol.label("id_rol"),
                    sopr.Nombre.label("nombre_objeto"),
                )
                .select_from(sup)
                .join(spoa, spoa.IdSapPerfil == sup.IdSapPerfil)
                .outerjoin(sroa, sroa.IdSapAutorizacion == spoa.IdSapAutorizacion)
                .join(sopr, sopr.Id == spoa.IdSapObjetoProceso)
                .where(
                    and_(
                        sup.IdMatrizSap == IdMatrizSap,
                        sup.IdUsuario == IdUsuario,
                        sopr.Nombre.in_(Objetos_Lista)
                    )
                )            
                .order_by(sup.IdSapPerfil)
                .distinct()
            )
            result_aux = session.execute(stmt).mappings().all()  
            
            SapPerfilesAutorizaciones_activity = defaultdict(list) 
            aut_lista = list(dict.fromkeys([x["id_autorizacion"] for x in result_aux]))

            for row in result_aux:
                SapPerfilesAutorizaciones_activity[row["nombre_objeto"]].append(row)

            stmt = (
                select(
                    soa.IdSapAutorizacion.label("id_autorizacion"),
                    sopr.Nombre.label("objeto"),
                    scpr.Nombre.label("campo"),
                    soa.IdSapObjetoProceso.label("id_objeto"),
                    soa.IdSapCampoProceso.label("id_campo"),
                    soa.Desde.label("desde"),
                    soa.Hasta.label("hasta"))
                .join(sopr, soa.IdSapObjetoProceso == sopr.Id)
                .join(scpr, soa.IdSapCampoProceso == scpr.Id)
                .where(and_(soa.IdMatrizSap == IdMatrizSap,
                    soa.IdSapAutorizacion.in_(aut_lista),
                    sopr.Nombre.in_(obj_lista),
                    scpr.Nombre.in_(cam_lista),
                    soa.Desde != '',
                    soa.Estado == 1))
                .order_by(soa.Desde)                                            
            )
            CampoValores_General = session.execute(stmt).mappings().all() 

            cache["CampoValoresPorAutorizacion"] = defaultdict(dict)

            for row in CampoValores_General:
                cache["CampoValoresPorAutorizacion"][ row["id_autorizacion"] ] \
                                            .setdefault(row["objeto"], {}) \
                                            .setdefault(row["campo"], []) \
                                            .append(row)

            
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
                                # get_active_by_proceso_nombre_objeto                  
                                SapObjetoProceso = [x for x in SapObjetoProceso_General if x["nombre"] == Objeto]

                                if SapObjetoProceso:
                                    IdSapObjetoProcesoOFRisk = SapObjetoProceso[0]["id"]

                                SapCampoProceso = [x for x in SapCampoProceso_General if x["nombre"] == Campo]

                                if SapCampoProceso:
                                    IdSapCampoProcesoOFRisk = SapCampoProceso[0]["id"]

                            BolCampo = False                                                
                            
                            for ObjetoSap, SapPerfilesAutorizaciones in SapPerfilesAutorizaciones_activity.items():
                                if ObjetoSap != Objeto:
                                    continue                            

                                # Añadir RolesExtras cuando no existan
                                RolesExtrasNew = []
                                if len(RolesExtras) > 0:
                                    for RolExtra in RolesExtras:
                                        exists = [Obj for Obj in SapPerfilesAutorizaciones if Obj.get("id_rol") == RolExtra]
                                        if len(exists) == 0:
                                            for SapPerfilesAutorizacion in SapPerfilesAutorizaciones:
                                                RolesExtrasNew.append(
                                                    {
                                                        "id_perfil": SapPerfilesAutorizacion["id_perfil"],
                                                        "id_autorizacion": SapPerfilesAutorizacion["id_autorizacion"],
                                                        "id_rol": RolExtra,
                                                        "extra": True,
                                                    }
                                                )
                                if len(RolesExtrasNew) > 0:
                                    for RolExtraNew in RolesExtrasNew:
                                        SapPerfilesAutorizaciones.append(RolExtraNew)

                                # HOME AUTORIZACIONES
                                for SapPerfilesAutorizacion in SapPerfilesAutorizaciones:
                                    IdPerfil = SapPerfilesAutorizacion["id_perfil"]
                                    IdSapAutorizacion = SapPerfilesAutorizacion["id_autorizacion"]
                                    BolRol = True
                                    isExtra = ("extra" in SapPerfilesAutorizacion)

                                    if SapPerfilesAutorizacion.get("id_rol") and not isExtra:
                                        #get_active_group_usuario_rol_by_proceso_usuario_rol
                                        DatoRoles = [x for x in DatoRoles_General if x.id_rol == SapPerfilesAutorizacion["id_rol"]]

                                        if len(DatoRoles) > 0:
                                            for DatoRol in DatoRoles:
                                                # En PHP se toma strtotime(fecha->format('Y-m-d H:i:s'))
                                                FechaInicio = int(DatoRol["fechainicio"].replace(tzinfo=timezone.utc).timestamp())
                                                FechaFin = int(DatoRol["fechafin"].replace(tzinfo=timezone.utc).timestamp())
                                                max_date = int(datetime.strptime(max_date_sap, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())

                                                if FechaFin == max_date:
                                                    # Emular: $FechaFin = strtotime($max_date_php);
                                                    if isinstance(max_date_php, str):
                                                        # permitir string 'YYYY-mm-dd HH:MM:SS'
                                                        FechaFin = int(datetime.fromisoformat(max_date_php).timestamp())
                                                    else:
                                                        FechaFin = int(max_date_php)

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
                                                    AddCampoValores = cache["AddCampoValores_General"].get(f"${Campo}", {}).get(IdSapRol, [])
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
                                                    aPerfilAutorizacionesObjetoCampo \
                                                        .setdefault(IdPerfil, {}) \
                                                        .setdefault(IdSapAutorizacion, {}) \
                                                        .setdefault(Objeto, {}) \
                                                        .setdefault(Campo, []) \
                                                        .append(
                                                            {
                                                                "ID_OBJETO": AutorizacionesExtra["id_objeto"],
                                                                "ID_CAMPO": AutorizacionesExtra["id_campo"],
                                                                "DESDE": AutorizacionesExtra["desde"],
                                                                "HASTA": AutorizacionesExtra["hasta"],
                                                                "EXTRA": True,
                                                            }
                                                        )
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

                                                    Results = Helper.BolCampoFindObjectAuthorization(
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
                        cantidad_campos = len(Campos["CAMPOS"])

                        Autorizaciones = {}
                        AutorizacionesValidas = []
                        AutorizacionesInvalidas = []

                        for Campo2, Valores2 in Campos["CAMPOS"].items():
                            condicion = aObjetosCampos[Transaccion]["OBJETOS"][Objeto]["CAMPOS"][Campo2]["CONDITION"]
                            if condicion:
                                oAutorizaciones = aObjetosCampos[Transaccion]["OBJETOS"][Objeto]["CAMPOS"][Campo2].get("AUTORIZACION", [])
                                for oAutorizacion in oAutorizaciones:
                                    Autorizaciones[oAutorizacion["ID"]] = oAutorizacion["ID"]

                        for Autorizacion in Autorizaciones.values():
                            IntAutorizacion = 0
                            for Campo2, Valores2 in Campos["CAMPOS"].items():
                                condicion = aObjetosCampos[Transaccion]["OBJETOS"][Objeto]["CAMPOS"][Campo2]["CONDITION"]
                                if condicion:
                                    rAutorizaciones = aObjetosCampos[Transaccion]["OBJETOS"][Objeto]["CAMPOS"][Campo2].get("AUTORIZACION", [])
                                    cantidad = [x for x in rAutorizaciones if x["ID"] == Autorizacion]
                                    if len(cantidad) > 0:
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
                                    # eliminar los que coinciden
                                    to_del = []
                                    for idx, ObjaResultPerfil in enumerate(arr):
                                        if (
                                            ObjaResultPerfil["IdTransaccion"] == Transaccion
                                            and ObjaResultPerfil["IdSapAutorizacion"] == AutorizacionesInvalida
                                            and ObjaResultPerfil["Objeto"] == Objeto
                                        ):
                                            to_del.append(idx)
                                    for idx in reversed(to_del):
                                        del aResultPerfiles["Actividad"][IdActividad]["TransaccionPerfiles"][Transaccion][idx]

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
    
def process_execute(only_user_ids,id_version, job_id, user_id, total_users, idx_shard):
    # ⚙️ Inicio de transacción y tiempo
    if len(only_user_ids) == 0:
        return
    
    time_start = time.perf_counter()
    TZ_LIMA = time.timezone(timedelta(hours=-5))
    now_dt = datetime.now(TZ_LIMA)
    conflictosLista = []
    limiteConflicto = 3000
    IntBatch  = 0
    IntUsuario = 0
    batchConflicto = 0
    progress = 0    
    # En SQLAlchemy, desactivar logs de SQL se hace a nivel de engine/logger (no por conexión como Doctrine)

    print(f"Inicio de Análisis: {str(time_start)}")
    progress += 5
    print(f"Avance: {progress}%")
    #storage.update_progress(job_id, progress)

    try:
        session = SessionLocal()
        
        myuser = session.get(AppUser, user_id)

        # Version y Proceso
        version = session.get(Version, id_version)
        proceso = session.get(Proceso, version.IdProceso)

        # Campos & Nivel organizacional
        Campos = ["$BUKRS", "$WERKS"]

        sup = aliased(SapUsuarioPerfil)    
        soc = aliased(sapobjetocampo)
        t = aliased(transaccion)
        so = aliased(SapObjeto)
        sc = aliased(SapCampo)
        sopr = aliased(sapobjetoproceso)
        scpr = aliased(sapcampoproceso)
        sup = aliased(SapUsuarioPerfil)
        spoa = aliased(SapPerfilObjetoAutorizacion)
        sroa = aliased(SapRolObjetoAutorizacion)
        sur = aliased(SapUsuarioRol)
        soa = aliased(SapObjetoAutorizacion)
        sno = aliased(SapNivelOrganizacional)
        
        #VALIDADO
        SapNivelOrganizacionales = session.query(SapNivelOrganizacional.IdSapRol.label("id_rol"),
                                                    SapNivelOrganizacional.NivelOrganizacional.label("nivelorganizacional"),
                                                    SapNivelOrganizacional.Desde.label("desde"),
                                                    SapNivelOrganizacional.Hasta.label("hasta")).filter(
                                                        SapNivelOrganizacional.IdMatrizSap == proceso.IdMatrizSap,
                                                        SapNivelOrganizacional.NivelOrganizacional.in_(Campos),
                                                        SapNivelOrganizacional.Desde != '').order_by(SapNivelOrganizacional.Desde).all()
        
        #VALIDADO
        CamposOrganizacionales = session.query(SapCampoOrganizacional).filter(SapCampoOrganizacional.IdMatrizSap == proceso.IdMatrizSap).all() 

        CamposOrganizacionalesIndex = defaultdict(list)
        for obj in CamposOrganizacionales:
            CamposOrganizacionalesIndex[obj.Campo].append(obj) 
        
        CamposOrganizacionales = CamposOrganizacionalesIndex
                      
        # Riesgos y sus actividades
        IdRegla = proceso.IdRegla
        Riesgos = session.query(Riesgo).filter(Riesgo.IdRegla == IdRegla).order_by(desc(Riesgo.Id)).all()

        print(f"Cantidad de Riesgos: {len(Riesgos)}")

        RiesgosActividad = {}
        for riesgo in Riesgos:
            IdRiesgo = riesgo.Id
            RiesgoActividad = session.query(RiesgoActividadTransaccion
                                                ).filter(RiesgoActividadTransaccion.IdRiesgo == IdRiesgo
                                                            ).group_by(RiesgoActividadTransaccion.IdActividad
                                                                ).all()
            RiesgosActividad[IdRiesgo] = RiesgoActividad                

        # Parámetros
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

        Sistemas = config.SYSTEMS
        
        # Transacciones por regla/sistema con meta columnas (Doctrine hint emulado como simple consulta)
        TransaccionesRegla = session.query(Transaccion.Id.label("id"),Transaccion.Codigo.label("codigo"),Transaccion.Nombre.label("nombre")
                                            ).filter(Transaccion.IdRegla == IdRegla, Transaccion.IdSistema == IdSistemaSap,Transaccion.Codigo != '').all()
        

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
            .where(and_(
                sopr.IdMatrizSap == proceso.IdMatrizSap
                )                                    
            )
            .order_by(desc(sopr.Id))                                
        )
        SapObjetoProceso_General = session.execute(stmt).mappings().all()       

        stmt = (
            select(
                scpr.Id.label("id"),
                scpr.IdMatrizSap.label("idmatrizsap"),
                scpr.Nombre.label("nombre"),
                scpr.Descripcion.label("descripcion")
            )                                
            .where(
                and_(scpr.IdMatrizSap == proceso.IdMatrizSap)
            )
            .order_by(desc(scpr.Id))                                
        )
        SapCampoProceso_General = session.execute(stmt).mappings().all()

        # Colecciones extras (transacciones, roles, autorizaciones) cuando Version no es completa
        UsuariosTransaccionesExtras = {}
        UsuariosRolesExtras = {}
        UsuariosAutorizacionesExtras = {}

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
            Usuarios = session.query(UsuarioTransaccion).join(
                    SapUsuario, and_(SapUsuario.IdUsuario == UsuarioTransaccion.IdUsuario, SapUsuario.IdMatrizSap == proceso.IdMatrizSap)
                    ).filter(
                        UsuarioTransaccion.IdProceso == proceso.Id,
                        SapUsuario.FechaInicio <= datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        SapUsuario.FechaFin >= datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        SapUsuario.Uflag.in_([0,128]),
                        UsuarioTransaccion.IdUsuario.in_(UsuariosFilters),
                        UsuarioTransaccion.IdUsuario.in_(only_user_ids)
                    ).group_by(UsuarioTransaccion.IdUsuario).order_by(UsuarioTransaccion.Id).all()
        
        print(f"Usuarios a analizar: {len(Usuarios)}")

        progress_per_user = 70 / total_users if total_users > 0 else 0
        # --- Bucle principal por usuario ---
        for usuario in Usuarios:
          IntBatch += 1
          IntUsuario += 1

          progress += progress_per_user
          print(f"Avance en SHARD #{idx_shard}: {progress:.2f}% - Procesando usuario {IntUsuario}/{len(Usuarios)}")
          #storage.update_progress(job_id, progress)

          IdUsuario = usuario.IdUsuario

          print(f"Usuario en análisis: {str(IdUsuario)}")

          SapPerfilesUsuario, DatoRoles_General, roles_usuario, RolCampoValores_General, CampoValores_Extra_General = prefetch_data_user(session, IdUsuario, proceso)
          
          #TRATAMIENTO PARA RECUDIR RAM
          
          AddCampoValoresIndex = defaultdict(lambda: defaultdict(list))
          for row in AddCampoValores_General:
              AddCampoValoresIndex[row["nivel_organizacional"]][row["id_rol"]].append(row)

          RolCampoValoresIndex = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
          for row in RolCampoValores_General:
              RolCampoValoresIndex[row["id_rol"]][row["objeto"]][row["campo"]].append(row)

          cache = {}
          cache["AddCampoValores_General"] = AddCampoValoresIndex
          cache["SapPerfilesUsuario"] = SapPerfilesUsuario
          cache["DatoRoles_General"] = DatoRoles_General
          cache["RolCampoValores_General"] = RolCampoValoresIndex
          cache["roles_usuario"] = roles_usuario
          cache["CampoValores_Extra_General"] = CampoValores_Extra_General
          cache["SapObjetoProceso_General"] = SapObjetoProceso_General
          cache["SapCampoProceso_General"] = SapCampoProceso_General

          TransaccionesUsuario = session.query(UsuarioTransaccion).where(and_(UsuarioTransaccion.IdProceso == proceso.Id, UsuarioTransaccion.IdUsuario == IdUsuario, UsuarioTransaccion.Estado == 1)).order_by(UsuarioTransaccion.Id).all()

          aTransaccionesUsuario = []
          for tu in TransaccionesUsuario:
              aTransaccionesUsuario.append(tu.IdTransaccion)

          # Agregar extras por usuario (transacciones derivadas)
          if IdUsuario in UsuariosTransaccionesExtras:
              for tx_extra in UsuariosTransaccionesExtras[IdUsuario]:
                  aTransaccionesUsuario.append(tx_extra)

          # --- Evaluación por riesgo ---
          for riesgo in Riesgos:
              IdRiesgo = riesgo.Id

              TotalActividades = len(RiesgosActividad[IdRiesgo])
              IntActividad = 0
              Riesgoactividadtransacciones = []

              # Recolectar todas las RAT (riesgo-Actividad-Transacción) que el usuario cumple
              for Actividad in RiesgosActividad[IdRiesgo]:
                  IdActividad = Actividad.IdActividad
                  Registros = session.query(RiesgoActividadTransaccion).filter(
                          RiesgoActividadTransaccion.IdRiesgo == IdRiesgo,
                          RiesgoActividadTransaccion.IdActividad == IdActividad,
                          RiesgoActividadTransaccion.IdTransaccion.in_(aTransaccionesUsuario)
                      ).all()
                  for Registro in Registros:
                      Riesgoactividadtransacciones.append(Registro)
                  if len(Registros) > 0:
                      IntActividad += 1

              # Si cumple todas las actividades del riesgo
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

                      TransaccionObj = session.get(Transaccion, RAT.IdTransaccion)

                      if TransaccionObj.IdSistema == IdSistemaFiori:
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
                  aFind = FindObjectAuthorizationByPerfil_optimized(
                      session,
                      SapNivelOrganizacionales,
                      proceso.IdMatrizSap,
                      IdRegla,
                      IdUsuario,
                      aActividades,
                      aActividadesFiori,
                      UsuariosRolesExtras.get(IdUsuario, []),
                      UsuariosAutorizacionesExtras.get(IdUsuario, []),
                      CamposOrganizacionales,
                      cache
                  )

                  if aFind.get("CONDITION"):
                      # Por cada actividad/transacción detectada
                      print(f"Usuario {str(IdUsuario)} con conflictos")

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
                                                  "FechaCreacion": now_dt,
                                                  "FechaActualizacion": now_dt,
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
                                                      "FechaCreacion": now_dt,
                                                      "FechaActualizacion": now_dt,
                                                      "Estado": 1
                                                  }
                                              )

                                              batchConflicto += 1
                                              if batchConflicto == limiteConflicto:
                                                  session.execute(insert(Conflicto), conflictosLista)
                                                  session.commit()
                                                  conflictosLista.clear()

                                  if conflictosLista:
                                      session.execute(insert(Conflicto), conflictosLista)
                                      session.commit()
                                      conflictosLista.clear()
            
        session.flush()
        time_end = time.perf_counter()
        totalTime = time_end - time_start                        
        print(f"Fin de Análisis para SHARD #{idx_shard}: Tiempo total: {totalTime:.2f} segundos")        
        return True                
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        message = f"Exception en SHARD #{idx_shard} de la versión #{id_version}: {e} in {fname}:{exc_tb.tb_lineno}"
        print(message)


if __name__ == "__main__":   
    main()

