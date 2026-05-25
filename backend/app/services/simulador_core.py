"""
Simulador logístico: selección automatizada de transportista.

Dado un envío (peso y zona de destino) y un conjunto de transportistas candidatos,
selecciona el óptimo minimizando una función de coste multicriterio:

    C(t, e) = w1 * tarifa_norm(t,e) + w2 * plazo_norm(t,e) + w3 * (1 - fiabilidad(t))

Los tres criterios se normalizan a la escala [0, 1] mediante normalización min-max
entre los candidatos del envío concreto, de modo que magnitudes de unidades distintas
(euros, días, probabilidad) sean comparables y ponderables. El transportista con menor
coste C es el elegido. La función devuelve, además del ganador, el desglose por criterio
de cada candidato, lo que hace la decisión transparente y auditable.

Los transportistas se modelan con perfiles genéricos (Express, Estándar, Económico,
Low-cost) cuyos parámetros NO corresponden a ningún operador real, en coherencia con la
restricción de integraciones simuladas del proyecto.

Uso:
    python simulador.py                          # demo con varios envíos
    python simulador.py --peso 2.5 --zona canarias
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# Modelo de datos (en memoria)
# --------------------------------------------------------------------------- #

@dataclass
class Tarifa:
    """Tarifa de un transportista para una zona: coste = base + por_kg * peso."""
    zona: str
    coste_base: float
    coste_por_kg: float
    plazo_dias: int


@dataclass
class Transportista:
    nombre: str
    fiabilidad: float            # en [0, 1]
    tarifas: dict[str, Tarifa]   # zona -> Tarifa

    def coste_envio(self, peso_kg: float, zona: str) -> float | None:
        t = self.tarifas.get(zona)
        if t is None:
            return None
        return t.coste_base + t.coste_por_kg * peso_kg

    def plazo_envio(self, zona: str) -> int | None:
        t = self.tarifas.get(zona)
        return t.plazo_dias if t else None


# Catálogo de transportistas mock (perfiles genéricos)
def catalogo_transportistas() -> list[Transportista]:
    return [
        Transportista(
            nombre="Express", fiabilidad=0.97,
            tarifas={
                "peninsula": Tarifa("peninsula", 6.50, 0.90, 1),
                "baleares":  Tarifa("baleares",  9.00, 1.20, 2),
                "canarias":  Tarifa("canarias", 14.00, 2.00, 3),
            },
        ),
        Transportista(
            nombre="Estándar", fiabilidad=0.92,
            tarifas={
                "peninsula": Tarifa("peninsula", 4.50, 0.70, 2),
                "baleares":  Tarifa("baleares",  6.50, 1.00, 4),
                "canarias":  Tarifa("canarias", 10.00, 1.60, 6),
            },
        ),
        Transportista(
            nombre="Económico", fiabilidad=0.88,
            tarifas={
                "peninsula": Tarifa("peninsula", 3.20, 0.55, 3),
                "baleares":  Tarifa("baleares",  5.00, 0.85, 5),
                "canarias":  Tarifa("canarias",  8.00, 1.30, 8),
            },
        ),
        Transportista(
            nombre="Low-cost", fiabilidad=0.80,
            tarifas={
                "peninsula": Tarifa("peninsula", 2.50, 0.45, 4),
                "baleares":  Tarifa("baleares",  4.00, 0.70, 7),
                "canarias":  Tarifa("canarias",  6.50, 1.10, 10),
            },
        ),
    ]


@dataclass
class Envio:
    peso_kg: float
    zona: str


@dataclass
class Pesos:
    coste: float = 0.5
    plazo: float = 0.3
    fiabilidad: float = 0.2

    def __post_init__(self):
        s = self.coste + self.plazo + self.fiabilidad
        if abs(s - 1.0) > 1e-6:
            raise ValueError(f"Los pesos deben sumar 1 (suman {s}).")


# --------------------------------------------------------------------------- #
# Núcleo: selección de transportista
# --------------------------------------------------------------------------- #

def _min_max_norm(valor: float, vmin: float, vmax: float) -> float:
    # normaliza a [0,1]; si todos los candidatos son iguales, devuelve 0
    if vmax - vmin < 1e-9:
        return 0.0
    return (valor - vmin) / (vmax - vmin)


def seleccionar_transportista(envio: Envio, transportistas: list[Transportista],
                              pesos: Pesos = Pesos()) -> dict:
    # 1. filtrar candidatos que sirven la zona
    candidatos = [t for t in transportistas if envio.zona in t.tarifas]
    if not candidatos:
        raise ValueError(f"Ningún transportista cubre la zona '{envio.zona}'.")

    # 2. calcular criterios brutos
    costes = {t.nombre: t.coste_envio(envio.peso_kg, envio.zona) for t in candidatos}
    plazos = {t.nombre: t.plazo_envio(envio.zona) for t in candidatos}
    fiab   = {t.nombre: t.fiabilidad for t in candidatos}

    cmin, cmax = min(costes.values()), max(costes.values())
    pmin, pmax = min(plazos.values()), max(plazos.values())

    # 3. coste multicriterio normalizado por candidato
    desglose = []
    for t in candidatos:
        c_n = _min_max_norm(costes[t.nombre], cmin, cmax)
        p_n = _min_max_norm(plazos[t.nombre], pmin, pmax)
        f_n = 1.0 - fiab[t.nombre]          # menor fiabilidad -> mayor coste
        C = pesos.coste * c_n + pesos.plazo * p_n + pesos.fiabilidad * f_n
        desglose.append({
            "transportista": t.nombre,
            "coste_eur": round(costes[t.nombre], 2),
            "plazo_dias": plazos[t.nombre],
            "fiabilidad": fiab[t.nombre],
            "coste_norm": round(c_n, 3),
            "plazo_norm": round(p_n, 3),
            "penal_fiab": round(f_n, 3),
            "C": round(C, 4),
        })

    desglose.sort(key=lambda d: d["C"])
    ganador = desglose[0]
    return {
        "envio": {"peso_kg": envio.peso_kg, "zona": envio.zona},
        "pesos": {"coste": pesos.coste, "plazo": pesos.plazo, "fiabilidad": pesos.fiabilidad},
        "elegido": ganador["transportista"],
        "coste_total_C": ganador["C"],
        "justificacion": desglose,
    }


# --------------------------------------------------------------------------- #
# Demo por consola
# --------------------------------------------------------------------------- #
