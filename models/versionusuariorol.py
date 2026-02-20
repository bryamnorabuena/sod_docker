from sqlalchemy import Column, String, DateTime, Integer 
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class VersionUsuarioRol(Base):
    __tablename__ = 'VersionUsuarioRol'

    Id = Column(Integer, primary_key=True, nullable=False)
    IdVersionUsuario = Column(Integer, nullable=False)
    IdSapRol = Column(Integer, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<VersionUsuarioRol(Id={self.Id}, IdVersionUsuario={self.IdVersionUsuario}, FechaCreacion={self.FechaCreacion})>"
