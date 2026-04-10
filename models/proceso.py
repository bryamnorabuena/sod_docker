from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Proceso(Base):
    __tablename__ = 'Proceso'  # nombre exacto de la tabla en MySQL

    Id = Column('Id', Integer, primary_key=True, autoincrement=True)
    IdRegla = Column(Integer, nullable=False)
    IdMatrizSap = Column(Integer, nullable=False)
    Nombre = Column(String(64), nullable=False)
    Descripcion = Column(String(128))
    FechaCorte = Column(DateTime, nullable=True)
    Procesado = Column(Integer, nullable=False, default=0)
    Tiempo = Column(Float, nullable=False, default=0)
    Cantidad = Column(Integer, nullable=False, default=0)
    CantidadSa = Column(Integer, nullable=False, default=0)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<Proceso(Id={self.Id}, Nombre={self.Nombre})>"
