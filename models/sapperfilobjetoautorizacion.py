from sqlalchemy import Column, Integer, SmallInteger, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SapPerfilObjetoAutorizacion(Base):
    __tablename__ = 'SapPerfilObjetoAutorizacion'

    Id = Column(Integer, primary_key=True, autoincrement=True)
    IdMatrizSap = Column(Integer, nullable=False)
    IdSapPerfil = Column(SmallInteger, nullable=False)
    IdSapObjetoProceso = Column(SmallInteger, nullable=False)
    IdSapAutorizacion = Column(SmallInteger, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

def __init__(self, IdMatrizSap, IdSapPerfil, IdSapObjetoProceso, IdSapAutorizacion, IdAppUserCreacion, IdAppUserActualizacion, FechaCreacion, FechaActualizacion, Estado):
    self.IdMatrizSap = IdMatrizSap
    self.IdSapPerfil = IdSapPerfil
    self.IdSapObjetoProceso = IdSapObjetoProceso
    self.IdSapAutorizacion = IdSapAutorizacion
    self.IdAppUserCreacion = IdAppUserCreacion
    self.IdAppUserActualizacion = IdAppUserActualizacion
    self.FechaCreacion = FechaCreacion
    self.FechaActualizacion = FechaActualizacion
    self.Estado = Estado