from sqlalchemy import Column, Integer, SmallInteger, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SapUsuarioPerfil(Base):
    __tablename__ = 'SapUsuarioPerfil'

    Id = Column('Id',Integer, primary_key=True, autoincrement=True)  # MEDIUMINT UNSIGNED
    IdMatrizSap = Column(Integer, nullable=False)
    IdSapPerfil = Column(Integer, nullable=False)
    IdUsuario = Column(Integer, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<SapUsuarioPerfil(Id={self.Id}, IdMatrizSap={self.IdMatrizSap}, IdSapPerfil={self.IdSapPerfil})>"
