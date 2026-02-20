from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class RiesgoActividadTransaccion(Base):
    __tablename__ = 'RiesgoActividadTransaccion'  # nombre exacto de la tabla en MySQL

    Id = Column('Id',Integer, primary_key=True, autoincrement=True)
    IdRiesgo = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    IdActividad = Column(Integer, nullable=False)
    IdTransaccion = Column(Integer, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False) 

    def __repr__(self):
        return f"<RiesgoActividadTransaccion(Id={self.Id}, IdRiesgo={self.IdRiesgo}, IdActividad={self.IdActividad}, IdTransaccion={self.IdTransaccion})>"
