from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class VersionUsuarioObjeto(Base):
    __tablename__ = 'VersionUsuarioObjeto'

    Id = Column(Integer, primary_key=True, nullable=False)
    IdVersionUsuario = Column(Integer, nullable=False)
    IdSapObjetoProceso = Column(Integer, nullable=False)
    IdSapCampoProceso = Column(Integer, nullable=False)
    Desde = Column(String, nullable=False)  # Adjust the length as needed
    Hasta = Column(String, nullable=False)  # Adjust the length as needed
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<VersionUsuarioObjeto(Id={self.Id}, IdVersionUsuario={self.IdVersionUsuario}, FechaCreacion={self.FechaCreacion})>"
    