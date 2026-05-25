# OptiLog D2C — Plataforma de optimización logística para marcas D2C

Trabajo Fin de Grado en Ingeniería Informática (CUNEF Universidad, curso 2025–2026).

Plataforma operativa monoinstancia que integra, en un único sistema de soporte a la
decisión, tres componentes para una pequeña o mediana marca *Direct-to-Consumer* (D2C):

- **Gestión de inventario multi-almacén** sobre PostgreSQL, con control de estados de stock
  (disponible, reservado, en tránsito).
- **Motor de predicción de demanda** mediante modelos de series temporales (Prophet y
  SARIMA) alimentado con datos sintéticos de estacionalidad realista.
- **Simulador de selección de transportista** basado en una función de coste multicriterio
  (coste, plazo y fiabilidad).

El sistema se completa con una **API REST** (FastAPI) y un **dashboard** (Streamlit).

## Arquitectura

El proyecto sigue una arquitectura en capas:

```
Presentación (Streamlit)  ->  Servicios (FastAPI)  ->  Dominio (Python)  ->  Persistencia (PostgreSQL)
```

El dashboard consume la API por HTTP; la API orquesta la lógica de negocio (inventario,
predicción, simulador); y la persistencia reside en PostgreSQL.

## Estructura del repositorio

```
optilog-d2c/
|-- backend/
|   |-- app/              # API FastAPI (api, core, services, repositories)
|   |-- data_engine/      # Generación de datos sintéticos y carga a BD; predicción
|   |-- db/               # Esquema SQL
|   |-- simulator/        # Simulador logístico y pruebas (pytest)
|-- frontend/
|   |-- dashboard.py      # Dashboard Streamlit
|-- data/                 # Datos sintéticos generados
```

## Requisitos

- Python 3.11
- PostgreSQL 18

## Puesta en marcha

### 1. Preparar la base de datos

Crear el esquema y cargar los datos sintéticos y el catálogo de transportistas:

```bash
# crear el esquema en una base de datos llamada 'optilog'
psql -d optilog -f backend/db/schema.sql

# generar y cargar los datos (desde backend/)
python data_engine/generate_synthetic_data.py
python data_engine/load_to_db.py --password TU_PASSWORD
python data_engine/load_carriers.py --password TU_PASSWORD
```

### 2. Configurar las credenciales

Crear un fichero `backend/.env` (a partir de `backend/.env.example`) con las credenciales de
la base de datos. **Este fichero no se versiona.**

### 3. Arrancar el backend (API)

```bash
cd backend
uvicorn app.main:app --reload
```

La documentación interactiva de la API queda disponible en `http://127.0.0.1:8000/docs`.

### 4. Arrancar el dashboard

En otra terminal:

```bash
cd frontend
streamlit run dashboard.py
```

El dashboard se abre en `http://localhost:8501` y consume la API.

## Pruebas

```bash
cd backend/simulator
pytest test_simulador.py -v
```

## Tecnologías

Python · PostgreSQL · Prophet · statsmodels (SARIMA) · FastAPI · Pydantic · Streamlit ·
pandas · pytest

## Autora

Elisa Julia Álvarez de Cienfuegos — TFG dirigido por Ismael Gómez García.
