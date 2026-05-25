"""
Carga de los datos sintéticos (CSV) a la base de datos PostgreSQL `optilog`.

Rellena las tablas del catálogo y el histórico de venta:
    1. producto         (artículo conceptual, derivado del SKU sin la talla)
    2. sku              (variante vendible)
    3. almacen          (los 3 almacenes definidos en el generador)
    4. historico_venta  (las series temporales de demanda)

Requisitos:
    - Haber creado la base de datos `optilog` y ejecutado schema.sql.
    - pip install psycopg2-binary pandas

Uso (desde backend/, con el venv activo):
    python data_engine\\load_to_db.py --password TU_PASSWORD
    python data_engine\\load_to_db.py --password TU_PASSWORD --host localhost --port 5432
"""
from __future__ import annotations
import argparse
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


# Direcciones de ejemplo para los almacenes (datos de relleno coherentes).
ALMACEN_DIRECCIONES = {
    "MAD": "Calle Logística 1, Madrid",
    "BCN": "Carrer de la Logística 2, Barcelona",
    "LPA": "Calle del Puerto 3, Las Palmas",
}


def producto_desde_sku(codigo_sku: str) -> str:
    # "VESTIDO-VERDE-L" -> producto "VESTIDO-VERDE" (quita la última parte, la talla)
    partes = codigo_sku.split("-")
    return "-".join(partes[:-1]) if len(partes) > 1 else codigo_sku


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--password", required=True, help="contraseña del usuario postgres")
    ap.add_argument("--user", default="postgres")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", default="5432")
    ap.add_argument("--dbname", default="optilog")
    ap.add_argument("--data-dir", default="../data/raw")
    args = ap.parse_args()

    data = Path(args.data_dir)
    catalogo = pd.read_csv(data / "catalogo.csv")
    ventas = pd.read_csv(data / "ventas.csv", parse_dates=["date"])

    conn = psycopg2.connect(
        dbname=args.dbname, user=args.user, password=args.password,
        host=args.host, port=args.port,
    )
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # ----- 1. PRODUCTOS (únicos, derivados del SKU) -----
        catalogo["producto_nombre"] = catalogo["sku"].map(producto_desde_sku)
        productos = (catalogo[["producto_nombre", "familia"]]
                     .drop_duplicates()
                     .reset_index(drop=True))
        execute_values(
            cur,
            "INSERT INTO producto (nombre, familia) VALUES %s "
            "ON CONFLICT DO NOTHING RETURNING id, nombre",
            [(r.producto_nombre, r.familia) for r in productos.itertuples()],
        )
        # mapa nombre_producto -> id  (reconsultamos para tenerlos todos)
        cur.execute("SELECT id, nombre FROM producto")
        prod_id = {nombre: pid for pid, nombre in cur.fetchall()}
        print(f"Productos insertados: {len(prod_id)}")

        # ----- 2. SKUs -----
        sku_rows = [
            (prod_id[producto_desde_sku(r.sku)], r.sku, r.color, r.talla)
            for r in catalogo.itertuples()
        ]
        execute_values(
            cur,
            "INSERT INTO sku (producto_id, codigo_sku, color, talla) VALUES %s "
            "ON CONFLICT (codigo_sku) DO NOTHING",
            sku_rows,
        )
        cur.execute("SELECT id, codigo_sku FROM sku")
        sku_id = {codigo: sid for sid, codigo in cur.fetchall()}
        print(f"SKUs insertados: {len(sku_id)}")

        # ----- 3. ALMACENES -----
        almacenes = ventas[["warehouse", "city"]].drop_duplicates()
        alm_rows = [
            (r.warehouse, r.city, ALMACEN_DIRECCIONES.get(r.warehouse, ""))
            for r in almacenes.itertuples()
        ]
        execute_values(
            cur,
            "INSERT INTO almacen (codigo, ciudad, direccion) VALUES %s "
            "ON CONFLICT (codigo) DO NOTHING",
            alm_rows,
        )
        cur.execute("SELECT id, codigo FROM almacen")
        alm_id = {codigo: aid for aid, codigo in cur.fetchall()}
        print(f"Almacenes insertados: {len(alm_id)}")

        # ----- 4. HISTÓRICO DE VENTA (inserción masiva) -----
        hist_rows = [
            (sku_id[r.sku], alm_id[r.warehouse], r.date.date(), int(r.units))
            for r in ventas.itertuples()
        ]
        # page_size grande = menos viajes a la BD = más rápido
        execute_values(
            cur,
            "INSERT INTO historico_venta (sku_id, almacen_id, fecha, unidades) VALUES %s "
            "ON CONFLICT (sku_id, almacen_id, fecha) DO NOTHING",
            hist_rows,
            page_size=5000,
        )
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM historico_venta")
        total = cur.fetchone()[0]
        print(f"Filas en historico_venta: {total:,}")
        print("\nCarga completada correctamente.")

    except Exception as e:
        conn.rollback()
        print("ERROR — se deshizo la carga (rollback):", e)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
