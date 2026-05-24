"""
Generador de datos sintéticos de venta para la plataforma de optimización logística D2C.

Genera ventas diarias por (SKU, almacén) con un proceso generador conocido y controlado:
    venta(t) = base_sku * almacen_factor
               * (1 + tendencia(t))
               * estacionalidad_semanal(t)
               * estacionalidad_anual(t)
               * factor_campaña(t)
               + ruido
La demanda final se redondea a enteros >= 0. Algunos SKU se marcan como
"intermitentes" (muchos ceros) para disponer de casos difíciles en el análisis de errores.

Como el proceso es conocido, la validación (Cap. 4) puede comprobar si Prophet/SARIMA
recuperan los componentes inyectados. Salida: data/raw/ventas.csv (formato tidy/largo).

Uso:
    python generate_synthetic_data.py            # parámetros por defecto
    python generate_synthetic_data.py --seed 7   # otra semilla reproducible
"""
from __future__ import annotations
import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Parámetros de configuración (decisiones de diseño, documentadas en la memoria)
# --------------------------------------------------------------------------- #

ALMACENES = [
    # (codigo, ciudad, factor de volumen relativo)
    ("MAD", "Madrid", 1.00),       # almacén principal
    ("BCN", "Barcelona", 0.70),    # secundario
    ("LPA", "Las Palmas", 0.35),   # menor volumen, plazos de transporte mayores
]

# Familias de producto (catálogo de moda D2C). Cada familia tendrá varios SKU.
FAMILIAS = [
    "CAMISETA", "VESTIDO", "PICHI", "ABRIGO", "BIKINI", "AMERICANA",
    "FALDA", "JEANS", "JERSEY", "PANTALON", "BLUSA", "CHAQUETA",
]
COLORES = ["NEGRO", "BLANCO", "AZUL", "CAMEL", "VERDE", "ROJO"]
TALLAS = ["XS", "S", "M", "L", "XL"]

# Campañas: (mes, dia_inicio, dia_fin, multiplicador, etiqueta)
CAMPANAS = [
    (11, 24, 30, 3.5, "black_friday"),   # Black Friday (última semana noviembre)
    (12, 1, 5, 2.0, "cyber_monday"),     # arrastre post-BF / cyber
    (1, 7, 31, 2.2, "rebajas_invierno"), # rebajas de invierno
    (7, 1, 31, 2.0, "rebajas_verano"),   # rebajas de verano
]


@dataclass
class GenConfig:
    n_skus: int = 40
    years: int = 3
    end_date: str = "2026-05-01"   # fecha final del histórico
    seed: int = 42
    intermittent_frac: float = 0.20  # fracción de SKU con demanda intermitente
    noise_cv: float = 0.15           # coef. de variación del ruido gaussiano
    out_dir: str = "data/raw"


# --------------------------------------------------------------------------- #
# Construcción del catálogo de SKU
# --------------------------------------------------------------------------- #

def build_catalog(cfg: GenConfig, rng: np.random.Generator) -> pd.DataFrame:
    skus = set()
    rows = []
    while len(rows) < cfg.n_skus:
        fam = rng.choice(FAMILIAS)
        col = rng.choice(COLORES)
        tal = rng.choice(TALLAS)
        sku = f"{fam}-{col}-{tal}"
        if sku in skus:
            continue
        skus.add(sku)
        rows.append({
            "sku": sku,
            "familia": fam,
            "color": col,
            "talla": tal,
            # volumen base diario medio del SKU (unidades), heterogéneo entre productos
            "base": float(np.round(rng.uniform(0.5, 8.0), 2)),
            # tendencia anual relativa: -20% a +30% por año (ciclo de vida del producto)
            "trend_per_year": float(np.round(rng.uniform(-0.20, 0.30), 3)),
            # ¿demanda intermitente? (ventas esporádicas, muchos ceros)
            "intermittent": bool(rng.random() < cfg.intermittent_frac),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Componentes de la serie
# --------------------------------------------------------------------------- #

def weekly_factor(dates: pd.DatetimeIndex) -> np.ndarray:
    # Lun=0 ... Dom=6. Más venta entre semana, menos fin de semana.
    weekday_mult = np.array([1.05, 1.10, 1.10, 1.00, 0.95, 0.70, 0.65])
    return weekday_mult[dates.dayofweek.to_numpy()]


def annual_factor(dates: pd.DatetimeIndex) -> np.ndarray:
    # Onda anual: valle en verano-otoño, subida hacia fin de año.
    doy = dates.dayofyear.to_numpy()
    return 1.0 + 0.25 * np.sin(2 * np.pi * (doy - 80) / 365.25)


def campaign_factor(dates: pd.DatetimeIndex):
    mult = np.ones(len(dates))
    label = np.array([""] * len(dates), dtype=object)
    months = dates.month.to_numpy()
    days = dates.day.to_numpy()
    for m, d0, d1, k, lab in CAMPANAS:
        mask = (months == m) & (days >= d0) & (days <= d1)
        mult[mask] *= k
        label[mask] = lab
    return mult, label


# --------------------------------------------------------------------------- #
# Generación principal
# --------------------------------------------------------------------------- #

def generate(cfg: GenConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(cfg.seed)
    catalog = build_catalog(cfg, rng)

    end = pd.Timestamp(cfg.end_date)
    start = end - pd.DateOffset(years=cfg.years) + pd.Timedelta(days=1)
    dates = pd.date_range(start, end, freq="D")
    n_days = len(dates)

    wf = weekly_factor(dates)
    af = annual_factor(dates)
    cf, clabel = campaign_factor(dates)
    # tendencia temporal normalizada [0,1] a lo largo de todo el histórico
    t_norm = np.linspace(0.0, 1.0, n_days) * cfg.years  # en "años transcurridos"

    records = []
    for _, prod in catalog.iterrows():
        trend = 1.0 + prod["trend_per_year"] * t_norm  # crecimiento/decaimiento
        for code, city, wh_factor in ALMACENES:
            mu = (prod["base"] * wh_factor) * trend * wf * af * cf
            noise = rng.normal(0.0, cfg.noise_cv * np.maximum(mu, 1e-6))
            qty = np.maximum(0.0, mu + noise)
            if prod["intermittent"]:
                # apaga la venta en ~70% de los días (demanda esporádica)
                on = rng.random(n_days) > 0.70
                qty = qty * on
            qty = np.round(qty).astype(int)
            df_sku = pd.DataFrame({
                "date": dates,
                "sku": prod["sku"],
                "warehouse": code,
                "city": city,
                "units": qty,
                "campaign": clabel,
            })
            records.append(df_sku)

    ventas = pd.concat(records, ignore_index=True)
    return ventas, catalog


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-skus", type=int, default=40)
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--out-dir", type=str, default="data/raw")
    args = ap.parse_args()

    cfg = GenConfig(seed=args.seed, n_skus=args.n_skus, years=args.years, out_dir=args.out_dir)
    ventas, catalog = generate(cfg)

    out = Path(cfg.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ventas.to_csv(out / "ventas.csv", index=False)
    catalog.to_csv(out / "catalogo.csv", index=False)
    with open(out / "gen_config.json", "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2, ensure_ascii=False)

    # resumen por consola
    print(f"OK -> {out/'ventas.csv'}")
    print(f"  Filas: {len(ventas):,}")
    print(f"  Rango: {ventas['date'].min().date()} .. {ventas['date'].max().date()}")
    print(f"  SKUs: {ventas['sku'].nunique()}  |  Almacenes: {ventas['warehouse'].nunique()}")
    print(f"  Unidades totales: {int(ventas['units'].sum()):,}")
    print(f"  Media diaria/serie: {ventas['units'].mean():.2f}")
    print(f"  Intermitentes: {int(catalog['intermittent'].sum())}/{len(catalog)} SKU")


if __name__ == "__main__":
    main()
