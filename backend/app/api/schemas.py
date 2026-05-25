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
