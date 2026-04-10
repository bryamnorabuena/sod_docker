from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class AppUserRol(Base):
    __tablename__ = 'AppUserRol'  # nombre exacto de la tabla en MySQL

    Id = Column('Id', Integer, primary_key=True, autoincrement=True)
    IdAppUser = Column(Integer, nullable=False)
    IdRol = Column(Integer, nullable=False)
    IdAppUserCreacion = Column(Integer, nullable=False)
    IdAppUserActualizacion = Column(Integer, nullable=True)
    FechaCreacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    FechaActualizacion = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    Estado = Column(Integer, nullable=False, server_default='1')
    # RolData = relationship("Rol", backref="UserRoles", lazy="joined")

    def __repr__(self):
        return f"<Appuserrol(Id={self.Id}, IdAppUser={self.IdAppUser})>"
