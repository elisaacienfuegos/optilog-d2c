"""
Pruebas unitarias del simulador logístico.

Verifican el comportamiento de la función de coste multicriterio, la normalización
de criterios, la sensibilidad a los pesos y la gestión de casos límite y errores.

Ejecución (desde backend/, con el venv activo):
    pytest simulator/test_simulador.py -v
"""
from __future__ import annotations
import pytest

from simulador import (
    catalogo_transportistas, seleccionar_transportista,
    Envio, Pesos, _min_max_norm,
)


# --------------------------- Normalización min-max -------------------------- #
def test_normalizacion_extremos():
    """El mínimo se normaliza a 0 y el máximo a 1."""
    assert _min_max_norm(5, 5, 15) == 0.0
    assert _min_max_norm(15, 5, 15) == 1.0
    assert _min_max_norm(10, 5, 15) == 0.5


def test_normalizacion_valores_iguales():
    """Si todos los candidatos son iguales, la normalización devuelve 0 (sin dividir por cero)."""
    assert _min_max_norm(7, 7, 7) == 0.0


# ------------------------------ Pesos válidos ------------------------------- #
def test_pesos_validos_suman_uno():
    p = Pesos(0.5, 0.3, 0.2)
    assert p.coste + p.plazo + p.fiabilidad == pytest.approx(1.0)


def test_pesos_invalidos_lanzan_error():
    """Unos pesos que no suman 1 deben lanzar ValueError."""
    with pytest.raises(ValueError):
        Pesos(0.5, 0.5, 0.5)


# --------------------------- Selección de transportista --------------------- #
def test_devuelve_un_elegido_valido():
    """El simulador devuelve un transportista del catálogo y su justificación."""
    trans = catalogo_transportistas()
    r = seleccionar_transportista(Envio(2.0, "peninsula"), trans)
    nombres = {t.nombre for t in trans}
    assert r["elegido"] in nombres
    assert len(r["justificacion"]) == len(trans)


def test_prioridad_coste_elige_barato():
    """Con todo el peso en coste, gana el transportista más barato."""
    trans = catalogo_transportistas()
    r = seleccionar_transportista(Envio(2.0, "peninsula"), trans, Pesos(1.0, 0.0, 0.0))
    # Low-cost es el de menor tarifa base en península
    assert r["elegido"] == "Low-cost"


def test_prioridad_plazo_elige_rapido():
    """Con todo el peso en plazo, gana el transportista más rápido (Express)."""
    trans = catalogo_transportistas()
    r = seleccionar_transportista(Envio(2.0, "peninsula"), trans, Pesos(0.0, 1.0, 0.0))
    assert r["elegido"] == "Express"


def test_justificacion_ordenada_por_coste():
    """La justificación se devuelve ordenada de menor a mayor coste C."""
    trans = catalogo_transportistas()
    r = seleccionar_transportista(Envio(3.0, "canarias"), trans)
    costes_c = [c["C"] for c in r["justificacion"]]
    assert costes_c == sorted(costes_c)
    # el elegido es el primero (menor C)
    assert r["elegido"] == r["justificacion"][0]["transportista"]


def test_peso_afecta_al_coste():
    """Un envío más pesado cuesta más con el mismo transportista y zona."""
    trans = catalogo_transportistas()
    express = next(t for t in trans if t.nombre == "Express")
    assert express.coste_envio(10, "peninsula") > express.coste_envio(1, "peninsula")


# ------------------------------- Casos límite ------------------------------- #
def test_zona_inexistente_lanza_error():
    """Una zona que ningún transportista cubre debe lanzar ValueError."""
    trans = catalogo_transportistas()
    with pytest.raises(ValueError):
        seleccionar_transportista(Envio(2.0, "marte"), trans)


def test_todas_las_zonas_tienen_solucion():
    """Para las tres zonas válidas siempre hay un transportista elegible."""
    trans = catalogo_transportistas()
    for zona in ["peninsula", "baleares", "canarias"]:
        r = seleccionar_transportista(Envio(2.0, zona), trans)
        assert r["elegido"] is not None
