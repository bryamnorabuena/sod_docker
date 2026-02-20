from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Version(Base):
    __tablename__ = 'Version'

    Id = Column(Integer, primary_key=True)
    IdProceso = Column(Integer, nullable=False)
    Nombre = Column(String, nullable=False)
    Descripcion = Column(String, nullable=False)
    Completo = Column(Integer, nullable=False)
    Procesado = Column(Integer, nullable=False)
    Tiempo = Column(Integer, nullable=False)
    Cantidad = Column(Integer, nullable=False)
    CantidadSa = Column(Integer, nullable=False)
    CantidadAlto = Column(Integer, nullable=False)
    CantidadMedio = Column(Integer, nullable=False)
    CantidadBajo = Column(Integer, nullable=False)
    CantidadUsuario = Column(Integer, nullable=False)
    CantidadSinConflicto = Column(Integer, nullable=False)
    CantidadConConflicto = Column(Integer, nullable=False)
    CantidadRegla = Column(Integer, nullable=False)
    CantidadReglaSinConflicto = Column(Integer, nullable=False)
    CantidadReglaConConflicto = Column(Integer, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}