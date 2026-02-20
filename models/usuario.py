from sqlalchemy import Column, Integer, SmallInteger, Enum, DateTime, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Usuario(Base):
    __tablename__ = 'Usuario'

    Id = Column(Integer, primary_key=True, nullable=False)
    Usuario = Column(String(32), nullable=False) 
    IdEmpresa = Column(Integer, nullable=False)    
    Nombre = Column(String(64), nullable=False, server_default="")
    Apellidos = Column(String(128), nullable=False, server_default="")
    Email = Column(String(128), nullable=False, server_default="")    
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=False)
    FechaCreacion = Column(DateTime, nullable=False)
    FechaActualizacion = Column(DateTime, nullable=False)
    Estado = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<Usuario(Id={self.Id}, Usuario={self.Usuario})>"
