from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class VersionUsuario(Base):
    __tablename__ = 'VersionUsuario'

    Id = Column(Integer, primary_key=True, nullable=False)
    IdVersion = Column(Integer, nullable=False)
    IdUsuario = Column(Integer, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<VersionUsuario(Id={self.Id}, IdUsuario={self.IdUsuario}, FechaCreacion={self.FechaCreacion})>"
