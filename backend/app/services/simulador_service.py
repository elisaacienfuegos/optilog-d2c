"""
Servicio del simulador logístico.

Envuelve la lógica de selección de transportista (simulador_core) para exponerla
desde la API. Usa el catálogo de transportistas mock definido en el core.
"""
from __future__ import annotations
from app.services.simulador_core import (
    catalogo_transportistas, seleccionar_transportista, Envio, Pesos,
)


def simular(peso_kg: float, zona: str,
            w_coste: float = 0.5, w_plazo: float = 0.3, w_fiab: float = 0.2) -> dict:
    transportistas = catalogo_transportistas()
    pesos = Pesos(w_coste, w_plazo, w_fiab)
    envio = Envio(peso_kg, zona)
    return seleccionar_transportista(envio, transportistas, pesos)
