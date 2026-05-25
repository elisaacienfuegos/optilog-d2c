"""
Capa de presentación de la API (routers).

Define los endpoints HTTP. Cada uno recibe una sesión de base de datos por
inyección de dependencias (get_db), delega en repositorios y servicios, y
devuelve los datos validados por los esquemas Pydantic.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import inventario_repo
from app.services import prediccion_service, simulador_service
from app.api.schemas import (
    Almacen, Sku, Kpis, Prediccion, EnvioRequest, ResultadoSimulador,
)

router = APIRouter()


# ----------------------------- Inventario / KPIs ---------------------------- #
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


@router.get("/transportistas", tags=["Logística"])
def get_transportistas(db: Session = Depends(get_db)):
    """Devuelve los transportistas con sus tarifas por zona."""
    return inventario_repo.listar_transportistas(db)


# ------------------------------- Predicción --------------------------------- #
@router.get("/prediccion/{sku}/{almacen}", response_model=Prediccion,
            tags=["Predicción"])
def get_prediccion(sku: str, almacen: str, horizonte: int = 30,
                   db: Session = Depends(get_db)):
    """
    Ejecuta Prophet sobre la serie histórica del (SKU, almacén) y devuelve la
    previsión de demanda para el horizonte indicado (por defecto 30 días).
    Nota: el ajuste de Prophet puede tardar unos segundos.
    """
    serie = inventario_repo.serie_historica(db, sku, almacen)
    if not serie:
        raise HTTPException(status_code=404,
                            detail=f"No hay histórico para SKU '{sku}' en almacén '{almacen}'.")
    try:
        return prediccion_service.predecir(serie, horizonte)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en la predicción: {e}")


# ------------------------------- Simulador ---------------------------------- #
@router.post("/simulador/seleccionar", response_model=ResultadoSimulador,
             tags=["Logística"])
def post_simulador(envio: EnvioRequest):
    """
    Selecciona el transportista óptimo para un envío (peso y zona) según la
    función de coste multicriterio, devolviendo la justificación de la decisión.
    """
    try:
        r = simulador_service.simular(
            envio.peso_kg, envio.zona,
            envio.w_coste, envio.w_plazo, envio.w_fiab,
        )
        return {
            "elegido": r["elegido"],
            "coste_total_C": r["coste_total_C"],
            "justificacion": r["justificacion"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
