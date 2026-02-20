from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Generica(Base):
    __tablename__ = 'Generica'

    Id = Column('Id', Integer, primary_key=True, autoincrement=True)
    Nombre = Column(String(64), nullable=False)
    Descripcion = Column(String(128))
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False)
    def __repr__(self):
        return f"<Generica(Id={self.Id}, Codigo={self.Codigo})>"
