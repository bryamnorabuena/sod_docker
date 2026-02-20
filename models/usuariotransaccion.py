from sqlalchemy import Column, Integer, SmallInteger, Enum, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UsuarioTransaccion(Base):
    __tablename__ = 'UsuarioTransaccion'

    Id = Column(Integer, primary_key=True, nullable=False)
    IdProceso = Column(Integer, nullable=False)
    IdUsuario = Column(Integer, nullable=False)
    IdTransaccion = Column(Integer, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<UsuarioTransaccion(Id={self.Id}, IdUsuario={self.IdUsuario}, FechaCreacion={self.FechaCreacion})>"
