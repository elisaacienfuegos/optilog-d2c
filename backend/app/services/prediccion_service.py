"""
Servicio de predicción de demanda.

Encapsula el ajuste de Prophet sobre la serie histórica de un (SKU, almacén)
obtenida de la base de datos, y devuelve la previsión para un horizonte dado.
Reutiliza la misma configuración de modelo que el script data_engine/forecast_prophet.py
(estacionalidad multiplicativa, festivos de campaña, predicciones no negativas).
"""
from __future__ import annotations
import warnings
import pandas as pd
from prophet import Prophet

warnings.filterwarnings("ignore")


def _festivos() -> pd.DataFrame:
    rows = []
    for year in range(2023, 2028):
        rows += [
            {"holiday": "black_friday", "ds": pd.Timestamp(f"{year}-11-27"),
             "lower_window": -3, "upper_window": 3},
            {"holiday": "rebajas_invierno", "ds": pd.Timestamp(f"{year}-01-07"),
             "lower_window": 0, "upper_window": 24},
            {"holiday": "rebajas_verano", "ds": pd.Timestamp(f"{year}-07-01"),
             "lower_window": 0, "upper_window": 30},
        ]
    return pd.DataFrame(rows)


def predecir(serie: list[dict], horizonte: int = 30) -> dict:
    """
    Ajusta Prophet a la serie [(fecha, unidades), ...] y predice `horizonte` días.
    Devuelve la previsión con su intervalo de confianza.
    """
    if not serie:
        raise ValueError("La serie histórica está vacía: SKU o almacén inexistente.")

    df = pd.DataFrame(serie).rename(columns={"fecha": "ds", "unidades": "y"})
    df["ds"] = pd.to_datetime(df["ds"])

    modelo = Prophet(
        weekly_seasonality=True,
        yearly_seasonality=True,
        daily_seasonality=False,
        seasonality_mode="multiplicative",
        holidays=_festivos(),
        changepoint_prior_scale=0.05,
    )
    modelo.fit(df)

    futuro = modelo.make_future_dataframe(periods=horizonte)
    fc = modelo.predict(futuro)

    # nos quedamos solo con el tramo predicho (el futuro), truncando a no negativo
    pred = fc.tail(horizonte)[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    pred["yhat"] = pred["yhat"].clip(lower=0)
    pred["yhat_lower"] = pred["yhat_lower"].clip(lower=0)
    pred["yhat_upper"] = pred["yhat_upper"].clip(lower=0)

    return {
        "horizonte_dias": horizonte,
        "dias_historico": len(df),
        "prediccion": [
            {
                "fecha": r.ds.date().isoformat(),
                "demanda_prevista": round(float(r.yhat), 2),
                "min": round(float(r.yhat_lower), 2),
                "max": round(float(r.yhat_upper), 2),
            }
            for r in pred.itertuples()
        ],
    }
