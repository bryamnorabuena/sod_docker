from collections import defaultdict
from datetime import datetime, timedelta, timezone
import os, sys, json, requests, io, time, csv
import uuid


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from models.job import Job
from models.campo import Campo
from models.conflicto import Conflicto
from models.usuario import Usuario
from models.riesgo import Riesgo
from models.actividad import Actividad
from models.transaccion import Transaccion
from models.saprol import SapRol
from models.sapperfil import SapPerfil
from models.sapautorizacion import SapAutorizacion
from models.sapusuariotipo import SapUsuarioTipo
from models.proceso import Proceso
from models.sapusuario import SapUsuario
from models.version import Version

from azure.storage.blob import BlobServiceClient
from utils import storage

from db.database import SessionLocal, engine



from sqlalchemy import func, or_, select, distinct, and_, union_all
from sqlalchemy.orm import aliased


def get_general_report():
    raw = os.getenv("INPUT_JSON")  # El Job recibe un JSON con toda la info, pero aquí nos enfocamos en lo esencial
    data = json.loads(raw)
    job_id = data.get("id_job") or uuid.uuid4().hex

    TZ_LIMA = timezone(timedelta(hours=-5))
    now = datetime.now(TZ_LIMA)

    idversion = data.get("id_version")
    if not idversion:
        raise ValueError("No se ingresó la versión")
    
    iduser = data.get("id_user")
    if not iduser:
        raise ValueError("No se ingresó el usuario de acción")
    
    typereport = data.get("type")
    if not typereport:
        raise ValueError("No se ingresó el tipo de reporte")

    try:        
        data_reporte = []

        with SessionLocal() as conn:                        
            idversion = data.get("id_version")
            if not idversion:
                raise ValueError("No se ingresó la versión")

            version = conn.get(Version, idversion)
            if not version:
                raise ValueError("No existe la versión")
            
            proceso = conn.get(Proceso, version.IdProceso)
            if not proceso:
                raise ValueError("No existe el proceso de la versión")   

            cae = aliased(Campo)  # empresa del usuario
            tu  = aliased(Campo)  # tipo_usuario
            pr  = aliased(Campo)  # proceso_riesgo
            nr  = aliased(Campo)  # nivel_riesgo  
            U = aliased(Usuario)
            SU = aliased(SapUsuario)
            SUT = aliased(SapUsuarioTipo)

            # 0) Subconsulta usuarios Dialogo y Servicio
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
                conn.query(
                    U.Id,U.Usuario
                )
                .join(SU, U.Id == SU.IdUsuario)
                .join(SUT, SUT.IdUsuario == U.Id)
                .filter(SU.IdMatrizSap == proceso.IdMatrizSap, SUT.IdTipoUsuario.in_(union_ids))
                .distinct()
                .all()
            )

            users_dialog_service = [v.Id for v in stmt]   

            storage.update_progress(job_id, 20)   

            # 1) Subconsulta con DISTINCT temprano SOLO sobre conflicto
            
            stmt = (
                select(
                    Conflicto.IdUsuario.label("id_usuario"),
                    Conflicto.IdRiesgo.label("id_riesgo"),
                    Conflicto.IdActividad.label("id_actividad"),
                    Transaccion.Codigo.label("transaccion"),
                    Campo.Nombre.label("sistema")
                )
                .select_from(Conflicto)
                .join(Transaccion, Conflicto.IdTransaccion == Transaccion.Id)
                .join(Campo, Transaccion.IdSistema == Campo.Id)
                .filter(Conflicto.IdVersion == idversion)
                .distinct()  # DISTINCT sobre las columnas del SELECT
            )

            transactions_per_risk = defaultdict(list)

            
            for row in conn.execute(stmt).mappings():
                key = (row["id_usuario"], row["id_riesgo"], row["id_actividad"])
                trx = row["transaccion"] + f" ({row['sistema']})"
                transactions_per_risk[key].append(trx)

            storage.update_progress(job_id, 40)

            # 2) Get Reporte General

            
            subq = (
                select(
                    Conflicto.Id.label("conflicto_id"),
                    Conflicto.IdUsuario,
                    Usuario.Usuario.label("usuario"),
                    tu.Nombre.label("tipo_usuario"),
                    pr.Nombre.label("proceso_riesgo"),
                    Conflicto.IdRiesgo,
                    Riesgo.Codigo.label("riesgo"),
                    Riesgo.Descripcion.label("descripcion"),
                    Conflicto.IdActividad,
                    Actividad.Codigo.label("actividad"),
                    nr.Nombre.label("nivel_riesgo"),
                )
                .select_from(Conflicto)  # FROM conflicto_v2 (mapeado por el modelo Conflicto)
                # JOINS
                .join(Usuario, and_(Conflicto.IdUsuario == Usuario.Id, Usuario.Id.in_(users_dialog_service)))
                .outerjoin(SapPerfil, Conflicto.IdSapPerfil == SapPerfil.Id)
                .outerjoin(SapAutorizacion, Conflicto.IdSapAutorizacion == SapAutorizacion.Id)
                .join(SapRol, Conflicto.IdSapRol == SapRol.Id)
                .join(cae, Usuario.IdEmpresa == cae.Id)
                .join(Riesgo, Conflicto.IdRiesgo == Riesgo.Id)
                .join(Actividad, Conflicto.IdActividad == Actividad.Id)
                .join(Transaccion, Conflicto.IdTransaccion == Transaccion.Id)
                .join(SapUsuarioTipo, Conflicto.IdUsuario == SapUsuarioTipo.IdUsuario)
                .join(tu, SapUsuarioTipo.IdTipoUsuario == tu.Id)
                .join(pr, Riesgo.IdProcesoRiesgo == pr.Id)
                .join(nr, Riesgo.IdNivelRiesgo == nr.Id)
                .filter(Conflicto.IdVersion == idversion)
                .order_by(Usuario.Usuario.asc(), Conflicto.Id.desc())
            ).subquery()

            
            stmt = (
                select(
                    subq.c.IdUsuario,
                    subq.c.usuario,
                    subq.c.tipo_usuario,
                    subq.c.proceso_riesgo,
                    subq.c.IdRiesgo,
                    subq.c.riesgo,
                    subq.c.descripcion,
                    subq.c.IdActividad,
                    subq.c.actividad,
                    subq.c.nivel_riesgo,
                )
                .distinct()
            )



            # stmt = (
            #     select(
            #         Conflicto.IdUsuario,
            #         Usuario.Usuario.label("usuario"),
            #         tu.Nombre.label("tipo_usuario"),
            #         pr.Nombre.label("proceso_riesgo"),
            #         Conflicto.IdRiesgo,
            #         Riesgo.Codigo.label("riesgo"),
            #         Riesgo.Descripcion.label("descripcion"),
            #         Conflicto.IdActividad,
            #         Actividad.Codigo.label("actividad"),
            #         nr.Nombre.label("nivel_riesgo"),
            #     )
            #     .select_from(Conflicto)  # FROM conflicto_v2 (mapeado por el modelo Conflicto)
            #     # JOINS
            #     .join(Usuario, and_(Conflicto.IdUsuario == Usuario.Id, Usuario.Id.in_(users_dialog_service)))
            #     .outerjoin(SapPerfil, Conflicto.IdSapPerfil == SapPerfil.Id)
            #     .outerjoin(SapAutorizacion, Conflicto.IdSapAutorizacion == SapAutorizacion.Id)
            #     .join(SapRol, Conflicto.IdSapRol == SapRol.Id)
            #     .join(cae, Usuario.IdEmpresa == cae.Id)
            #     .join(Riesgo, Conflicto.IdRiesgo == Riesgo.Id)
            #     .join(Actividad, Conflicto.IdActividad == Actividad.Id)
            #     .join(Transaccion, Conflicto.IdTransaccion == Transaccion.Id)
            #     .join(SapUsuarioTipo, Conflicto.IdUsuario == SapUsuarioTipo.IdUsuario)
            #     .join(tu, SapUsuarioTipo.IdTipoUsuario == tu.Id)
            #     .join(pr, Riesgo.IdProcesoRiesgo == pr.Id)
            #     .join(nr, Riesgo.IdNivelRiesgo == nr.Id)
            #     .filter(Conflicto.IdVersion == idversion)
            #     .distinct()                
            #     .order_by(Usuario.Usuario.asc(),Conflicto.Id.asc())
            # )

            data_reporte = []
            merged = {}

            storage.update_progress(job_id, 60)

            for row in conn.execute(stmt).mappings():
                key = (row.IdUsuario, row.IdRiesgo)

                transactions = transactions_per_risk.get((row.IdUsuario, row.IdRiesgo, row.IdActividad), set())
                tx_str = ",".join(sorted(transactions)) if transactions else ""

                if key not in merged:                    
                    merged[key] = {
                        "usuario": row.usuario,
                        "tipo_usuario": row.tipo_usuario,
                        "proceso_riesgo": row.proceso_riesgo,
                        "riesgo": row.riesgo,
                        "descripcion": row.descripcion,
                        "actividad": row.actividad,
                        "transaccion": tx_str,   # actividad principal
                        "nivel_riesgo": row.nivel_riesgo,
                        "actividad2": "",
                        "transaccion2": "",
                    }
                else:                    
                    if not merged[key]["actividad2"]:
                        merged[key]["actividad2"] = row.actividad
                        merged[key]["transaccion2"] = tx_str
                    else:
                        pass

            data_reporte = list(merged.values())

        # 3) Ejecutar en streaming (CORE): sin cargar todo en memoria
        
        # Crear carpeta temporal
        os.makedirs("./tmp", exist_ok=True)

        # ID único del job (si no viene desde INPUT_JSON)        
        idversion = data.get("id_version")

        timestamp = now.strftime("%Y%m%d_%H%M%S")

        # ✅ Nombre único del archivo temporal
        output_path = f"./tmp/report_{job_id}_{idversion}_{timestamp}.csv"

        fieldnames = [
            "usuario", "tipo_usuario", "proceso_riesgo",
            "riesgo", "descripcion",
            "actividad", "transaccion",
            "actividad2", "transaccion2",
            "nivel_riesgo"
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data_reporte)

        print(f"Reporte CSV generado: {output_path} (filas: {len(data_reporte)})")

        storage.update_progress(job_id, 95)

        # 1 = General, 2 = Detallado
        tipo_reporte = data.get("type", 1)

        # Subir a blob y borrar temporal
        download_url = storage.upload_to_blob(output_path, tipo_reporte, version)

        with SessionLocal() as db:
            job = db.query(Job).filter(Job.IdJob == job_id).first()
            if not job:
                raise ValueError("El Job no existe")

            job.UrlReporte = download_url
            job.FechaActualizacion = now

            db.commit()

        storage.complete_job(job_id)
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        message = f"Error en get_general_report: {str(e)} (File: {fname}, Line: {exc_tb.tb_lineno})"
        print(message)
        storage.update_job_with_errors(data.get("id_job"),[message])

        raise

if __name__ == "__main__":
    get_general_report()