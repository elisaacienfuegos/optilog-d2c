"""
Servicio de reaprovisionamiento.

Materializa la integración entre el motor de predicción y el módulo de inventario:
calcula el punto de reorden (ROP) de un SKU a partir de la demanda PREVISTA por el
modelo (no de medias históricas estáticas) y lo compara con el stock disponible para
decidir si procede emitir una alerta de reaprovisionamiento.

Fórmulas (Sección 1.2.1 de la memoria):
    SS  = z * sigma_demanda * sqrt(L)          (stock de seguridad)
    ROP = demanda_media * L + SS               (punto de reorden)

donde z es el cuantil normal del nivel de servicio, sigma_demanda la desviación típica
de la demanda diaria prevista, y L el plazo de entrega (lead time) en días.
"""
from __future__ import annotations
import math
import statistics

# cuantiles de la normal para niveles de servicio habituales
Z_POR_NIVEL = {0.90: 1.28, 0.95: 1.65, 0.975: 1.96, 0.99: 2.33}


def calcular_reorden(prediccion: list[dict], stock_disponible: int,
                     lead_time: int = 7, nivel_servicio: float = 0.95) -> dict:
    """
    A partir de la predicción de demanda (lista de puntos con 'demanda_prevista'),
    calcula el punto de reorden y decide si hay que reaprovisionar.
    """
    if not prediccion:
        raise ValueError("La predicción está vacía.")

    demandas = [p["demanda_prevista"] for p in prediccion]
    demanda_media = statistics.mean(demandas)
    # desviación típica de la demanda diaria prevista (0 si solo hay un punto)
    sigma = statistics.pstdev(demandas) if len(demandas) > 1 else 0.0

    z = Z_POR_NIVEL.get(round(nivel_servicio, 3), 1.65)

    stock_seguridad = z * sigma * math.sqrt(lead_time)
    punto_reorden = demanda_media * lead_time + stock_seguridad

    reaprovisionar = stock_disponible < punto_reorden
    # cantidad sugerida: lo que falta para cubrir el ROP, redondeado al alza
    cantidad_sugerida = max(0, math.ceil(punto_reorden - stock_disponible))

    return {
        "stock_disponible": stock_disponible,
        "demanda_media_diaria": round(demanda_media, 2),
        "desviacion_demanda": round(sigma, 2),
        "lead_time_dias": lead_time,
        "nivel_servicio": nivel_servicio,
        "stock_seguridad": round(stock_seguridad, 2),
        "punto_reorden": round(punto_reorden, 2),
        "reaprovisionar": reaprovisionar,
        "cantidad_sugerida": cantidad_sugerida if reaprovisionar else 0,
    }
