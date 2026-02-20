from sqlalchemy import Column, Integer, SmallInteger, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SapUsuario(Base):
    __tablename__ = 'SapUsuario'

    Id = Column(Integer, primary_key=True, nullable=False)
    IdMatrizSap = Column(Integer, nullable=False)
    IdUsuario = Column(Integer, nullable=False)
    FechaInicio = Column(DateTime, nullable=False)
    FechaFin = Column(DateTime, nullable=False)
    Uflag = Column(Integer, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<SapUsuario(Id={self.Id}, IdUsuario={self.IdUsuario}, FechaCreacion={self.FechaCreacion})>"
