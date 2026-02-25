import json
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import quote_plus
from utils.environment import get_environment

try:
    from utils.environment import get_environment
except Exception:
    get_environment = lambda *args, **kwargs: None  # respaldo inofensivo

def _get(name, default=None):
    # Prioriza env del contenedor (lo que define el Job en Azure)
    return os.getenv(name) or get_environment(name) or default

# En Job no necesitamos APP_ENV para nada; define un valor por defecto estable
FLASK_ENV = _get("APP_ENV", "production")

CONFIG_TYPE = _get("DB_CONNECTION_TYPE", "MYSQL")
DB_CONNECTION = _get("DB_CONNECTION")
DB_CONNECTION_SQL_SERVER = _get("DB_CONNECTION_SQL_SERVER")

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
                        pool_size=18,
                        max_overflow=20,
                        future=True,                        
                        connect_args={
                            "ssl": {
                                "ca": "/app/certs/mysql-ca-cert"
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