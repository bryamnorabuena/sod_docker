from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SapRolObjetoAutorizacion(Base):
    __tablename__ = 'SapRolObjetoAutorizacion'

    Id = Column(Integer, primary_key=True, nullable=False)
    IdMatrizSap = Column(Integer, nullable=False)
    IdSapRol = Column(Integer, nullable=False)
    IdSapObjetoProceso = Column(Integer, nullable=False)
    IdSapAutorizacion = Column(Integer, nullable=False)
    IdSapCampoProceso = Column(Integer, nullable=False)
    Desde = Column(String(40), nullable=False)
    Hasta = Column(String, nullable=False)  # Adjust the length as needed
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<SapRolObjetoAutorizacion(Id={self.Id}, IdSapRol={self.IdSapRol}, FechaCreacion={self.FechaCreacion})>"
