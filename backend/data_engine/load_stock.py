"""
Carga de stock inicial en la tabla `stock`.

Genera un nivel de stock disponible inicial para cada par (SKU, almacén) basado en la
demanda media histórica del SKU, de modo que el inventario de partida sea realista (en
torno a unas semanas de cobertura). El stock reservado y en tránsito se inicializan a 0.
Semilla fija para reproducibilidad.

Uso (desde backend/, con el venv activo):
    python data_engine\\load_stock.py --password TU_PASSWORD
"""
from __future__ import annotations
import argparse
import numpy as np
import psycopg2
from psycopg2.extras import execute_values


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--password", required=True)
    ap.add_argument("--user", default="postgres")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", default="5432")
    ap.add_argument("--dbname", default="optilog")
    ap.add_argument("--dias-cobertura", type=int, default=14,
                    help="Semanas de cobertura objetivo para el stock inicial.")
    args = ap.parse_args()

    rng = np.random.default_rng(42)
    conn = psycopg2.connect(dbname=args.dbname, user=args.user, password=args.password,
                            host=args.host, port=args.port)
    cur = conn.cursor()
    try:
        # demanda media diaria por (sku, almacen) a partir del histórico
        cur.execute("""
            SELECT sku_id, almacen_id, AVG(unidades) AS media
            FROM historico_venta
            GROUP BY sku_id, almacen_id
        """)
        filas = cur.fetchall()

        registros = []
        for sku_id, almacen_id, media in filas:
            media = float(media or 0)
            # stock inicial = cobertura objetivo * demanda media, con algo de variación
            base = media * args.dias_cobertura
            disponible = max(0, int(rng.normal(base, base * 0.2)))
            registros.append((sku_id, almacen_id, disponible, 0, 0))

        execute_values(cur,
            "INSERT INTO stock (sku_id, almacen_id, disponible, reservado, en_transito) "
            "VALUES %s ON CONFLICT (sku_id, almacen_id) DO UPDATE SET disponible = EXCLUDED.disponible",
            registros)
        conn.commit()

        cur.execute("SELECT COUNT(*), SUM(disponible) FROM stock")
        n, total = cur.fetchone()
        print(f"Filas de stock cargadas: {n}")
        print(f"Unidades disponibles totales: {total}")
        print("\nCarga completada correctamente.")
    except Exception as e:
        conn.rollback()
        print("ERROR — rollback:", e)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
