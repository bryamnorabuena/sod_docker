from sqlalchemy import Column, Integer, BigInteger, DateTime, SmallInteger
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UsuarioTransaccionRol(Base):
    __tablename__ = 'UsuarioTransaccionRol'

    Id = Column(BigInteger, primary_key=True, autoincrement=True)
    IdProceso = Column(BigInteger, nullable=False)
    IdUsuario = Column(BigInteger, nullable=False)
    IdTransaccion = Column(BigInteger, nullable=False)
    IdSapRol = Column(BigInteger, nullable=False)
    IdAppUserCreacion = Column(BigInteger, nullable=False)
    IdAppUserActualizacion = Column(BigInteger, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(SmallInteger, nullable=False)
