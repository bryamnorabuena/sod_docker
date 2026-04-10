from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class AppUser(Base):
    __tablename__ = 'AppUser'  # nombre exacto de la tabla en MySQL

    Id = Column('Id', Integer, primary_key=True, autoincrement=True)
    Nombre = Column(String(64), nullable=False)
    Apellidos = Column(String(128), nullable=False)
    UserName = Column(String(32), nullable=False, unique=True)
    Password = Column(String(255), nullable=False)
    Email = Column(String(128), nullable=False, unique=True)
    Activo = Column(Integer, nullable=False, default=1)  # 1 para activo, 0 para inactivo
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False, default=1)  # Estado del usuario    

    def __repr__(self):
        return f"<Appuser(Id={self.Id}, UserName={self.UserName})>"
