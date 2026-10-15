# -*- coding: utf-8 -*-
"""
main.py — Punto de entrada para Aprovisionamiento Automático de ONUs VSOL.
Inicia el servidor web y abre automáticamente la interfaz en el navegador.
"""
import os
import sys
import threading
import time
import webbrowser

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "core") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "core"))
if os.path.join(PROJECT_ROOT, "web") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "web"))

from aprovisionamiento.web.server import run_server


def open_browser_delayed(url, delay=1.5):
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    port = 8088
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    url = f"http://localhost:{port}/"
    threading.Thread(target=open_browser_delayed, args=(url,), daemon=True).start()
    run_server(port=port)


if __name__ == "__main__":
    main()
