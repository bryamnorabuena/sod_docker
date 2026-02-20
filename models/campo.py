from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Campo(Base):
    __tablename__ = 'Campo'  # nombre exacto de la tabla en MySQL

    Id = Column('Id', Integer, primary_key=True, autoincrement=True)
    IdGenerica = Column(Integer, nullable=False)  # asumo que es un entero (clave foránea?)
    Nombre = Column(String(64), nullable=False)
    Descripcion = Column(String(128))  # tamaño arbitrario, ajusta según necesidad
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<Campo(Id={self.Id}, Nombre={self.Nombre})>"
