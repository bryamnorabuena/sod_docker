from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Conflicto(Base):
    __tablename__ = 'Conflicto'

    Id = Column('Id', Integer, primary_key=True, autoincrement=True)
    IdVersion = Column(Integer, nullable=False)
    IdUsuario = Column(Integer, nullable=False)
    IdSapPerfil = Column(Integer, nullable=True)
    IdSapAutorizacion = Column(Integer, nullable=True)
    IdSapRol = Column(Integer, nullable=False)
    IdRiesgoActividadTransaccion = Column(Integer, nullable=False)
    IdRiesgo = Column(Integer, nullable=False)
    IdActividad = Column(Integer, nullable=False)
    IdTransaccion = Column(Integer, nullable=False)
    IdSapObjetoProceso = Column(Integer, nullable=True)
    IdSapCampoProceso = Column(Integer, nullable=True)
    Desde = Column(String(64), nullable=False)
    Hasta = Column(String(64), nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=True)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<Conflicto(Id={self.Id}, IdVersion={self.IdVersion})>"
