import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import quote_plus
from utils.environment import get_environment

# Configuración de la base de datos
FLASK_ENV = get_environment("APP_ENV", "local")

if FLASK_ENV == "local":
    CONFIG_TYPE = get_environment('DB_CONNECTION_TYPE', 'MYSQL').upper()
    PATH_PEM = get_environment('PATH_PEM', 'DigiCertGlobalRootG2.crt.pem')

    if CONFIG_TYPE == 'SQL_SERVER':
        CONFIG = json.loads(get_environment('DB_CONNECTION_SQL_SERVER'))

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
        CONFIG = json.loads(get_environment('DB_CONNECTION'))

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
    CONFIG = json.loads(get_environment('DB_CONNECTION'))

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
                                "ca": PATH_PEM
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