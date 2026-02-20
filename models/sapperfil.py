from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SapPerfil(Base):
    __tablename__ = 'SapPerfil'

    Id = Column(Integer, primary_key=True)
    IdMatrizSap = Column(Integer, nullable=False)
    IdPadre = Column(Integer, nullable=False)
    Nombre = Column(String(64), nullable=False)
    Descripcion = Column(String(256), nullable=True)  # tamaño 0, pero es CHAR(0), posible string vacío
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)
