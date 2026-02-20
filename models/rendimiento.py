from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Rendimiento(Base):
    __tablename__ = 'Rendimiento'

    Id = Column('Id', Integer, primary_key=True, autoincrement=True)
    IdProceso = Column(Integer, nullable=False)
    Tiempo = Column(Float, nullable=False)
    Errores = Column(Integer, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<Rendimiento(Id={self.Id}, Tiempo={self.Tiempo}, Errores={self.Errores})>"
