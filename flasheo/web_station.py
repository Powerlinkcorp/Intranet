# -*- coding: utf-8 -*-
"""
web_station.py — Servidor Web Profesional FastAPI para la Estación de Flasheo.
Incluye:
  - Documentación interactiva Swagger en /docs y ReDoc en /redoc
  - API REST modularizada (/api/v1/...) para integración con aplicaciones externas
  - WebSockets para telemetría en tiempo real (/ws/status)
  - Interfaz de usuario reactiva en /
"""
import os
import sys
import threading
import time
import webbrowser
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Configurar rutas del proyecto
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(PROJECT_ROOT, "core")
WEB_DIR = os.path.join(PROJECT_ROOT, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")

for p in [PROJECT_ROOT, CORE_DIR, WEB_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Inicializar Base de Datos SQLAlchemy y Sincronizador en Background
from core import database
database.init_db()

from core.sync_client import StationSyncClient, start_background_sync
start_background_sync()

# Routers de la API
from api.v1 import api_v1_router
from api.v1.endpoints import ws

app = FastAPI(
    title="Powerlink Estación de Flasheo API",
    version="3.0.0",
    description=(
        "Sistema Profesional para Gestión de Flasheo de ONUs, Asignación de "
        "Credenciales por Lote y Consulta Externa por Dirección MAC o GPON SN."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# Habilitar CORS para integración con cualquier otra aplicación
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar archivos estáticos
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Registrar Routers
app.include_router(api_v1_router)
app.include_router(ws.router)


@app.get("/", response_class=FileResponse, include_in_schema=False)
def serve_dashboard():
    dashboard_path = os.path.join(WEB_DIR, "dashboard.html")
    return dashboard_path


@app.get("/ping", tags=["Salud"])
def ping():
    return {"ok": True, "version": "3.0.0", "time": time.time()}


# ============================================================================
# ENDPOINTS DE SINCRONIZACIÓN CON INTRANET CENTRAL (OFFLINE / MULTI-ESTACIÓN)
# ============================================================================
from pydantic import BaseModel
from typing import Optional

class StationConfigUpdate(BaseModel):
    station_id: Optional[str] = None
    station_name: Optional[str] = None
    server_url: Optional[str] = None
    auto_sync: Optional[bool] = None
    sync_interval_seconds: Optional[int] = None

@app.get("/api/v1/sync/status", tags=["Sincronización Intranet"])
def get_station_sync_status():
    """Retorna el estado de conectividad con la Intranet y registros pendientes de subir."""
    return StationSyncClient.get_status()

@app.post("/api/v1/sync/trigger", tags=["Sincronización Intranet"])
def trigger_station_sync():
    """Fuerza una sincronización inmediata de registros pendientes hacia la Intranet."""
    return StationSyncClient.sync_pending_records()

@app.post("/api/v1/sync/config", tags=["Sincronización Intranet"])
def update_station_sync_config(cfg: StationConfigUpdate):
    """Actualiza la configuración de la estación (ID de laptop, URL de la Intranet)."""
    data = {k: v for k, v in cfg.dict().items() if v is not None}
    ok = StationSyncClient.save_config(data)
    return {"ok": ok, "config": StationSyncClient.load_config()}


def run_server(port: int = 8080, open_browser: bool = True):
    print("=" * 66)
    print("      POWERLINK ESTACIÓN DE FLASHEO — SERVIDOR FASTAPI 3.0")
    print("=" * 66)
    print(f"  Dashboard Web:   http://localhost:{port}/")
    print(f"  API Swagger UI:  http://localhost:{port}/docs")
    print(f"  API Externa:     http://localhost:{port}/api/v1/onus/{{mac}}/credentials")
    print("=" * 66)

    if open_browser:
        threading.Timer(2.0, lambda: webbrowser.open(f"http://localhost:{port}/")).start()

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


run_web_server = run_server



if __name__ == "__main__":
    port = 8080
    open_browser = True
    args = sys.argv[1:]
    if "--no-browser" in args:
        open_browser = False
        args = [a for a in args if a != "--no-browser"]
    if args and args[0].isdigit():
        port = int(args[0])
    run_server(port=port, open_browser=open_browser)
