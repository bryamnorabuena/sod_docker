from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SapCampoOrganizacional(Base):
    __tablename__ = 'SapCampoOrganizacional'

    Id = Column(Integer, primary_key=True, autoincrement=True)  # ENUM de valores numéricos → Integer fijo
    IdMatrizSap = Column(Integer, nullable=False)
    Campo = Column(String(50), nullable=False)
    Variable = Column(String(50), nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
