"""
Conexión a la base de datos mediante SQLAlchemy.

Crea el engine a partir de la URL de configuración y expone una dependencia
`get_db` que FastAPI inyecta en cada endpoint para obtener una sesión, cerrándola
automáticamente al terminar la petición.
"""
from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependencia de FastAPI: abre una sesión y la cierra al finalizar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
