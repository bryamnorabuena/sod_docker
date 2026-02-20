from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class ActividadTransaccion(Base):
    __tablename__ = 'ActividadTransaccion'  # nombre exacto de la tabla en MySQL

    Id = Column("Id",Integer, primary_key=True, autoincrement=True)
    IdActividad = Column(Integer, nullable=False)
    IdTransaccion = Column(Integer, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False) 

    def __repr__(self):
        return f"<ActividadTransaccion(Id={self.Id}, IdActividad={self.IdActividad}, IdTransaccion={self.IdTransaccion})>"
