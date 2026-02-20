from sqlalchemy import Column, Integer, String, DateTime, SmallInteger
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class SapNivelOrganizacional(Base):
    __tablename__ = 'SapNivelOrganizacional'

    Id = Column(SmallInteger, primary_key=True, autoincrement=True)
    IdMatrizSap = Column(Integer, nullable=False)
    IdSapRol = Column(SmallInteger, nullable=False)
    NivelOrganizacional = Column(String(50), nullable=False)
    Desde = Column(String(10), nullable=False)
    Hasta = Column(String(10), nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}