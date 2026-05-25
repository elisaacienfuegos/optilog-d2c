"""
Esquemas Pydantic: definen la forma de los datos que la API devuelve.

FastAPI usa estos modelos para validar las respuestas y para generar
automáticamente la documentación interactiva (OpenAPI / Swagger).
"""
from __future__ import annotations
from pydantic import BaseModel


class Almacen(BaseModel):
    id: int
    codigo: str
    ciudad: str
    direccion: str | None = None


class Sku(BaseModel):
    id: int
    codigo_sku: str
    color: str | None = None
    talla: str | None = None
    producto: str
    familia: str


class Kpis(BaseModel):
    productos: int
    skus: int
    almacenes: int
    registros_venta: int
    unidades_totales: int
    transportistas: int


# --- Predicción ---
class PuntoPrediccion(BaseModel):
    fecha: str
    demanda_prevista: float
    min: float
    max: float


class Prediccion(BaseModel):
    horizonte_dias: int
    dias_historico: int
    prediccion: list[PuntoPrediccion]


# --- Simulador ---
class EnvioRequest(BaseModel):
    peso_kg: float
    zona: str  # peninsula | baleares | canarias
    w_coste: float = 0.5
    w_plazo: float = 0.3
    w_fiab: float = 0.2


class CandidatoSimulador(BaseModel):
    transportista: str
    coste_eur: float
    plazo_dias: int
    fiabilidad: float
    C: float


class ResultadoSimulador(BaseModel):
    elegido: str
    coste_total_C: float
    justificacion: list[CandidatoSimulador]
