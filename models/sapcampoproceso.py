from sqlalchemy import Column, Integer, SmallInteger, String, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
import enum
import datetime

Base = declarative_base()

class SapCampoProceso(Base):
    __tablename__ = 'SapCampoProceso'

    Id = Column(Integer, primary_key=True, autoincrement=True)  # Puede cambiar a Integer si se requiere
    IdMatrizSap = Column(Integer, nullable=False)
    Nombre = Column(String(64), nullable=False)
    Descripcion = Column(String(255), nullable=True)  # Antes CHAR(0), ajustado
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    Estado = Column(Integer, nullable=False)
