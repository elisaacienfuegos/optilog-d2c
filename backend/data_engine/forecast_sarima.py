"""
Ajuste de un modelo SARIMA (referencia Box-Jenkins) a la demanda diaria de un (SKU, almacén).

SARIMA(p,d,q)(P,D,Q)_m con m=7 (estacionalidad semanal). En lugar de fijar los órdenes
a mano, se realiza una búsqueda en rejilla minimizando el criterio de información AIC,
que es la versión automatizada de la fase de "identificación" de la metodología Box-Jenkins.

Sirve como MODELO DE REFERENCIA para comparar contra Prophet (sección 4.3.2 de la memoria).
Calcula MAE/RMSE/MAPE con la misma partición temporal que el script de Prophet, de modo que
las métricas son directamente comparables.

Uso:
    python forecast_sarima.py
    python forecast_sarima.py --sku VESTIDO-VERDE-L --warehouse MAD
    python forecast_sarima.py --horizon 30
"""
from __future__ import annotations
import argparse
import itertools
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.tsa.statespace.sarimax import SARIMAX

warnings.filterwarnings("ignore")  # silencia avisos de convergencia durante la búsqueda

M = 7  # periodo estacional: semanal


# --------------------------------------------------------------------------- #
# Métricas (idénticas al script de Prophet, para comparar manzanas con manzanas)
# --------------------------------------------------------------------------- #
def mae(y, yhat):  return float(np.mean(np.abs(y - yhat)))
def rmse(y, yhat): return float(np.sqrt(np.mean((y - yhat) ** 2)))
def mape(y, yhat):
    mask = y != 0
    if mask.sum() == 0: return float("nan")
    return float(np.mean(np.abs((y[mask] - yhat[mask]) / y[mask])) * 100)


# --------------------------------------------------------------------------- #
# Carga de una serie (misma lógica que en el script de Prophet)
# --------------------------------------------------------------------------- #
def load_series(path, sku, warehouse) -> pd.Series:
    df = pd.read_csv(path, parse_dates=["date"])
    s = df[(df["sku"] == sku) & (df["warehouse"] == warehouse)].copy()
    if s.empty:
        ejemplos = df["sku"].drop_duplicates().head(10).tolist()
        raise SystemExit(
            f"No hay datos para sku='{sku}', warehouse='{warehouse}'.\n"
            f"Ejemplos válidos: {ejemplos}\n"
            f"Almacenes: {sorted(df['warehouse'].unique())}"
        )
    s = s.groupby("date")["units"].sum().sort_index()
    s = s.asfreq("D").fillna(0)  # frecuencia diaria explícita
    return s


# --------------------------------------------------------------------------- #
# Búsqueda de órdenes por AIC (rejilla reducida)
# --------------------------------------------------------------------------- #
def search_orders(train: pd.Series, verbose: bool = True):
    # rejilla deliberadamente pequeña para que sea rápido y documentable
    p = d = q = range(0, 2)        # 0..1
    P = D = Q = range(0, 2)        # 0..1
    best = {"aic": np.inf, "order": None, "seasonal": None}
    combos = list(itertools.product(p, d, q, P, D, Q))
    if verbose:
        print(f"Probando {len(combos)} combinaciones de órdenes (m={M})...")
    for (pp, dd, qq, PP, DD, QQ) in combos:
        try:
            res = SARIMAX(
                train, order=(pp, dd, qq), seasonal_order=(PP, DD, QQ, M),
                enforce_stationarity=False, enforce_invertibility=False,
            ).fit(disp=False)
            if res.aic < best["aic"]:
                best.update(aic=res.aic, order=(pp, dd, qq),
                            seasonal=(PP, DD, QQ, M))
        except Exception:
            continue
    return best


# --------------------------------------------------------------------------- #
# Línea base: media móvil estacional (mismo día de la semana, últimas semanas)
# --------------------------------------------------------------------------- #
def baseline_seasonal_naive(train: pd.Series, horizon: int) -> np.ndarray:
    # predice cada día futuro con la media de los últimos 4 mismos-día-de-semana
    last = train.iloc[-(4 * M):]
    by_dow = last.groupby(last.index.dayofweek).mean()
    future_idx = pd.date_range(train.index[-1] + pd.Timedelta(days=1),
                               periods=horizon, freq="D")
    return np.array([by_dow.get(d.dayofweek, train.mean()) for d in future_idx])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../data/raw/ventas.csv")
    ap.add_argument("--sku", default="BLUSA-AZUL-M")
    ap.add_argument("--warehouse", default="MAD")
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--out-dir", default="../data/processed")
    args = ap.parse_args()

    s = load_series(args.data, args.sku, args.warehouse)
    print(f"Serie: {args.sku} @ {args.warehouse}  |  {len(s)} días "
          f"({s.index.min().date()} .. {s.index.max().date()})")

    h = args.horizon
    train, test = s.iloc[:-h], s.iloc[-h:]
    print(f"Train: {len(train)} días  |  Test: {len(test)} días")

    best = search_orders(train)
    print(f"Mejor modelo por AIC: SARIMA{best['order']}{best['seasonal']}  "
          f"(AIC={best['aic']:.1f})")

    model = SARIMAX(train, order=best["order"], seasonal_order=best["seasonal"],
                    enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
    fc = model.get_forecast(steps=h)
    pred = np.clip(fc.predicted_mean.to_numpy(), 0, None)
    ci = fc.conf_int(alpha=0.20)  # intervalo 80%
    y_true = test.to_numpy()

    base = baseline_seasonal_naive(train, h)

    print("\n=== MÉTRICAS sobre el conjunto de test ===")
    print(f"{'Modelo':<22}{'MAE':>8}{'RMSE':>8}{'MAPE':>9}")
    print(f"{'SARIMA':<22}{mae(y_true,pred):>8.3f}{rmse(y_true,pred):>8.3f}{mape(y_true,pred):>8.1f}%")
    print(f"{'Baseline (naive)':<22}{mae(y_true,base):>8.3f}{rmse(y_true,base):>8.3f}{mape(y_true,base):>8.1f}%")

    # gráfica
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(train.index[-90:], train.iloc[-90:], color="#888", label="histórico (train)")
    ax.plot(test.index, y_true, color="#1f77b4", marker="o", ms=3, label="real (test)")
    ax.plot(test.index, pred, color="#2ca02c", lw=2, label="predicción SARIMA")
    ax.fill_between(test.index, np.clip(ci.iloc[:, 0], 0, None), ci.iloc[:, 1],
                    color="#2ca02c", alpha=0.15, label="intervalo 80%")
    ax.set_title(f"SARIMA{best['order']}{best['seasonal']} — {args.sku} @ {args.warehouse}")
    ax.set_xlabel("fecha"); ax.set_ylabel("unidades/día"); ax.legend()
    fig.autofmt_xdate(); fig.tight_layout()
    fname = out / f"sarima_{args.sku}_{args.warehouse}.png"
    fig.savefig(fname, dpi=120)
    print(f"\nGráfica guardada en: {fname}")


if __name__ == "__main__":
    main()
