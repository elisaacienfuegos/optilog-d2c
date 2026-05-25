"""
Capa de presentación de la API (routers).

Define los endpoints HTTP. Cada uno recibe una sesión de base de datos por
inyección de dependencias (get_db), delega en la capa de repositorio y devuelve
los datos validados por los esquemas Pydantic.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import inventario_repo
from app.api.schemas import Almacen, Sku, Kpis

router = APIRouter()


@router.get("/almacenes", response_model=list[Almacen], tags=["Inventario"])
def get_almacenes(db: Session = Depends(get_db)):
    """Devuelve la lista de almacenes."""
    return inventario_repo.listar_almacenes(db)


@router.get("/skus", response_model=list[Sku], tags=["Inventario"])
def get_skus(limite: int = 100, db: Session = Depends(get_db)):
    """Devuelve el catálogo de SKUs (con su producto y familia)."""
    return inventario_repo.listar_skus(db, limite)


@router.get("/kpis", response_model=Kpis, tags=["KPIs"])
def get_kpis(db: Session = Depends(get_db)):
    """Devuelve métricas resumen del sistema."""
    return inventario_repo.contar_kpis(db)
