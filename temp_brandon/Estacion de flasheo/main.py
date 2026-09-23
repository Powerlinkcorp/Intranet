#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
main.py — Punto de entrada unificado para la Estación de Flasheo de ONUs.
Permite lanzar tanto la interfaz web como la interfaz de consola o el motor autopilot.
"""
import os
import sys

# Configurar rutas del proyecto
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(PROJECT_ROOT, "core")
WEB_DIR = os.path.join(PROJECT_ROOT, "web")
CLI_DIR = os.path.join(PROJECT_ROOT, "cli")

for p in [PROJECT_ROOT, CORE_DIR, WEB_DIR, CLI_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import profiles
import web_station
import flasheo


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if "--web" in sys.argv:
        port = 8080
        for i, a in enumerate(sys.argv):
            if a == "--port" and i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit():
                port = int(sys.argv[i + 1])
        web_station.run_web_server(port=port, open_browser=True)
    elif len(sys.argv) > 1 and sys.argv[1] not in ("--cli", "-c"):
        # Redirigir argumentos a vsol_autopilot
        import vsol_autopilot
        import asyncio
        asyncio.run(vsol_autopilot.main())
    else:
        # Menú interactivo CLI por defecto
        flasheo.main()


if __name__ == "__main__":
    main()
