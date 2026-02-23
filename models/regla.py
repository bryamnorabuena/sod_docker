from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

from sqlalchemy.sql.sqltypes import Double

Base = declarative_base()

Columns = {
    "id": "Id",
    "nombre": "Nombre",
    "descripcion": "Descripcion",
    "archivo": "Archivo",
    "tiempo": "Tiempo",
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
    Descripcion = Column(Columns["descripcion"],String(128), nullable=False, server_default='')
    Archivo = Column(Columns["archivo"],String(128), nullable=True)
    Tiempo = Column(Columns["tiempo"],Double, nullable=True, server_default='0')  # nuevo campo para almacenar el tiempo de ejecución
    IdAppUserCreacion = Column(Columns["id_app_user_creacion"],Integer, nullable=False)
    IdAppUserActualizacion = Column(Columns["id_app_user_actualizacion"],Integer, nullable=True)
    FechaCreacion = Column(Columns["fecha_creacion"],DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(Columns["fecha_actualizacion"],DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Columns["estado"],Integer, nullable=False)

    def __repr__(self):
        return f"<Regla(Id={self.Id}, Nombre={self.Nombre})>"
