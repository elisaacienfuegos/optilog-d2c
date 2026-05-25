"""
Punto de entrada de la API de OptiLog.

Crea la aplicación FastAPI, habilita CORS (para que el dashboard React pueda
consumirla desde el navegador) y monta los routers. La documentación interactiva
queda disponible automáticamente en /docs (Swagger) y /redoc.

Arranque (desde backend/, con el venv activo):
    uvicorn app.main:app --reload
"""
from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(
    title="OptiLog D2C API",
    description="API de la plataforma de optimización logística para marcas D2C.",
    version="0.1.0",
)

# CORS: permite que el frontend (React, normalmente en localhost:5173 o :3000)
# consuma la API. Para desarrollo se permiten los orígenes locales habituales.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["General"])
def raiz():
    """Endpoint de bienvenida / comprobación de que la API está viva."""
    return {"mensaje": "API de OptiLog D2C operativa", "docs": "/docs"}
