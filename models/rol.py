from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Rol(Base):
    __tablename__ = 'Rol'  # nombre exacto de la tabla en MySQL

    Id = Column('Id',Integer, primary_key=True, autoincrement=True)
    IdTipoRol = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    Nombre = Column(Integer, nullable=False)
    Role = Column(Integer, nullable=False)
    Descripcion = Column(String, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=False)
    Estado = Column(Integer, nullable=False) 

    def __repr__(self):
        return f"<Rol(Id={self.Id})>"
