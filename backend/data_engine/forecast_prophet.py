"""
Ajuste de un modelo Prophet a la demanda diaria de un (SKU, almacén).

Pipeline:
    1. Carga ventas.csv (formato largo) y filtra una serie (sku + warehouse).
    2. Agrega a frecuencia diaria y la deja en el formato que Prophet exige:
       un DataFrame con columnas 'ds' (fecha) e 'y' (valor).
    3. Parte temporalmente en train/test (las últimas N filas son test; NUNCA aleatorio).
    4. Ajusta Prophet con estacionalidad semanal y anual + festivos de campaña.
    5. Predice sobre el horizonte de test y calcula MAE, RMSE y MAPE.
    6. Guarda una gráfica (real vs. predicho) en data/processed/.

Uso:
    python forecast_prophet.py                          # SKU por defecto
    python forecast_prophet.py --sku VESTIDO-NEGRO-M --warehouse MAD
    python forecast_prophet.py --horizon 30
"""
from __future__ import annotations
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # backend sin ventana (para guardar a archivo)
import matplotlib.pyplot as plt
from prophet import Prophet


# --------------------------------------------------------------------------- #
# Métricas de evaluación
# --------------------------------------------------------------------------- #
def mae(y, yhat):
    return float(np.mean(np.abs(y - yhat)))

def rmse(y, yhat):
    return float(np.sqrt(np.mean((y - yhat) ** 2)))

def mape(y, yhat):
    # MAPE robusto: ignora los días con venta real 0 (evita división por cero)
    mask = y != 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((y[mask] - yhat[mask]) / y[mask])) * 100)


# --------------------------------------------------------------------------- #
# Festivos de campaña (los mismos que inyectó el generador)
# --------------------------------------------------------------------------- #
def build_holidays() -> pd.DataFrame:
    rows = []
    for year in range(2023, 2027):
        rows += [
            {"holiday": "black_friday", "ds": pd.Timestamp(f"{year}-11-27"),
             "lower_window": -3, "upper_window": 3},
            {"holiday": "rebajas_invierno", "ds": pd.Timestamp(f"{year}-01-07"),
             "lower_window": 0, "upper_window": 24},
            {"holiday": "rebajas_verano", "ds": pd.Timestamp(f"{year}-07-01"),
             "lower_window": 0, "upper_window": 30},
        ]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Carga y preparación de una serie
# --------------------------------------------------------------------------- #
def load_series(path: str, sku: str, warehouse: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    serie = df[(df["sku"] == sku) & (df["warehouse"] == warehouse)].copy()
    if serie.empty:
        # ayuda al usuario: lista algunos SKU válidos
        ejemplos = df["sku"].drop_duplicates().head(10).tolist()
        raise SystemExit(
            f"No hay datos para sku='{sku}', warehouse='{warehouse}'.\n"
            f"Ejemplos de SKU válidos: {ejemplos}\n"
            f"Almacenes válidos: {sorted(df['warehouse'].unique())}"
        )
    serie = serie.groupby("date", as_index=False)["units"].sum()
    serie = serie.rename(columns={"date": "ds", "units": "y"}).sort_values("ds")
    return serie


# --------------------------------------------------------------------------- #
# Principal
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../data/raw/ventas.csv")
    ap.add_argument("--sku", default="BLUSA-AZUL-M")
    ap.add_argument("--warehouse", default="MAD")
    ap.add_argument("--horizon", type=int, default=30, help="días de test/predicción")
    ap.add_argument("--out-dir", default="../data/processed")
    args = ap.parse_args()

    serie = load_series(args.data, args.sku, args.warehouse)
    print(f"Serie: {args.sku} @ {args.warehouse}  |  {len(serie)} días "
          f"({serie['ds'].min().date()} .. {serie['ds'].max().date()})")

    # partición temporal: últimas `horizon` filas como test
    h = args.horizon
    train, test = serie.iloc[:-h], serie.iloc[-h:]
    print(f"Train: {len(train)} días  |  Test: {len(test)} días")

    # modelo
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        seasonality_mode="multiplicative",
        changepoint_prior_scale=0.05,
        holidays=build_holidays(),
    )
    model.fit(train)

    # predicción sobre el horizonte de test
    future = model.make_future_dataframe(periods=h, freq="D")
    forecast = model.predict(future)

    # alinear predicción con test real
    pred = forecast.set_index("ds").loc[test["ds"]]["yhat"].to_numpy()
    pred = np.clip(pred, 0, None)  # la demanda no puede ser negativa
    y_true = test["y"].to_numpy()

    print("\n=== MÉTRICAS sobre el conjunto de test ===")
    print(f"  MAE : {mae(y_true, pred):.3f}")
    print(f"  RMSE: {rmse(y_true, pred):.3f}")
    print(f"  MAPE: {mape(y_true, pred):.1f}%")

    # gráfica real vs predicho
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(train["ds"].iloc[-90:], train["y"].iloc[-90:], color="#888",
            label="histórico (train)")
    ax.plot(test["ds"], y_true, color="#1f77b4", marker="o", ms=3,
            label="real (test)")
    ax.plot(test["ds"], pred, color="#FF5600", lw=2, label="predicción Prophet")
    band = forecast.set_index("ds").loc[test["ds"]]
    ax.fill_between(test["ds"], np.clip(band["yhat_lower"], 0, None),
                    band["yhat_upper"], color="#FF5600", alpha=0.15,
                    label="intervalo 80%")
    ax.set_title(f"Predicción de demanda — {args.sku} @ {args.warehouse}")
    ax.set_xlabel("fecha"); ax.set_ylabel("unidades/día"); ax.legend()
    fig.autofmt_xdate(); fig.tight_layout()
    fname = out / f"forecast_{args.sku}_{args.warehouse}.png"
    fig.savefig(fname, dpi=120)
    print(f"\nGráfica guardada en: {fname}")


if __name__ == "__main__":
    main()
