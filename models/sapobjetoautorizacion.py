from sqlalchemy import Column, Integer, DateTime, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SapObjetoAutorizacion(Base):
    __tablename__ = 'SapObjetoAutorizacion'

    Id = Column(Integer, primary_key=True, autoincrement=True)
    IdMatrizSap = Column(Integer, nullable=False)
    IdSapObjetoProceso = Column(Integer, nullable=False)
    IdSapAutorizacion = Column(Integer, nullable=False)
    IdSapCampoProceso = Column(Integer, nullable=False)
    Desde = Column(String(64), nullable=False)
    Hasta = Column(String(64), nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)
