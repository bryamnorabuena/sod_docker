from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Riesgo(Base):
    __tablename__ = 'Riesgo'  # nombre exacto de la tabla en MySQL

    Id = Column(Integer, primary_key=True, autoincrement=True)
    IdRegla  = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    IdProcesoRiesgo = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    IdNivelRiesgo = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    IdTipoRiesgo = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    Codigo = Column(String(16), nullable=False)  # tamaño arbitrario, ajusta según necesidad
    Descripcion = Column(String(255), nullable=False, server_default='')  # tamaño arbitrario, ajusta según necesidad
    Observacion = Column(String(255), nullable=False, server_default='')  # tamaño arbitrario, ajusta según necesidad
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False)  # asumo que es un entero (estado de la actividad)

    def __repr__(self):
        return f"<Riesgo(Id={self.Id}, Codigo={self.Codigo})>"
