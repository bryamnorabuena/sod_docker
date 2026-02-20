from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

Columns = {
    "id": "Id",
    "nombre": "Nombre",
    "descripcion": "Descripcion",
    "archivo": "Archivo",
    "id_app_user_creacion": "IdAppUserCreacion",
    "id_app_user_actualizacion": "IdAppUserActualizacion",
    "fecha_creacion": "FechaCreacion",
    "fecha_actualizacion": "FechaActualizacion",
    "estado": "Estado"
}


class Regla(Base):
    __tablename__ = 'Regla'

    Id = Column(Columns["id"],Integer, primary_key=True, autoincrement=True)
    Nombre = Column(Columns["nombre"],String(64), nullable=False)
    Descripcion = Column(Columns["descripcion"],String(128))
    Archivo = Column(Columns["archivo"],String(128), nullable=True)
    IdAppUserCreacion = Column(Columns["id_app_user_creacion"],Integer, nullable=False)
    IdAppUserActualizacion = Column(Columns["id_app_user_actualizacion"],Integer, nullable=True)
    FechaCreacion = Column(Columns["fecha_creacion"],DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(Columns["fecha_actualizacion"],DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Columns["estado"],Integer, nullable=False)

    def __repr__(self):
        return f"<Regla(Id={self.Id}, Nombre={self.Nombre})>"
