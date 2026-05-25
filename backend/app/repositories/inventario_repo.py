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


def serie_historica(db: Session, codigo_sku: str, codigo_almacen: str) -> list[dict]:
    """Devuelve la serie temporal (fecha, unidades) de un SKU en un almacén."""
    filas = db.execute(text(
        "SELECT h.fecha, h.unidades "
        "FROM historico_venta h "
        "JOIN sku s ON s.id = h.sku_id "
        "JOIN almacen a ON a.id = h.almacen_id "
        "WHERE s.codigo_sku = :sku AND a.codigo = :alm "
        "ORDER BY h.fecha"
    ), {"sku": codigo_sku, "alm": codigo_almacen}).mappings().all()
    return [dict(f) for f in filas]


def listar_transportistas(db: Session) -> list[dict]:
    """Devuelve transportistas con sus tarifas."""
    filas = db.execute(text(
        "SELECT t.nombre, t.fiabilidad, ta.zona, ta.coste_base, ta.plazo_dias "
        "FROM transportista t JOIN tarifa ta ON ta.transportista_id = t.id "
        "ORDER BY t.fiabilidad DESC, ta.zona"
    )).mappings().all()
    return [dict(f) for f in filas]


def stock_disponible(db: Session, codigo_sku: str, codigo_almacen: str) -> int | None:
    """Devuelve el stock disponible de un SKU en un almacén, o None si no existe la fila."""
    fila = db.execute(text(
        "SELECT st.disponible "
        "FROM stock st "
        "JOIN sku s ON s.id = st.sku_id "
        "JOIN almacen a ON a.id = st.almacen_id "
        "WHERE s.codigo_sku = :sku AND a.codigo = :alm"
    ), {"sku": codigo_sku, "alm": codigo_almacen}).scalar()
    return fila
