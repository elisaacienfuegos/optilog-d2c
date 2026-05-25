"""
Carga de los transportistas y sus tarifas (mock) en la base de datos `optilog`.

Inserta los cuatro transportistas con perfiles genéricos (Express, Estándar, Económico,
Low-cost) y sus tarifas por zona, usando los MISMOS valores que el simulador logístico
(simulator/simulador.py) para mantener la coherencia entre la lógica y la base de datos.

Nota: el esquema de la tabla `tarifa` tiene una única columna de coste (coste_base). Para
reflejar el modelo del simulador (coste = base + por_kg * peso), se almacena el coste_base
y el coste por kg se documenta como atributo del simulador. Aquí se persiste coste_base y
plazo_dias por zona, suficiente para que la API y el dashboard muestren el catálogo.

Uso (desde backend/, con el venv activo):
    python data_engine\\load_carriers.py --password TU_PASSWORD
"""
from __future__ import annotations
import argparse
import psycopg2
from psycopg2.extras import execute_values


# (nombre, fiabilidad, [(zona, coste_base, plazo_dias), ...])
TRANSPORTISTAS = [
    ("Express",   0.97, [("peninsula", 6.50, 1), ("baleares", 9.00, 2), ("canarias", 14.00, 3)]),
    ("Estándar",  0.92, [("peninsula", 4.50, 2), ("baleares", 6.50, 4), ("canarias", 10.00, 6)]),
    ("Económico", 0.88, [("peninsula", 3.20, 3), ("baleares", 5.00, 5), ("canarias",  8.00, 8)]),
    ("Low-cost",  0.80, [("peninsula", 2.50, 4), ("baleares", 4.00, 7), ("canarias",  6.50, 10)]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--password", required=True)
    ap.add_argument("--user", default="postgres")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", default="5432")
    ap.add_argument("--dbname", default="optilog")
    args = ap.parse_args()

    conn = psycopg2.connect(dbname=args.dbname, user=args.user, password=args.password,
                            host=args.host, port=args.port)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        for nombre, fiab, tarifas in TRANSPORTISTAS:
            cur.execute(
                "INSERT INTO transportista (nombre, fiabilidad) VALUES (%s, %s) "
                "ON CONFLICT (nombre) DO UPDATE SET fiabilidad = EXCLUDED.fiabilidad "
                "RETURNING id",
                (nombre, fiab),
            )
            tid = cur.fetchone()[0]
            execute_values(
                cur,
                "INSERT INTO tarifa (transportista_id, zona, coste_base, plazo_dias) VALUES %s",
                [(tid, zona, coste, plazo) for (zona, coste, plazo) in tarifas],
            )
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM transportista")
        nt = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tarifa")
        ntar = cur.fetchone()[0]
        print(f"Transportistas insertados: {nt}")
        print(f"Tarifas insertadas: {ntar}")
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
