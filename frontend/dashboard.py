"""
Dashboard de OptiLog D2C — interfaz de soporte a la decisión.

Consume la API REST (FastAPI) y visualiza los KPIs operativos, las predicciones
de demanda y el simulador de selección de transportista. No accede directamente a
la base de datos: toda la información se obtiene a través de la API, respetando la
arquitectura en capas del sistema.

Requisitos: la API debe estar en marcha (uvicorn app.main:app) en API_URL.

Ejecución (desde frontend/, con el venv activo):
    streamlit run dashboard.py
"""
from __future__ import annotations
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

API_URL = "http://127.0.0.1:8000"
ZONAS = ["peninsula", "baleares", "canarias"]

st.set_page_config(page_title="OptiLog D2C", layout="wide")


# --------------------------------------------------------------------------- #
# Utilidades de conexión a la API (con manejo de errores amable)
# --------------------------------------------------------------------------- #
def api_get(path: str, params: dict | None = None):
    try:
        r = requests.get(f"{API_URL}{path}", params=params, timeout=60)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("No se puede conectar con la API. ¿Está `uvicorn app.main:app` "
                 f"en marcha en {API_URL}?")
        st.stop()
    except requests.exceptions.HTTPError as e:
        st.warning(f"La API respondió con error: {e.response.status_code} "
                   f"— {e.response.json().get('detail', '')}")
        return None


def api_post(path: str, payload: dict):
    try:
        r = requests.post(f"{API_URL}{path}", json=payload, timeout=60)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("No se puede conectar con la API. ¿Está la API en marcha?")
        st.stop()
    except requests.exceptions.HTTPError as e:
        st.warning(f"Error: {e.response.json().get('detail', '')}")
        return None


# --------------------------------------------------------------------------- #
# Cabecera
# --------------------------------------------------------------------------- #
st.title("OptiLog D2C: Panel de operaciones")
st.caption("Plataforma de optimización logística para marcas Direct-to-Consumer")

# --------------------------------------------------------------------------- #
# Sección 1: KPIs
# --------------------------------------------------------------------------- #
st.header("Indicadores generales")
kpis = api_get("/kpis")
if kpis:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Productos", kpis["productos"])
    c2.metric("SKUs", kpis["skus"])
    c3.metric("Almacenes", kpis["almacenes"])
    c4.metric("Transportistas", kpis["transportistas"])
    c1.metric("Registros de venta", f"{kpis['registros_venta']:,}".replace(",", "."))
    c2.metric("Unidades totales", f"{kpis['unidades_totales']:,}".replace(",", "."))

st.divider()

# --------------------------------------------------------------------------- #
# Sección 2: Predicción de demanda
# --------------------------------------------------------------------------- #
st.header("Predicción de demanda")

skus = api_get("/skus", {"limite": 100}) or []
almacenes = api_get("/almacenes") or []
cod_skus = [s["codigo_sku"] for s in skus]
cod_alm = [a["codigo"] for a in almacenes]

col_a, col_b, col_c = st.columns([2, 1, 1])
sku_sel = col_a.selectbox("SKU", cod_skus,
                          index=cod_skus.index("BLUSA-AZUL-M") if "BLUSA-AZUL-M" in cod_skus else 0)
alm_sel = col_b.selectbox("Almacén", cod_alm,
                          index=cod_alm.index("MAD") if "MAD" in cod_alm else 0)
horizonte = col_c.slider("Horizonte (días)", 7, 60, 30)

if st.button("Calcular predicción"):
    with st.spinner("Ajustando el modelo Prophet…"):
        pred = api_get(f"/prediccion/{sku_sel}/{alm_sel}", {"horizonte": horizonte})
    if pred:
        df = pd.DataFrame(pred["prediccion"])
        df["fecha"] = pd.to_datetime(df["fecha"])
        fig = go.Figure()
        # banda de confianza
        fig.add_trace(go.Scatter(x=df["fecha"], y=df["max"], mode="lines",
                                 line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=df["fecha"], y=df["min"], mode="lines",
                                 line=dict(width=0), fill="tonexty",
                                 fillcolor="rgba(255,134,0,0.15)", name="intervalo"))
        fig.add_trace(go.Scatter(x=df["fecha"], y=df["demanda_prevista"],
                                 mode="lines+markers", line=dict(color="#FF5600", width=2),
                                 name="demanda prevista"))
        fig.update_layout(title=f"Previsión de demanda — {sku_sel} @ {alm_sel}",
                          xaxis_title="fecha", yaxis_title="unidades/día",
                          height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Modelo ajustado sobre {pred['dias_historico']} días de histórico.")

st.divider()

# --------------------------------------------------------------------------- #
# Sección 3: Simulador de envíos
# --------------------------------------------------------------------------- #
st.header("Simulador de selección de transportista")

s1, s2 = st.columns(2)
peso = s1.number_input("Peso del envío (kg)", min_value=0.1, max_value=50.0,
                       value=2.0, step=0.5)
zona = s2.selectbox("Zona de destino", ZONAS)

st.markdown("**Prioridades (los pesos deben sumar 1):**")
p1, p2, p3 = st.columns(3)
w_coste = p1.slider("Coste", 0.0, 1.0, 0.5, 0.1)
w_plazo = p2.slider("Plazo", 0.0, 1.0, 0.3, 0.1)
w_fiab = p3.slider("Fiabilidad", 0.0, 1.0, 0.2, 0.1)

suma = round(w_coste + w_plazo + w_fiab, 2)
if abs(suma - 1.0) > 0.001:
    st.warning(f"Los pesos suman {suma}. Deben sumar 1 para ejecutar el simulador.")
else:
    if st.button("Seleccionar transportista"):
        res = api_post("/simulador/seleccionar", {
            "peso_kg": peso, "zona": zona,
            "w_coste": w_coste, "w_plazo": w_plazo, "w_fiab": w_fiab,
        })
        if res:
            st.success(f"Transportista óptimo: **{res['elegido']}**  "
                       f"(coste multicriterio C = {res['coste_total_C']})")
            df = pd.DataFrame(res["justificacion"]).rename(columns={
                "transportista": "Transportista", "coste_eur": "Coste (€)",
                "plazo_dias": "Plazo (días)", "fiabilidad": "Fiabilidad", "C": "Coste C",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
