"""
Capa de repositorios: acceso a datos.

Encapsula las consultas SQL a la base de datos. Las capas superiores (servicios,
routers) no escriben SQL directamente, sino que llaman a estas funciones. Esto
aísla el acceso a datos y facilita su mantenimiento o sustitución.
"""
from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.orm import Session


def listar_almacenes(db: Session) -> list[dict]:
    filas = db.execute(text(
        "SELECT id, codigo, ciudad, direccion FROM almacen ORDER BY codigo"
    )).mappings().all()
    return [dict(f) for f in filas]


def listar_skus(db: Session, limite: int = 100) -> list[dict]:
    filas = db.execute(text(
        "SELECT s.id, s.codigo_sku, s.color, s.talla, p.nombre AS producto, p.familia "
        "FROM sku s JOIN producto p ON p.id = s.producto_id "
        "ORDER BY s.codigo_sku LIMIT :lim"
    ), {"lim": limite}).mappings().all()
    return [dict(f) for f in filas]


def contar_kpis(db: Session) -> dict:
    n_productos = db.execute(text("SELECT COUNT(*) FROM producto")).scalar_one()
    n_skus      = db.execute(text("SELECT COUNT(*) FROM sku")).scalar_one()
    n_almacenes = db.execute(text("SELECT COUNT(*) FROM almacen")).scalar_one()
    n_ventas    = db.execute(text("SELECT COUNT(*) FROM historico_venta")).scalar_one()
    total_uds   = db.execute(text("SELECT COALESCE(SUM(unidades),0) FROM historico_venta")).scalar_one()
    n_transp    = db.execute(text("SELECT COUNT(*) FROM transportista")).scalar_one()
    return {
        "productos": n_productos,
        "skus": n_skus,
        "almacenes": n_almacenes,
        "registros_venta": n_ventas,
        "unidades_totales": int(total_uds),
        "transportistas": n_transp,
    }
