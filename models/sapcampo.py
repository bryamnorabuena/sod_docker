from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class SapCampo(Base):
    __tablename__ = 'SapCampo'  # nombre exacto de la tabla en MySQL

    Id = Column("Id",Integer, primary_key=True, autoincrement=True)
    IdRegla = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    IdSistema = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    Nombre = Column(String(64), nullable=False)
    Descripcion = Column(String(255),default="")  # tamaño arbitrario, ajusta según necesidad
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False)  # asumo que es un entero (estado de la actividad)

    def __repr__(self):
        return f"<SapCampo(Id={self.Id}, Nombre={self.Nombre})>"
