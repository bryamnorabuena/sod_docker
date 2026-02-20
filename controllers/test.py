import base64
from datetime import datetime
from fnmatch import fnmatch
from io import BytesIO
import io
import os
import zipfile
from flask import Blueprint, json, request, jsonify
import requests
from sqlalchemy import and_, asc, desc, select

from config import config
from db.database import SessionLocal
from models.appfiori import AppFiori
from models.catalogo import Catalogo
from models.catalogoappfiori import CatalogoAppFiori
from models.proceso import Proceso
from models.sapautorizacion import SapAutorizacion
from models.sapcampoproceso import SapCampoProceso
from models.sapobjetoautorizacion import SapObjetoAutorizacion
from models.sapobjetoproceso import SapObjetoProceso
from models.sapperfil import SapPerfil
from models.sapperfilobjetoautorizacion import SapPerfilObjetoAutorizacion
from models.saprol import SapRol
from models.saprolcatalogo import SapRolCatalogo
from models.saprolobjetoautorizacion import SapRolObjetoAutorizacion
from models.sapusuario import SapUsuario
from models.sapusuarioperfil import SapUsuarioPerfil
from models.sapusuariorol import SapUsuarioRol
from models.transaccion import Transaccion
from models.usuario import Usuario
from models.usuariotransaccion import UsuarioTransaccion
from models.usuariotransaccionrol import UsuarioTransaccionRol
from services import analyze_conflicts
from utils.environment import get_environment
from db.database import SessionLocal

test = Blueprint('test', __name__)

@test.route('/get-ip', methods=['GET'])
def get_ip():
    response = requests.get(f'http://ipinfo.io/json', verify=False)
    return jsonify(response.json())

@test.route('/testConflicts', methods=['GET'])
def test_conflicts():
    session = SessionLocal()
    proceso = Proceso(
        Id = 35,
        IdRegla = 6
    )

    aAuthorization = {}
    field_transaction = get_environment('FIELD_TRANSACTION')
    sap_object_process = session.query(SapObjetoProceso).filter(SapObjetoProceso.IdProceso == proceso.Id, SapObjetoProceso.Nombre == field_transaction).first()

    if sap_object_process:
        transaction_rules = session.query(Transaccion).filter(Transaccion.IdRegla == proceso.IdRegla, Transaccion.IdSistema == config.SYSTEMS['SAP'], Transaccion.Codigo != '').all()
        users = session.query(
            SapUsuarioPerfil.IdUsuario.label("id_usuario"),
            SapUsuarioPerfil.IdSapPerfil.label("id_perfil"),
            SapPerfilObjetoAutorizacion.IdSapAutorizacion.label("id_autorizacion"),
            Usuario.Usuario.label("usuario"),
            SapPerfil.Nombre.label("nombre_perfil"),                                
        ).join(
            SapPerfilObjetoAutorizacion, SapPerfilObjetoAutorizacion.IdSapPerfil == SapUsuarioPerfil.IdSapPerfil
        ).join(
            Usuario, Usuario.Id == SapUsuarioPerfil.IdUsuario
        ).join(
            SapPerfil, SapPerfil.Id == SapUsuarioPerfil.IdSapPerfil
        ).filter(
            SapUsuarioPerfil.IdProceso == proceso.Id
        ).group_by(
            SapUsuarioPerfil.IdUsuario,
            SapUsuarioPerfil.IdSapPerfil,
            SapPerfilObjetoAutorizacion.IdSapAutorizacion
        ).order_by(
            SapUsuarioPerfil.IdUsuario,
            SapUsuarioPerfil.IdSapPerfil,
            SapPerfilObjetoAutorizacion.IdSapAutorizacion
        ).all()

        for user in users:
            row = user._asdict()

            user_id = row["id_usuario"]
            user = row["usuario"]
            authorization_id = row["id_autorizacion"]
            if authorization_id not in aAuthorization:
                transactions = session.query(SapObjetoAutorizacion).filter(SapObjetoAutorizacion.IdProceso == proceso.Id, SapObjetoAutorizacion.IdSapAutorizacion == authorization_id, SapObjetoAutorizacion.IdSapObjetoProceso == sap_object_process.Id).all()
                aTransactions = []
                for transaction in transactions:
                    from_val = transaction.Desde
                    to_val = transaction.Hasta
                    aTransactions.append({"Desde": from_val, "Hasta": to_val})
                aAuthorization[authorization_id] = aTransactions
            if len(aAuthorization[authorization_id]) > 0:
                for idx, transaction in enumerate(aAuthorization[authorization_id]):
                    transaction = aAuthorization[authorization_id][idx]["Desde"]
                    if transaction == "*":
                        transaction_codes = transaction_rules
                        for transaction_rule in transaction_rules:
                            user_transaction = session.query(UsuarioTransaccionRol).filter(UsuarioTransaccionRol.IdProceso == proceso.Id, UsuarioTransaccionRol.IdUsuario == user_id, UsuarioTransaccionRol.IdTransaccion == transaction_rule.Id).first()
                            if not user_transaction:
                                oTransaction = session.query(Transaccion).filter(Transaccion.Id == transaction_rule.Id).first()
                                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                new_userTransaction = UsuarioTransaccion(
                                    IdProceso = proceso.Id,
                                    IdUsuario = user_id,
                                    IdTransaccion = oTransaction.Id,
                                    IdAppUserCreacion = proceso.IdAppUserCreacion,
                                    IdAppUserActualizacion = proceso.IdAppUserActualizacion,
                                    FechaCreacion = now,
                                    FechaActualizacion = now,
                                    Estado = 1
                                )
                                #sesion.add(new_userTransaction)
                    elif transaction.find("*") != -1:
                        transaction_codes = [ tr for tr in transaction_rules if fnmatch(tr.Codigo, transaction) ]
                        if len(transaction_codes) == 0:
                            transaction_codes = [ tr for tr in transaction_rules if fnmatch(transaction, tr.Codigo) ]
                        for item_transaction_code in transaction_codes:
                            user_transaction = session.query(UsuarioTransaccionRol).filter(UsuarioTransaccionRol.IdProceso == proceso.Id, UsuarioTransaccionRol.IdUsuario == user_id, UsuarioTransaccionRol.IdTransaccion == transaction_codes[0].Id).first()
                            if not user_transaction:
                                oTransaction = session.query(Transaccion).filter(Transaccion.Id == transaction_codes[0].Id).first()
                                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                                new_userTransaction = UsuarioTransaccion(
                                    IdProceso = proceso.Id,
                                    IdUsuario = user_id,
                                    IdTransaccion = oTransaction.Id,
                                    IdAppUserCreacion = proceso.IdAppUserCreacion,
                                    IdAppUserActualizacion = proceso.IdAppUserActualizacion,
                                    FechaCreacion = now,
                                    FechaActualizacion = now,
                                    Estado = 1
                                )
                                #sesion.add(new_userTransaction)
                    else:
                        transaction_codes = [ tr for tr in transaction_rules if tr.Codigo == transaction ]
                        if len(transaction_codes) > 0:
                            user_transaction = session.query(UsuarioTransaccion).filter(UsuarioTransaccion.IdProceso == proceso.Id, UsuarioTransaccion.IdUsuario == user_id, UsuarioTransaccion.IdTransaccion == transaction_codes[0].Id).first()
                            if not user_transaction:
                                oTransaction = session.query(Transaccion).filter(Transaccion.Id == transaction_codes[0].Id).first()
                                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                new_userTransaction = UsuarioTransaccion(
                                    IdProceso = proceso.Id,
                                    IdUsuario = user_id,
                                    IdTransaccion = oTransaction.Id,
                                    IdAppUserCreacion = proceso.IdAppUserCreacion,
                                    IdAppUserActualizacion = proceso.IdAppUserActualizacion,
                                    FechaCreacion = now,
                                    FechaActualizacion = now,
                                    Estado = 1
                                )
                                #sesion.add(new_userTransaction)
        ##session.flush()
    
    id_system_fiori = config.SYSTEMS["FIORI"]
    max_date_sap = config.MAX_DATE_SAP
    transaction_rules = session.query(Transaccion).filter(Transaccion.IdRegla == proceso.IdRegla, Transaccion.IdSistema == id_system_fiori, Transaccion.Codigo != '').all()
    users = session.query(UsuarioTransaccion)\
        .join(SapUsuario, SapUsuario.IdUsuario == UsuarioTransaccion.IdUsuario, SapUsuario.IdProceso == UsuarioTransaccion.IdProceso)\
        .filter(UsuarioTransaccion.IdProceso == proceso.Id, SapUsuario.FechaInicio <= now, SapUsuario.FechaFin >= now, SapUsuario.Uflag.in_(0,128))\
        .group_by(UsuarioTransaccion.IdUsuario)\
        .order_by(UsuarioTransaccion.Id).all()
    
    for user in users:
        item_user_id = user.Id
        for transaction_rule in transaction_rules:
            bol_transaction = False
            transaction_id = transaction_rule.Id
            transaction_code = transaction_rule.Codigo

            catalog_app_fioris = session.query(
                CatalogoAppFiori
            ).join(
                Catalogo, Catalogo.Id == CatalogoAppFiori.IdCatalogo
            ).join(
                AppFiori, AppFiori.Id == CatalogoAppFiori.IdAppFiori
            ).filter(
                Catalogo.IdProceso == proceso.Id,
                AppFiori.IdProceso == proceso.Id,
                AppFiori.Nombre == transaction_code
            ).all()

            aCatalog = []
            for catalog_app_fiori in catalog_app_fioris:
                aCatalog.append(catalog_app_fiori.IdCatalogo)

            if len(aCatalog) > 0:
                sapRoleCatalogs = session.query(
                    SapRolCatalogo
                ).filter(
                    SapRolCatalogo.IdProceso == proceso.Id,
                    SapRolCatalogo.IdCatalogo.in_(aCatalog)
                ).all()

                aRoles = []
                for sapRoleCatalog in sapRoleCatalogs:
                    aRoles.append(sapRoleCatalog.IdSapRol)

                if len(aRoles) > 0:
                    for aRole in aRoles:
                        data_roles = session.query(SapUsuarioRol).filter(
                            SapUsuarioRol.IdProceso == proceso.Id,
                            SapUsuarioRol.IdUsuario == item_user_id,
                            SapUsuarioRol.IdSapRol == aRole
                        ).order_by(desc(SapUsuarioRol.IdSapRol)).all()

                        if len(data_roles) > 0:
                            for data_role in data_roles:
                                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                IdSapRole = data_role["IdSapRol"]
                                bolRole = True
                                start_date = datetime.strptime(data_role.FechaInicio, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
                                end_date = datetime.strptime(data_role.FechaFin, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
                                if end_date == datetime.strptime(max_date_sap, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S'):
                                    end_date = datetime.strptime(config.MAX_DATE_PHP, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
                                if not (start_date <= now and end_date >= now):
                                    bolRole = False
                                if bolRole is True and bol_transaction is False:
                                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    new_userTransaction = UsuarioTransaccion(
                                        IdProceso = proceso.Id,
                                        IdUsuario = item_user_id,
                                        IdTransaccion = transaction_id,
                                        IdAppUserCreacion = proceso.IdAppUserCreacion,
                                        IdAppUserActualizacion = proceso.IdAppUserActualizacion,
                                        FechaCreacion = now,
                                        FechaActualizacion = now,
                                        Estado = 1
                                    )
                                    #sesion.add(new_userTransaction)
                                    #session.flush()
                                    bol_transaction = True
                                if bolRole:
                                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    new_userTransactionRole = UsuarioTransaccionRol(
                                        IdProceso = proceso.Id,
                                        IdUsuario = item_user_id,
                                        IdTransaccion = transaction_id,
                                        IdSapRol = IdSapRole,
                                        IdAppUserCreacion = proceso.IdAppUserCreacion,
                                        IdAppUserActualizacion = proceso.IdAppUserActualizacion,
                                        FechaCreacion = now,
                                        FechaActualizacion = now,
                                        Estado = 1                                                
                                    )
                                    #sesion.add(new_userTransactionRole)
                                    ##session.flush()   

    return jsonify({"success": True})

@test.route('/testUsers', methods=['GET'])
def test_process():
    session = SessionLocal()

    try:        
        users = session.query(Usuario).all()
        for user in users:
            print(user.Usuario)
        return True
    except Exception as e:
        print(f"Error al procesar el archivo: {str(e)}")
        return False
    finally:
        session.rollback()
        session.expunge_all()
        session.close()


