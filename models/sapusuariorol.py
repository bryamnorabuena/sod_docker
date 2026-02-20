from sqlalchemy import Column, Integer, SmallInteger, Enum, DateTime, CHAR
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SapUsuarioRol(Base):
    __tablename__ = 'SapUsuarioRol'

    Id = Column(Integer, primary_key=True, autoincrement=True)
    IdMatrizSap = Column(Integer, nullable=False)
    IdSapRol = Column(SmallInteger, nullable=False)
    IdUsuario = Column(SmallInteger, nullable=False)
    FechaInicio = Column(DateTime, nullable=False)
    FechaFin = Column(DateTime, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return '<SapUsuarioRol %r>' % self.Id

    def __init__(self, IdMatrizSap, IdSapRol, IdUsuario, FechaInicio, FechaFin, IdAppUserCreacion, IdAppUserActualizacion, FechaCreacion, FechaActualizacion, Estado):
        self.IdMatrizSap = IdMatrizSap
        self.IdSapRol = IdSapRol
        self.IdUsuario = IdUsuario
        self.FechaInicio = FechaInicio
        self.FechaFin = FechaFin
        self.IdAppUserCreacion = IdAppUserCreacion
        self.IdAppUserActualizacion = IdAppUserActualizacion
        self.FechaCreacion = FechaCreacion
        self.FechaActualizacion = FechaActualizacion
        self.Estado = Estado
