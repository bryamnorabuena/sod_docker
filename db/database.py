import json
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import quote_plus
from utils.environment import get_environment

FLASK_ENV = os.getenv("APP_ENV") or get_environment("APP_ENV")
if not FLASK_ENV:
    raise RuntimeError("APP_ENV no está definida en el entorno del Job.")

CONFIG_TYPE = os.getenv("DB_CONNECTION_TYPE") or get_environment('DB_CONNECTION_TYPE', 'MYSQL')
DB_CONNECTION_SQL_SERVER = os.getenv("DB_CONNECTION_SQL_SERVER") or get_environment('DB_CONNECTION_SQL_SERVER')
DB_CONNECTION = os.getenv("DB_CONNECTION") or get_environment('DB_CONNECTION')

if FLASK_ENV == "local":
    if CONFIG_TYPE == 'SQL_SERVER':
        CONFIG = json.loads(DB_CONNECTION_SQL_SERVER)

        DB_SERVER = CONFIG['server']
        DB_NAME = CONFIG['database']

        DATABASE_URL = (
            f"mssql+pyodbc://{DB_SERVER}/{DB_NAME}?driver=ODBC+Driver+17+for+SQL+Server"
        )

        # Configuración para SQL Server con contraseña

        # DATABASE_URL = (
        #     f"mssql+pymssql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
        #     f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        # )
    else:
        CONFIG = json.loads(DB_CONNECTION)

        DB_USER = CONFIG['user']
        DB_PASSWORD = CONFIG['password']
        DB_HOST = CONFIG['host']
        DB_NAME = CONFIG['database']
        DB_PORT = CONFIG['port']

        DATABASE_URL = (
            f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
            f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
else:
    CONFIG = json.loads(DB_CONNECTION)

    DB_USER = CONFIG['user']
    DB_PASSWORD = CONFIG['password']
    DB_HOST = CONFIG['host']
    DB_NAME = CONFIG['database']
    DB_PORT = CONFIG['port']

    DATABASE_URL = (
        f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

# Crear engine
#engine = create_engine(DATABASE_URL, echo=True)

engine = create_engine(DATABASE_URL, 
                        echo=False,                # pon True solo si necesitas ver SQL
                        pool_pre_ping=True,        # reconecta si la conexión se cae
                        pool_recycle=1800,         # evita "MySQL server has gone away"
                        pool_size=5,
                        max_overflow=10,
                        future=True,                        
                        connect_args={
                            "ssl": {
                                "ca": ".\db\DigiCertGlobalRootG2.crt.pem"
                                #"ca": "/app/certs/mysql-ca-cert"
                            }
                        }
                        )

# Crear session factory
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

def init_db():
    from models.actividad import Actividad 
    from models.campo import Campo
    from models.actividadtransaccion import ActividadTransaccion
    from models.regla import Regla
    from models.riesgo import Riesgo
    from models.transaccion import Transaccion
    from models.riesgoactividadtransaccion import RiesgoActividadTransaccion
    from models.sapcampo import SapCampo
    from models.sapobjeto import SapObjeto
    from models.sapobjetocampo import SapObjetoCampo
    
    Base.metadata.create_all(bind=engine)