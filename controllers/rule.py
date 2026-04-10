from collections import defaultdict
from io import BytesIO
import time
import threading
import json
import base64
import tempfile
import sys
from flask import Blueprint, request, jsonify
from openpyxl import load_workbook
from sqlalchemy import and_, desc
from validator import rules
from repository.log_repository import LogRepository
from utils.customValidation import white_space_rule
from db.database import SessionLocal
from datetime import datetime, timedelta, timezone
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import aliased

from utils import storage
from services.nsg_service import *
from models import *

rule = Blueprint('rule', __name__)

comodin = "*"
DATE_FMT = "%Y-%m-%d %H:%M:%S"

rules_analize_conflicts = {
  'token': [rules.Required(), white_space_rule],
  'idVersion': [rules.Required(), rules.Integer, rules.Min(1)]
}
@rule.route('/newrule', methods = ['POST'], )
def import_file():
    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({"error": "Se requiere un JSON válido"}), 400
        
        name = data.get("name")
        description = data.get("description") or ''
        file_base64 = data.get("filebase64")
        user_id = data.get("iduser")

        if not name:
            return jsonify({'error': 'Falta nombre'}), 400
        if not description:
            description = ''
        if not file_base64:
            return jsonify({'error': 'Falta archivo'}), 400
        if not user_id:
            return jsonify({'error': 'Falta Id de Usuario'}), 400        

        job_id = storage.create_job()

        def run():
            MAX_ATTEMPTS = 3
            RETRY_DELAY = 5
            
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    print(f"Iniciando intento {attempt} para job {job_id}")
                    storage.update_progress(job_id, 10)
                    
                    response = rules_process_form(job_id, name, description, file_base64, user_id)
                    
                    print(f"Termina llamada a función rules_process_form")

                    if response:
                        storage.complete_job(job_id)
                        return
                    elif isinstance(response, list):
                        storage.update_job_with_errors(job_id, response)                                                
                    else:
                        storage.fail_job(job_id)
                        return
                        

                except Exception as e:
                    # Captura EXCEPCIONES (conexión DB, I/O, etc.)
                    # El traceback de rules_process_form ya habrá hecho rollback y logging en el error de la sub-función
                    
                    if attempt < MAX_ATTEMPTS:
                        print(f"Error TRANSITORIO en intento {attempt}. Reintentando en {RETRY_DELAY}s: {e}")
                        # Opcional: registrar el intento de reintento
                        time.sleep(RETRY_DELAY)
                    else:
                        # Último intento fallido: notificar al usuario.
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        error_msg = f"Fallo definitivo después de {MAX_ATTEMPTS} intentos. Error: {e} en {fname}:{exc_tb.tb_lineno}"
                        
                        storage.update_job_with_errors(job_id, [error_msg])
                        storage.fail_job(job_id)
                        print(f"Error FINAL en job {job_id}: {e}")
                        return

        threading.Thread(target=run).start()

        return jsonify({"jobId": job_id}), 200
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

        return jsonify({
            "status": "Error",
            "detail": f"Error at {fname}:{exc_tb.tb_lineno}: {e}",
            "data": {}
        }), 400
    
def rules_process_form(id_job, nombre, descripcion, archivo_base64, user_id):
    regla_id = None
    try:
        session = SessionLocal()    
        time_start = time.perf_counter()

        nombre = nombre
        descripcion = descripcion
        archivo_base64 = archivo_base64

        TZ_LIMA = timezone(timedelta(hours=-5))
        now = datetime.now(TZ_LIMA)

        new_job = Job(
            IdJob = id_job,
            IdUsuario = user_id,
            Nombre = nombre,
            Tipo = "Matriz SoD (Reglas)",
            IdAppUserCreacion = user_id,
            IdAppUserActualizacion = user_id,
            FechaCreacion = now,
            FechaActualizacion = now,
            Estado = 1
        )
        session.add(new_job)
        session.flush()
        session.commit()
        session.expunge_all()

        contenido_base64 = archivo_base64.split(",")[-1]      

        exist_rule = session.query(Regla).filter(Regla.Nombre == nombre).first()

        if exist_rule:
            storage.update_job_with_errors(id_job, [f"La regla con nombre '{nombre}' ya existe."])
            return False            

        storage.update_progress(id_job, 10)  

        new_rule = Regla(
            Nombre=nombre,
            Descripcion=descripcion,
            Archivo="archivo",
            IdAppUserCreacion=user_id,
            IdAppUserActualizacion=user_id,
            FechaCreacion=now,
            FechaActualizacion=now,
            Estado=1
        )
        session.add(new_rule)
        session.flush()
        regla_id = new_rule.Id

        storage.update_progress(id_job, 20)

        response = import_file_regla(contenido_base64, new_rule.Id, user_id=user_id, session=session, id_job=id_job)

        if response is True:
            session.commit()
            return True
        elif isinstance(response, list):
            session.rollback()            
            return response
        else:
            session.rollback()            
            storage.update_job_with_errors(id_job, ["Error desconocido al importar la regla."])
            return False
    except Exception as e:
        raise Exception(f"Error en la función rules_process_form: {e}")
    finally:        
        time_end = time.perf_counter()
        tiempo = round(time_end - time_start,2)
        print(f"Tiempo de ejecución de Regla: {tiempo} segundos")  
        if regla_id:      
            session.query(Regla).filter(Regla.Id == regla_id).update({"Tiempo": tiempo})
            session.commit()

        session.expunge_all()
        session.close()

def import_file_regla(file_base64, regla_id, user_id, session=None, id_job=None):   
    errores = []
    nivelGeneralTransaccion = {}
    nivelGeneralActividad = {}
    nivelGeneralActividadTransaccion = {}
    nivelGeneralObjeto = {}
    nivelGeneralCampo = {} 

    idNivelRiesgo = 5
    genericaNivelRiesgo = session.query(Generica).filter(Generica.Id == idNivelRiesgo).first()
    nivelRiesgos = session.query(Campo).filter(Campo.IdGenerica == idNivelRiesgo).all()
    aNivelRiesgos = {}
    for nivelRiesgo in nivelRiesgos:
        aNivelRiesgos[nivelRiesgo.Nombre] = { "ID": nivelRiesgo.Id, "Nombre": nivelRiesgo.Nombre, "Object": nivelRiesgo }
    
    idTipoRiesgo = 6
    genericaTipoRiesgo = session.query(Generica).filter(Generica.Id == idTipoRiesgo).first()
    tipoRiesgos = session.query(Campo).filter(Campo.IdGenerica == idTipoRiesgo).all()
    aTipoRiesgos = {}
    for tipoRiesgo in tipoRiesgos:
        aTipoRiesgos[tipoRiesgo.Nombre] = { "ID": tipoRiesgo.Id, "Nombre": tipoRiesgo.Nombre, "Object": tipoRiesgo }

    idProcesoRiesgo = 3
    genericaProcesoRiesgo = session.query(Generica).filter(Generica.Id == idProcesoRiesgo).first()
    procesoRiesgos = session.query(Campo).filter(Campo.IdGenerica == idProcesoRiesgo).all()
    aProcesoRiesgos = {}
    for procesoRiesgo in procesoRiesgos:
        aProcesoRiesgos[procesoRiesgo.Nombre] = { "ID": procesoRiesgo.Id, "Nombre": procesoRiesgo.Nombre, "Object": procesoRiesgo }

    idCampo = 1

    idSistema = 2
    campoSistemas = session.query(Campo).filter(Campo.IdGenerica == idSistema).all()
    aCampoSistemas = {}
    for campoSistema in campoSistemas:
        aCampoSistemas[campoSistema.Nombre] = { "ID": campoSistema.Id, "Nombre": campoSistema.Nombre, "Object": campoSistema }

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    storage.update_progress(id_job, 25)

    file_bytes = base64.b64decode(file_base64)
    excel_file = BytesIO(file_bytes)
    wb = load_workbook(filename=excel_file, data_only=True)


    # HOME READ MATRIZ - HOJA FUNCIONES
    hoja_funciones = "II. Funciones"
    if hoja_funciones not in wb.sheetnames:
        errores.append({
            "hoja": hoja_funciones,
            "tipo": "Estructura",
            "posicion": f"N/A",
            "mensaje": f"La hoja '{hoja_funciones}' no existe en el Excel"
        })
    else:
        sheet = wb[hoja_funciones]
        rows = list(sheet.iter_rows(values_only=True))

        storage.update_progress(id_job, 15)

        # Índices de columnas (como en PHP)
        i_actividad = 1
        i_desc_actividad = 2
        i_desc_sistema = 3
        i_desc_transaccion = 4
        i_transaccion = 5

        id_sistema_sap = 2

        bol_save_activity = True

        #cursor = connection.cursor()

        for i, row in enumerate(rows[10:], start=11):  # desde la fila 11       
            codigo_actividad = row[i_actividad]

            if not codigo_actividad:
                errores.append({
                    "hoja": hoja_funciones,
                    "tipo": "Actividad",
                    "posicion": f"C{i}",
                    "mensaje": f"El código de la actividad está vacío"
                })
                continue

            id_sistema = idCampo
            desc_sistema = row[i_desc_sistema] or ""
            bol_sistema = False

            if desc_sistema == "":
                errores.append({
                    "hoja": hoja_funciones,
                    "tipo": "Sistema",
                    "posicion": f"D{i}",
                    "mensaje": f"El sistema está vacío"
                })
                bol_save_activity = False
                continue

            if desc_sistema.upper() in aCampoSistemas:
                id_sistema = aCampoSistemas[desc_sistema.upper()]["ID"]
                bol_sistema = True
            else:
                continue
                
            if codigo_actividad not in nivelGeneralActividad:
                if bol_sistema:
                    desc_actividad = row[i_desc_actividad] or ""

                    new_activity = Actividad(
                        IdRegla=regla_id,
                        Codigo=codigo_actividad,
                        Descripcion=desc_actividad,
                        IdSistema=id_sistema,
                        IdAppUserCreacion=user_id,
                        IdAppUserActualizacion=user_id,
                        FechaCreacion=now,
                        FechaActualizacion=now,
                        Estado=1
                    )
                    session.add(new_activity)
                    session.flush()
                    id_actividad = new_activity.Id
                    nivelGeneralActividad[codigo_actividad] = {"Id": id_actividad, "IdSistema": idSistema}
                    bol_save_activity = True
                else:
                    errores.append({
                        "hoja": hoja_funciones,
                        "tipo": "Sistema",
                        "posicion": f"C{i}",
                        "mensaje": f"El sistema '{desc_sistema}' no existe"
                    })
                    bol_save_activity = False
            else:
                bol_save_activity = True
            
            if bol_save_activity:
                id_actividad = nivelGeneralActividad[codigo_actividad]["Id"]
                codigo_transaccion = row[i_transaccion] or ""
                descripcion_transaccion = row[i_desc_transaccion] or ""

                if not nivelGeneralActividadTransaccion.get(id_actividad, {}).get(idSistema, {}).get(codigo_transaccion):
                    if not nivelGeneralTransaccion.get(idSistema, {}).get(codigo_transaccion):
                        # Guardar Transacción
                        new_transaction = Transaccion(
                            IdRegla=regla_id,
                            IdSistema=id_sistema,
                            Codigo=codigo_transaccion,
                            Nombre=descripcion_transaccion,
                            Padre=0,
                            Nivel=1,
                            IdAppUserCreacion=user_id,
                            IdAppUserActualizacion=user_id,
                            FechaCreacion=now,
                            FechaActualizacion=now,
                            Estado=1
                        )
                        session.add(new_transaction)
                        session.flush()
                        id_transaccion = new_transaction.Id
                        if idSistema not in nivelGeneralTransaccion:
                            nivelGeneralTransaccion[idSistema] = {}
                        nivelGeneralTransaccion[idSistema][codigo_transaccion] = {"IdTransaccion": id_transaccion, "IdSistema": idSistema, "Codigo": codigo_transaccion}
                    else:
                        id_transaccion = nivelGeneralTransaccion[idSistema][codigo_transaccion]["IdTransaccion"]

                    nivelGeneralActividadTransaccion.setdefault(id_actividad, {}) \
                                                    .setdefault(id_sistema, {}) \
                                                    [codigo_transaccion] = {
                        "IdActividad": id_actividad,
                        "IdTransaccion": id_transaccion,
                        "IdSistema": idSistema,
                        "Codigo": codigo_transaccion
                    }
                    new_activity_transaction = ActividadTransaccion(
                        IdActividad=id_actividad,
                        IdTransaccion=id_transaccion,
                        IdAppUserCreacion=user_id,
                        IdAppUserActualizacion=user_id,
                        FechaCreacion=now,
                        FechaActualizacion=now,
                        Estado=1
                    )
                    session.add(new_activity_transaction)
                    session.flush()
            else:
                errores.append({
                    "hoja": hoja_funciones,
                    "tipo": "Actividad",
                    "posicion": f"B{i}",
                    "mensaje": f"El sistema de la actividad '{codigo_actividad}' no existe"
                })         
    
    storage.update_progress(id_job, 30)

    #HOME READ MATRIZ PERMISOS
    hoja_funciones = "III. Permisos"
    if hoja_funciones not in wb.sheetnames:
        errores.append({
            "hoja": hoja_funciones,
            "tipo": "Estructura",
            "posicion": f"N/A",
            "mensaje": f"La hoja '{hoja_funciones}' no existe en el Excel"
        })
    else:
        sheet = wb[hoja_funciones]
        rows = list(sheet.iter_rows(values_only=True))

        storage.update_progress(id_job, 45)

        i_actividad = 0
        i_transaccion = 1
        i_objeto = 2
        i_campo = 3
        i_desde = 4
        i_hasta = 5
        i_condicional = 6

        bol_save_activity = True

        for i, row in enumerate(rows[1:], start=2):  # desde la fila 2
            codigo_actividad = row[i_actividad]            
            codigo_transaccion = row[i_transaccion] or ""
            codigo_objeto = row[i_objeto] or ""
            codigo_campo = row[i_campo] or ""

            if(not codigo_actividad):
                errores.append({
                    "hoja": hoja_funciones,
                    "tipo": "Actividad",
                    "posicion": f"C{i}",
                    "mensaje": f"El código de la actividad está vacío"
                })
                continue

            BolSapObjetoCampo = True

            if codigo_actividad not in nivelGeneralActividad:
                errores.append({
                    "hoja": hoja_funciones,
                    "tipo": "Actividad",
                    "posicion": f"A{i}",
                    "mensaje": f"La actividad {codigo_actividad} no existe"
                })
                BolSapObjetoCampo = False

            if id_sistema_sap not in nivelGeneralTransaccion or codigo_transaccion not in nivelGeneralTransaccion[id_sistema_sap]:
                errores.append({
                    "hoja": hoja_funciones,
                    "tipo": "Transacccion",
                    "posicion": f"A{i}",
                    "mensaje": f"La transacción {codigo_transaccion} no existe"
                })
                BolSapObjetoCampo = False

            if BolSapObjetoCampo:
                id_activity = nivelGeneralActividad[codigo_actividad]["Id"]
                id_transaction = nivelGeneralTransaccion[id_sistema_sap][codigo_transaccion]["IdTransaccion"]
                id_sistema =  nivelGeneralTransaccion[id_sistema_sap][codigo_transaccion]["IdSistema"]

                if codigo_objeto not in nivelGeneralObjeto:
                    new_sapobject = SapObjeto(
                        IdRegla=regla_id,
                        IdSistema=id_sistema,
                        Nombre=codigo_objeto,
                        Descripcion="",
                        IdAppUserCreacion=user_id,
                        IdAppUserActualizacion=user_id,
                        FechaCreacion=now,
                        FechaActualizacion=now,
                        Estado=1
                    )
                    session.add(new_sapobject)
                    session.flush()
                    id_sap_objeto = new_sapobject.Id
                    nivelGeneralObjeto[codigo_objeto] = {"Id": id_sap_objeto}
                else:
                    id_sap_objeto = nivelGeneralObjeto[codigo_objeto]["Id"]

                if codigo_campo not in nivelGeneralCampo:
                    new_sapfield = SapCampo(
                        IdRegla=regla_id,
                        IdSistema=id_sistema,
                        Nombre=codigo_campo,
                        Descripcion="",
                        IdAppUserCreacion=user_id,
                        IdAppUserActualizacion=user_id,
                        FechaCreacion=now,
                        FechaActualizacion=now,
                        Estado=1
                    )
                    session.add(new_sapfield)
                    session.flush()
                    id_sap_campo = new_sapfield.Id
                    nivelGeneralCampo[codigo_campo] = {"Id": id_sap_campo}
                else:
                    id_sap_campo = nivelGeneralCampo[codigo_campo]["Id"]

                
                def php_empty(value):
                    # Emula el comportamiento de PHP empty() para los casos relevantes aquí
                    if value is None:
                        return True
                    if value == 0 or value == 0.0:
                        return True
                    if isinstance(value, str):
                        return value == "" or value == "0"
                    return False

                celda_desde = row[i_desde]
                celda_hasta = row[i_hasta]
                celda_condicional = row[i_condicional]

                desde = "" if php_empty(celda_desde) else str(celda_desde)
                hasta = "" if php_empty(celda_hasta) else str(celda_hasta)
                condicional = "" if php_empty(celda_condicional) else str(celda_condicional)                

                if condicional != "AND" and condicional != "OR" and condicional != "NOT":
                    condicional = "OR"

                new_sapobjctfield = SapObjetoCampo(
                    IdRegla=regla_id,
                    IdActividad=id_activity,
                    IdTransaccion=id_transaction,
                    IdSapObjeto=id_sap_objeto,
                    IdSapCampo=id_sap_campo,
                    Desde=desde,
                    Hasta=hasta,
                    Condicional=condicional,
                    IdAppUserCreacion=user_id,
                    IdAppUserActualizacion=user_id,
                    FechaCreacion=now,
                    FechaActualizacion=now,
                    Estado=1
                )
                session.add(new_sapobjctfield)
                session.flush()

    storage.update_progress(id_job, 50)

    #HOME READ MATRIZ - HOJA REGLAS
    hoja_funciones = "I. Reglas SoD"
    if hoja_funciones not in wb.sheetnames:
        errores.append({
            "hoja": hoja_funciones,
            "tipo": "Estructura",
            "posicion": f"N/A",
            "mensaje": f"La hoja '{hoja_funciones}' no existe en el Excel"
        })
    else:
        sheet = wb[hoja_funciones]
        rows = list(sheet.iter_rows(values_only=True))

        storage.update_progress(id_job, 75)
        
        i_codigoriesgo = 1
        i_descripcionriesgo = 2
        i_actividad = 3

        i_codigo_proceso_riesgo = 0
        for i, value in enumerate(rows[9]):  # Fila 10 en base 0
            if value == "Proceso":
                i_codigo_proceso_riesgo = i
                break

        i_nombrenivelriesgo = i_codigo_proceso_riesgo - 1
        i_nombretiporiesgo = i_codigo_proceso_riesgo + 1

        itemreglas = []

        for p_row in rows[10:]:  # Desde la fila 11 (índice 10)
            codigo_riesgo = p_row[i_codigoriesgo]
            if codigo_riesgo is None:
                break
            itemreglas.append(codigo_riesgo)

        from collections import Counter
        count_reglas = Counter(itemreglas)

        # Cálculo de columnas (equivalente exacto al PHP)
        max_colum_actividad = i_codigo_proceso_riesgo - 2 - (i_actividad - 1)
        max_activity = max_colum_actividad // 2  # En PHP es división normal pero al ser par el resultado es igual

        # Procesamiento de filas (equivalente exacto)
        for i, row in enumerate(rows[10:], start=11):  # Equivalente a for($IntRow=10;...)
            # Extracción de valores (índices calculados igual que en PHP)
            codigo_proceso_riesgo = row[i_codigo_proceso_riesgo].strip()
            nombre_nivel_riesgo = row[i_nombrenivelriesgo].strip()
            codigo_tipo_riesgo = row[i_nombretiporiesgo].strip()
            codigo_riesgo = row[i_codigoriesgo].strip()
            
            # Validación de fin de datos (equivalente a is_null en PHP)
            if codigo_riesgo is None:  # Más explícito que 'if not' para equivalencia exacta
                break
            
            # Validaciones (estructura idéntica al PHP)
            if codigo_proceso_riesgo is None:
                errores.append({
                    "hoja": hoja_funciones,
                    "tipo": "Proceso",
                    "posicion": f"{get_column_letter(i_codigo_proceso_riesgo + 1)}{i}",  # Equivalente a Helper::ColumnsExcel
                    "mensaje": "El valor del proceso no está ingresado"
                })
                codigo_proceso_riesgo = ""
            
            if nombre_nivel_riesgo is None:
                errores.append({
                    "hoja": hoja_funciones,
                    "tipo": "Nivel de Riesgo",
                    "posicion": f"{get_column_letter(i_nombrenivelriesgo + 1)}{i}",
                    "mensaje": "El valor del nivel de riesgo no está ingresado"
                })
                nombre_nivel_riesgo = ""
            
            if codigo_tipo_riesgo is None:
                errores.append({
                    "hoja": hoja_funciones,
                    "tipo": "Tipo de Riesgo",
                    "posicion": f"{get_column_letter(i_nombretiporiesgo + 1)}{i}",
                    "mensaje": "El valor del tipo de riesgo no está ingresado"
                })
                codigo_tipo_riesgo = ""
            
            # Gestión de ProcesoRiesgo (equivalente exacto)
            if codigo_proceso_riesgo in aProcesoRiesgos:
                proceso_riesgo = aProcesoRiesgos[codigo_proceso_riesgo]["Object"]
            else:
                new_proceso_riesgo = Campo(
                    IdGenerica=genericaProcesoRiesgo.Id,
                    Nombre=codigo_proceso_riesgo,
                    IdAppUserCreacion=user_id,
                    IdAppUserActualizacion=user_id,
                    FechaCreacion=now,
                    FechaActualizacion=now
                )
                session.add(new_proceso_riesgo)
                session.flush()
                
                aProcesoRiesgos[codigo_proceso_riesgo] = {
                    "ID": new_proceso_riesgo.Id,
                    "Nombre": codigo_proceso_riesgo,
                    "Object": new_proceso_riesgo
                }
                proceso_riesgo = new_proceso_riesgo
            
            # Gestión de NivelRiesgo (patrón idéntico al PHP)
            if nombre_nivel_riesgo in aNivelRiesgos:
                nivel_riesgo = aNivelRiesgos[nombre_nivel_riesgo]["Object"]
            else:
                new_nivel_riesgo = Campo(
                    IdGenerica=genericaNivelRiesgo.Id,
                    Nombre=nombre_nivel_riesgo,
                    IdAppUserCreacion=user_id,
                    IdAppUserActualizacion=user_id,
                    FechaCreacion=now,
                    FechaActualizacion=now
                )
                session.add(new_nivel_riesgo)
                session.flush()
                
                aNivelRiesgos[nombre_nivel_riesgo] = {
                    "ID": new_nivel_riesgo.Id,
                    "Nombre": nombre_nivel_riesgo,
                    "Object": new_nivel_riesgo
                }
                nivel_riesgo = new_nivel_riesgo
            
            # Gestión de TipoRiesgo (equivalente exacto)
            if codigo_tipo_riesgo in aTipoRiesgos:
                tipo_riesgo = aTipoRiesgos[codigo_tipo_riesgo]["Object"]
            else:
                new_tipo_riesgo = Campo(
                    IdGenerica=genericaTipoRiesgo.Id,
                    Nombre=codigo_tipo_riesgo,
                    IdAppUserCreacion=user_id,
                    IdAppUserActualizacion=user_id,
                    FechaCreacion=now,
                    FechaActualizacion=now
                )
                session.add(new_tipo_riesgo)
                session.flush()
                
                aTipoRiesgos[codigo_tipo_riesgo] = {
                    "ID": new_tipo_riesgo.Id,
                    "Nombre": codigo_tipo_riesgo,
                    "Object": new_tipo_riesgo
                }
                tipo_riesgo = new_tipo_riesgo

            bolRiesgo = True
            # Verificación de duplicados (equivalente exacto al array_count_values de PHP)
            if itemreglas.count(codigo_riesgo) > 1:
                errores.append({
                    "hoja": hoja_funciones,
                    "tipo": "Riesgo",  # Corregido para que coincida con PHP ("Nivel de Riesgo" → "Riesgo")
                    "posicion": f"{get_column_letter(i_codigoriesgo + 1)}{i}",  # Equivalente exacto a Helper::ColumnsExcel
                    "mensaje": f"El código de riesgo {codigo_riesgo} está duplicado"
                })
                bolRiesgo = False

            if bolRiesgo:
                # Equivalente exacto al PHP (None → cadena vacía)
                descripcionriesgo = row[i_descripcionriesgo] if row[i_descripcionriesgo] is not None else ""
                
                new_risk = Riesgo(
                    IdRegla=regla_id,
                    IdProcesoRiesgo=proceso_riesgo.Id,
                    IdNivelRiesgo=nivel_riesgo.Id,
                    IdTipoRiesgo=tipo_riesgo.Id,
                    Codigo=codigo_riesgo,
                    Descripcion=descripcionriesgo,
                    Observacion="",
                    IdAppUserCreacion=user_id,
                    IdAppUserActualizacion=user_id,
                    FechaCreacion=now,
                    FechaActualizacion=now,
                    Estado=1  # PHP no muestra este campo pero se asume que es necesario
                )
                session.add(new_risk)
                session.flush()  # Equivalente a entityManager->persist()

            # Procesamiento de actividades (ajustado para equivalencia exacta)
            int_column_count = 0
            for j in range(max_activity):
                # Validación idéntica al PHP (None y string vacío)
                codigo_actividad = row[i_actividad + int_column_count]
                if codigo_actividad is None:
                    break
                if isinstance(codigo_actividad, str) and codigo_actividad.strip() == "":
                    break
                
                if codigo_actividad in nivelGeneralActividad:
                    if bolRiesgo:
                        id_actividad = nivelGeneralActividad[codigo_actividad]["Id"]
                        actividad = session.query(Actividad).get(id_actividad)  # Equivalente a find()
                        
                        # Equivalente exacto al getActiveByActividad()
                        actividad_transacciones = session.query(ActividadTransaccion)\
                                                    .filter(ActividadTransaccion.IdActividad == id_actividad,
                                                            ActividadTransaccion.Estado == 1)\
                                                    .all()
                        
                        for actividad_transaccion in actividad_transacciones:
                            new_riskactivitytransaction = RiesgoActividadTransaccion(
                                IdRiesgo=new_risk.Id,
                                IdActividad=actividad.Id,
                                IdTransaccion=actividad_transaccion.IdTransaccion,
                                IdAppUserCreacion=user_id,
                                IdAppUserActualizacion=user_id,
                                FechaCreacion=now,
                                FechaActualizacion=now,
                                Estado=1
                            )
                            session.add(new_riskactivitytransaction)
                            # Movido el flush() fuera del bucle para mejor performance
                else:
                    errores.append({
                        "hoja": hoja_funciones,
                        "tipo": "Función",  # Cambiado de "Actividad" a "Función" como en PHP
                        "posicion": f"{get_column_letter(i_actividad + int_column_count + 1)}{i}",
                        "mensaje": f"El código de la función {codigo_actividad} no existe"
                    })
                
                int_column_count += 2

            # Single flush para todas las transacciones de actividad
            if bolRiesgo and 'actividad_transacciones' in locals():
                session.flush()

    storage.update_progress(id_job, 80)
    
    if len(errores) > 0:       
        print("Regla con errores:")     
        for error in errores:
            print(error)
        return errores
    
    print("Regla importada exitosamente sin errores.")
    
    return True

def serialize_regla(r):
    """Serializa el modelo Regla al mismo formato esperado por tu frontend."""
    return {
        "id": r.Id,
        "nombre": r.Nombre,
        "descripcion": r.Descripcion,
        "idAppUserCreacion": r.IdAppUserCreacion,
        "idAppUserActualizacion": r.IdAppUserActualizacion,
        "fechaCreacion": r.FechaCreacion.strftime(DATE_FMT) if r.FechaCreacion else None,
        "fechaActualizacion": r.FechaActualizacion.strftime(DATE_FMT) if r.FechaActualizacion else None,
        "estado": r.Estado
    }

def json_500(e):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    return jsonify({
        "status": "Error",
        "detail": f"Error at {fname}:{exc_tb.tb_lineno}: {e}"
    }), 500

@rule.route('/update', methods=['POST','OPTIONS'])
def update():
    session = SessionLocal()

    try:
        data = request.get_json()

        if not data or not isinstance(data, dict):
            return jsonify({"error": "Se requiere un JSON válido"}), 400

        rule_id = data.get("id")
        nombre = data.get("nombre")
        descripcion = data.get("descripcion", "")
        id_user = data.get("idAppUserCreacion")

        if not rule_id:
            return jsonify({"error": "Falta id"}), 400
        if not nombre:
            return jsonify({"error": "Falta nombre"}), 400
        if not id_user:
            return jsonify({"error": "Falta Id de Usuario"}), 400

        rule = session.get(Regla, rule_id)
        if not rule:
            return jsonify({"error": "Regla no encontrada"}), 404
        
        duplicate = (
            session.query(Regla)
            .filter(Regla.Nombre == nombre, Regla.Id != rule_id)
            .first()
        )

        if duplicate:
            return jsonify({"error": "Ya existe una regla con ese nombre"}), 400

        TZ_LIMA = timezone(timedelta(hours=-5))
        now_dt = datetime.now(TZ_LIMA)

        # Actualizar
        rule.Nombre = nombre
        rule.Descripcion = descripcion
        rule.IdAppUserActualizacion = id_user
        rule.FechaActualizacion = now_dt

        session.commit()

        return jsonify({"status": "success", "data": {"id": rule_id}}), 200

    except Exception as e:
        session.rollback()

        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

        return jsonify({
            "status": "Error",
            "detail": f"Error at {fname}:{exc_tb.tb_lineno}: {e}"
        }), 500

    finally:
        session.close()

@rule.route('/all', methods=['GET'])
def get_all():
    session = SessionLocal()

    try:
        reglas = session.query(Regla).order_by(desc(Regla.FechaActualizacion)).all()

        # Serialización al formato deseado
        data = []
        for r in reglas:
            data.append({
                "id": r.Id,
                "nombre": r.Nombre,
                "descripcion": r.Descripcion,
                "idAppUserCreacion": r.IdAppUserCreacion,
                "idAppUserActualizacion": r.IdAppUserActualizacion,
                "fechaCreacion": r.FechaCreacion.strftime("%Y-%m-%d %H:%M:%S") if r.FechaCreacion else None,
                "fechaActualizacion": r.FechaActualizacion.strftime("%Y-%m-%d %H:%M:%S") if r.FechaActualizacion else None,
                "estado": r.Estado
            })

        return jsonify(data), 200

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

        return jsonify({
            "status": "Error",
            "detail": f"Error at {fname}:{exc_tb.tb_lineno}: {e}"
        }), 500

    finally:
        session.close()

@rule.route('/<int:regla_id>', methods=['GET'])
def get_by_id(regla_id):
    session = SessionLocal()
    try:
        regla = session.get(Regla, regla_id)
        if not regla:
            return jsonify({"error": "Regla no encontrada"}), 404
        return jsonify(serialize_regla(regla)), 200
    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()

@rule.route('/delete', methods=['POST'])
def delete_one():
    session = SessionLocal()
    try:
        data = request.get_json() or {}
        regla_id = data.get("id")
        if not regla_id:
            return jsonify({"error": "Falta id"}), 400

        regla = session.get(Regla, regla_id)
        if not regla:
            return jsonify({"error": "Regla no encontrada"}), 404

        regla.Estado = 0
        session.commit()
        return jsonify({"status": "success", "deletedId": regla_id}), 200

    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()

@rule.route('/<int:regla_id>', methods=['DELETE'])
def delete_one_rest(regla_id):
    session = SessionLocal()
    try:
        regla = session.get(Regla, regla_id)
        if not regla:
            return jsonify({"error": "Regla no encontrada"}), 404
        regla.Estado = 0
        session.commit()
        return jsonify({"status": "success", "deletedId": regla_id}), 200
    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()

@rule.route('/delete-multiple', methods=['POST'])
def delete_multiple():
    session = SessionLocal()
    try:
        data = request.get_json() or []
        if not isinstance(data, list) or not all(isinstance(x, int) for x in data):
            return jsonify({"error": "Se requiere lista de enteros (ids)"}), 400

        if not data:
            return jsonify({"error": "Lista de ids vacía"}), 400

        # Soft-delete
        updated = (
            session.query(Regla)
            .filter(Regla.Id.in_(data))
            .update({Regla.Estado: 0}, synchronize_session=False)
        )
        session.commit()
        return jsonify({"status": "success", "updated": updated}), 200

    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()

@rule.route('/details/<int:regla_id>', methods=['GET'])
def get_details_by_id(regla_id):
    session = SessionLocal()
    try:
        # 1) Regla base
        regla = session.get(Regla, regla_id)
        if not regla:
            return jsonify({"error": "Regla no encontrada"}), 404

        # ---------- 2) SOD ----------
        # Aliases (equivalentes a canr, capr, ac, etc.)
        RIAT = RiesgoActividadTransaccion
        RI = Riesgo
        CANR = aliased(Campo)  # nivel riesgo
        CAPR = aliased(Campo)  # proceso riesgo
        AC = Actividad

        sod_rows = (
            session.query(
                RI.Id.label("ri_id"),
                RI.Codigo.label("ri_codigo"),
                RI.Descripcion.label("ri_descripcion"),
                RIAT.IdActividad.label("riat_idactividad"),
                AC.Codigo.label("ac_codigo"),
                AC.Descripcion.label("ac_descripcion"),
                CANR.Nombre.label("canr_nombre"),
                CAPR.Nombre.label("capr_nombre"),
                RIAT.Id.label("riat_id")  # para ordenar como en tu LINQ (orderby riat.Id)
            )
            .join(RI, RIAT.IdRiesgo == RI.Id)
            .join(CANR, RI.IdNivelRiesgo == CANR.Id)
            .join(CAPR, RI.IdProcesoRiesgo == CAPR.Id)
            .join(AC, RIAT.IdActividad == AC.Id)
            .filter(RI.IdRegla == regla.Id)
            .order_by(RIAT.Id.asc())
            .all()
        )

        # Agrupar por (IdRiesgo, IdActividad) y tomar el primero (equivalente a g.First())
        seen = set()
        data_sod = []
        for row in sod_rows:
            key = (row.ri_id, row.riat_idactividad)
            if key in seen:
                continue
            seen.add(key)
            data_sod.append({
                "id": row.ri_id,
                "codigo": row.ri_codigo,
                "descripcion": row.ri_descripcion,
                "idActividad": row.riat_idactividad,
                "codigoActividad": row.ac_codigo,
                "descripcionActividad": row.ac_descripcion,
                "nombreNivelRiesgo": row.canr_nombre,
                "nombreProcesoRiesgo": row.capr_nombre
            })

        # ---------- 3) FUNCIONES ----------
        AT = ActividadTransaccion
        T = Transaccion
        CAAC = Campo  # sistema de actividad

        funciones_rows = (
            session.query(
                AC.Codigo.label("ac_codigo"),
                AC.Descripcion.label("ac_descripcion"),
                CAAC.Nombre.label("sistema_nombre"),
                T.Codigo.label("t_codigo"),
                T.Nombre.label("t_nombre")
            )
            .select_from(AT)
            .join(AC, AT.IdActividad == AC.Id)
            .join(CAAC, AC.IdSistema == CAAC.Id)
            .join(T, AT.IdTransaccion == T.Id)
            .filter(AC.IdRegla == regla.Id)
            .order_by(AT.Id.asc())
            .all()
        )

        data_funciones = [{
            "codigoActividad": r.ac_codigo,
            "descripcionActividad": r.ac_descripcion,
            "nombreSistema": r.sistema_nombre,
            "codigoTransaccion": r.t_codigo,
            "nombreTransaccion": r.t_nombre
        } for r in funciones_rows]

        # ---------- 4) OPCIONES ----------
        CAS = Campo  # sistema de transacción

        opciones_rows = (
            session.query(
                T.Id.label("t_id"),
                T.Codigo.label("t_codigo"),
                CAS.Nombre.label("sistema_nombre")
            )
            .join(CAS, T.IdSistema == CAS.Id)
            .filter(and_(T.IdRegla == regla.Id, T.Codigo != ""))
            .order_by(CAS.Nombre.asc(), T.Codigo.asc())
            .all()
        )

        data_opciones = [{
            "id": r.t_id,
            "codigo": r.t_codigo,
            "nombre": r.t_codigo,  # igual que tu DTO
            "nombreSistema": r.sistema_nombre
        } for r in opciones_rows]

        # ---------- 5) Respuesta final ----------
        result = {
            "regla": serialize_regla(regla),
            "sod": data_sod,
            "funciones": data_funciones,
            "opciones": data_opciones
        }

        return jsonify(result), 200

    except Exception as e:
        session.rollback()
        return json_500(e)
    finally:
        session.close()


