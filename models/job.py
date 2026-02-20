from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Job(Base):
    __tablename__ = 'Job'

    Id = Column('Id', Integer, primary_key=True, autoincrement=True)
    IdJob = Column(Integer, nullable=False)
    IdUsuario = Column(Integer, nullable=False)
    Nombre = Column(String(50), nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False)
    def __repr__(self):
        return f"<Job(Id={self.Id}, IdJob={self.IdJob})>"
