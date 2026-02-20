from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Transaccion(Base):
    __tablename__ = 'Transaccion'  # nombre exacto de la tabla en MySQL

    Id = Column("Id",Integer, primary_key=True, autoincrement=True)
    IdRegla  = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    IdSistema = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    Padre = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    Nivel = Column(Integer, nullable=False)  # asumo que es un entero (nivel de la transacción)
    Codigo = Column(String(64), nullable=False)  # tamaño arbitrario, ajusta según necesidad
    Nombre = Column(String(128), nullable=False)    
    Descripcion = Column(String(512), nullable=False, default="")  # en caso de Null grabar ""
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False)  # asumo que es un entero (estado de la actividad)

    def __repr__(self):
        return f"<Transaccion(Id={self.Id}, Codigo={self.Codigo})>"
