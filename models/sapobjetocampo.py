from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class SapObjetoCampo(Base):
    __tablename__ = 'SapObjetoCampo'  # nombre exacto de la tabla en MySQL

    Id = Column("Id",Integer, primary_key=True, autoincrement=True)
    IdRegla = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    IdActividad = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    IdTransaccion = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    IdSapObjeto = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    IdSapCampo = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    Desde = Column(String(64), nullable=False)
    Hasta = Column(String(64), nullable=False)
    Condicional = Column(String(8), nullable=False)  # asumo que es un string (condición lógica)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False)  # asumo que es un entero (estado de la actividad)

    def __repr__(self):
        return f"<SapObjetoCampo(Id={self.Id})>"
