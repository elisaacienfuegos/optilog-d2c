"""
Validación del simulador logístico sobre un conjunto de envíos sintéticos.

Genera 500 envíos aleatorios (peso y zona) y compara tres políticas de selección:
    1. Multicriterio  : el simulador (función de coste ponderada).
    2. Más barato     : siempre el transportista de menor tarifa.
    3. Más rápido     : siempre el transportista de menor plazo.

Para cada política calcula el coste medio (EUR), el plazo medio (días) y la fiabilidad
media, y la distribución de transportistas seleccionados. Produce dos gráficos y una
tabla resumen, que alimentan la Sección 4.4 de la memoria.

Uso (desde backend/, con el venv activo):
    python simulator\\validar_simulador.py
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# importa el simulador (mismo paquete)
from simulador import (catalogo_transportistas, seleccionar_transportista,
                       Envio, Pesos)

ZONAS = ["peninsula", "baleares", "canarias"]
ZONA_PROB = [0.75, 0.10, 0.15]   # la mayoría de envíos van a península


def generar_envios(n: int, seed: int = 7) -> list[Envio]:
    rng = np.random.default_rng(seed)
    envios = []
    for _ in range(n):
        peso = round(float(rng.uniform(0.2, 10.0)), 2)
        zona = rng.choice(ZONAS, p=ZONA_PROB)
        envios.append(Envio(peso, zona))
    return envios


def politica_mas_barato(envio, transportistas):
    cands = [t for t in transportistas if envio.zona in t.tarifas]
    return min(cands, key=lambda t: t.coste_envio(envio.peso_kg, envio.zona))


def politica_mas_rapido(envio, transportistas):
    cands = [t for t in transportistas if envio.zona in t.tarifas]
    return min(cands, key=lambda t: t.plazo_envio(envio.zona))


def evaluar(envios, transportistas, pesos):
    resultados = {"Multicriterio": [], "Más barato": [], "Más rápido": []}
    elegidos = {"Multicriterio": [], "Más barato": [], "Más rápido": []}

    for e in envios:
        # multicriterio
        r = seleccionar_transportista(e, transportistas, pesos)
        nombre = r["elegido"]
        t = next(x for x in transportistas if x.nombre == nombre)
        resultados["Multicriterio"].append(
            (t.coste_envio(e.peso_kg, e.zona), t.plazo_envio(e.zona), t.fiabilidad))
        elegidos["Multicriterio"].append(nombre)

        # más barato
        tb = politica_mas_barato(e, transportistas)
        resultados["Más barato"].append(
            (tb.coste_envio(e.peso_kg, e.zona), tb.plazo_envio(e.zona), tb.fiabilidad))
        elegidos["Más barato"].append(tb.nombre)

        # más rápido
        tr = politica_mas_rapido(e, transportistas)
        resultados["Más rápido"].append(
            (tr.coste_envio(e.peso_kg, e.zona), tr.plazo_envio(e.zona), tr.fiabilidad))
        elegidos["Más rápido"].append(tr.nombre)

    return resultados, elegidos


def main():
    transportistas = catalogo_transportistas()
    pesos = Pesos(0.5, 0.3, 0.2)
    envios = generar_envios(500)

    resultados, elegidos = evaluar(envios, transportistas, pesos)

    # ---- tabla resumen ----
    print(f"=== Validación sobre {len(envios)} envíos | pesos "
          f"{pesos.coste}/{pesos.plazo}/{pesos.fiabilidad} ===\n")
    print(f"{'Política':<16}{'Coste medio':>13}{'Plazo medio':>13}{'Fiab. media':>13}")
    resumen = {}
    for pol, vals in resultados.items():
        arr = np.array(vals)
        coste_m, plazo_m, fiab_m = arr[:,0].mean(), arr[:,1].mean(), arr[:,2].mean()
        resumen[pol] = (coste_m, plazo_m, fiab_m)
        print(f"{pol:<16}{coste_m:>11.2f} €{plazo_m:>11.2f} d{fiab_m:>12.3f}")

    # ahorro / comparación de la multicriterio frente a las otras
    base_barato = resumen["Más barato"][0]
    base_rapido = resumen["Más rápido"][1]
    mc = resumen["Multicriterio"]
    print(f"\nMulticriterio vs. más barato: "
          f"+{100*(mc[0]-base_barato)/base_barato:.1f}% coste, "
          f"pero {base_rapido and ''}plazo {resumen['Más barato'][1]-mc[1]:+.2f} d más rápido")
    print(f"Multicriterio vs. más rápido: "
          f"{100*(mc[0]-resumen['Más rápido'][0])/resumen['Más rápido'][0]:.1f}% coste "
          f"({resumen['Más rápido'][0]-mc[0]:+.2f} € por envío)")

    # ---- gráfico 1: distribución de transportistas (multicriterio) ----
    out = Path("../data/processed"); out.mkdir(parents=True, exist_ok=True)
    nombres = [t.nombre for t in transportistas]
    counts = [elegidos["Multicriterio"].count(n) for n in nombres]
    fig, ax = plt.subplots(figsize=(7,4))
    colors = ["#185FA5", "#0F6E56", "#BA7517", "#993556"]
    ax.bar(nombres, counts, color=colors)
    ax.set_title("Distribución de transportistas (política multicriterio, 500 envíos)")
    ax.set_ylabel("nº de envíos asignados")
    for i,c in enumerate(counts):
        ax.text(i, c+3, str(c), ha='center', fontsize=10)
    fig.tight_layout(); fig.savefig(out/"sim_distribucion.png", dpi=120)
    print(f"\nGráfico guardado: {out/'sim_distribucion.png'}")

    # ---- gráfico 2: coste vs plazo medio por política ----
    fig, ax = plt.subplots(figsize=(7,4))
    pols = list(resumen.keys())
    costes = [resumen[p][0] for p in pols]
    plazos = [resumen[p][1] for p in pols]
    x = np.arange(len(pols)); wdt=0.35
    ax.bar(x-wdt/2, costes, wdt, label="Coste medio (€)", color="#185FA5")
    ax.bar(x+wdt/2, plazos, wdt, label="Plazo medio (días)", color="#BA7517")
    ax.set_xticks(x); ax.set_xticklabels(pols)
    ax.set_title("Coste y plazo medio por política")
    ax.legend()
    fig.tight_layout(); fig.savefig(out/"sim_comparativa.png", dpi=120)
    print(f"Gráfico guardado: {out/'sim_comparativa.png'}")


if __name__ == "__main__":
    main()
