# -*- coding: utf-8 -*-
"""
web.web_station — Servidor Web y Dashboard en Tiempo Real para la Estación de Flasheo de ONUs.
Layout redistribuido a 100% Ancho Horizontal:
  1. Barra horizontal integrada con Modelo, Diagnóstico de Red y Botón de Flasheo (Posición 2 superior).
  2. Matriz de Puertos MikroTik a pantalla completa (100% de ancho) con mayor tamaño vertical.
  3. Tabla Feed en Vivo y Terminal en posición inferior.
"""
import csv
import http.server
import json
import os
import re
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime

# Rutas modulares
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(WEB_DIR) if os.path.basename(WEB_DIR) == "web" else WEB_DIR
CORE_DIR = os.path.join(PROJECT_ROOT, "core")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
FIRMWARES_DIR = os.path.join(PROJECT_ROOT, "firmwares")

for d in [CONFIG_DIR, LOGS_DIR, FIRMWARES_DIR]:
    os.makedirs(d, exist_ok=True)

for p in [PROJECT_ROOT, CORE_DIR, WEB_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from flasheo.core import inventory_db as db
from flasheo.core import mikrotik as mtk
from flasheo.core import network_diag as netdiag
from flasheo.core import profiles

STATUS_FILE = os.path.join(LOGS_DIR, "estado.json")
LOG_FILE = os.path.join(LOGS_DIR, "continuo.log")
CSV_FILE = os.path.join(LOGS_DIR, "registro_flasheo.csv")
AUTOPILOT = os.path.join(CORE_DIR, "vsol_autopilot.py")
if not os.path.exists(AUTOPILOT):
    AUTOPILOT = os.path.join(PROJECT_ROOT, "vsol_autopilot.py")

DEFAULT_PORT = 8080

FLASH_PROCESS = None
FLASH_PROCESS_LOCK = threading.Lock()
FLASH_INFO = {
    "running": False,
    "mode": None,
    "pid": None,
    "start_time": None,
    "model": None,
    "target_ip": None,
    "box_code": None,
}

CACHE_LOCK = threading.Lock()
CACHED_MIKROTIK_PORTS = {}
CACHED_DIAGNOSIS = {}


def _get_process_status():
    global FLASH_PROCESS, FLASH_INFO
    with FLASH_PROCESS_LOCK:
        if FLASH_PROCESS is not None:
            poll = FLASH_PROCESS.poll()
            if poll is None:
                FLASH_INFO["running"] = True
            else:
                FLASH_INFO["running"] = False
                FLASH_PROCESS = None
        else:
            FLASH_INFO["running"] = False
    return dict(FLASH_INFO)


def _start_flash_process(mode="continuo", model=None, ip=None, parallel=20, box_code=None):
    global FLASH_PROCESS, FLASH_INFO
    with FLASH_PROCESS_LOCK:
        if FLASH_PROCESS is not None and FLASH_PROCESS.poll() is None:
            return False, "Ya hay un proceso de flasheo en ejecución"

        active_prof = profiles.get_active_profile(model)
        model_id = active_prof.get("id", "V2801S-B") if active_prof else "V2801S-B"
        profiles.set_active_model(model_id)

        if not box_code:
            caja_activa = db.obtener_caja_activa()
            if caja_activa:
                box_code = caja_activa.get("codigo_caja")

        cmd = [
            sys.executable,
            "-u",
            AUTOPILOT,
            "--headless",
            "--model",
            model_id,
        ]

        if box_code:
            cmd.extend(["--caja", box_code])

        if mode == "continuo":
            cmd.extend(["--continuo", "--final-first", "--parallel", str(parallel)])
        elif mode == "masivo":
            cmd.extend(["--mass", "--parallel", str(parallel)])
        elif mode == "individual":
            target = ip if ip else "192.168.1.1"
            cmd.extend(["--ip", target, "--no-stabilize"])

        try:
            log_f = open(LOG_FILE, "w", encoding="utf-8")
        except Exception:
            log_f = subprocess.DEVNULL

        try:
            FLASH_PROCESS = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                cwd=PROJECT_ROOT,
            )
            FLASH_INFO = {
                "running": True,
                "mode": mode,
                "pid": FLASH_PROCESS.pid,
                "start_time": time.time(),
                "model": model_id,
                "target_ip": ip,
                "box_code": box_code,
            }
            return True, f"Proceso iniciado en modo {mode.upper()} ({model_id})" + (f" - Caja: {box_code}" if box_code else "")
        except Exception as ex:
            return False, f"Error al ejecutar autopilot: {ex}"


def _stop_flash_process():
    global FLASH_PROCESS, FLASH_INFO
    with FLASH_PROCESS_LOCK:
        if FLASH_PROCESS is None:
            FLASH_INFO["running"] = False
            return True, "No hay proceso en ejecución"
        try:
            FLASH_PROCESS.terminate()
            try:
                FLASH_PROCESS.wait(timeout=4)
            except Exception:
                FLASH_PROCESS.kill()
            FLASH_INFO["running"] = False
            FLASH_PROCESS = None
            return True, "Proceso de flasheo detenido exitosamente"
        except Exception as ex:
            return False, f"Error deteniendo proceso: {ex}"


def _read_status_json():
    for path in [STATUS_FILE, os.path.join(PROJECT_ROOT, "estado.json")]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {"onus": [], "total": 20, "procesadas": 0, "en_curso": 0}


def _read_logs(max_lines=150):
    for path in [LOG_FILE, os.path.join(PROJECT_ROOT, "continuo.log")]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    return [line.rstrip() for line in lines[-max_lines:]]
            except Exception:
                pass
    return []


def _background_monitor_loop():
    global CACHED_MIKROTIK_PORTS, CACHED_DIAGNOSIS
    while True:
        try:
            mtk_cfg = mtk.load_config()
            host = mtk_cfg.get("host", "10.100.0.1") if mtk_cfg else "10.100.0.1"
            port = int(mtk_cfg.get("port", 8728)) if mtk_cfg else 8728
            
            ports_res = {}
            is_reachable = False
            try:
                with socket.create_connection((host, port), timeout=0.3):
                    is_reachable = True
            except Exception:
                is_reachable = False

            if is_reachable and mtk_cfg:
                try:
                    res = mtk.get_active_ports(mtk_cfg, quiet=True)
                    if res:
                        ports_res = res
                except Exception:
                    pass

            with CACHE_LOCK:
                CACHED_MIKROTIK_PORTS = ports_res
                CACHED_DIAGNOSIS = {
                    "api_auth_ok": is_reachable,
                    "host": host,
                    "api_port": port,
                    "current_ip": netdiag.DEFAULT_LAPTOP_IP if is_reachable else "Desconectado"
                }
        except Exception:
            pass
        time.sleep(2.0)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class StationAPIHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, content_bytes, content_type, filename=None):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content_bytes)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(content_bytes)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self._serve_dashboard()
        elif path == "/api/status":
            self._handle_api_status()
        elif path == "/api/diagnosis":
            self._handle_api_diagnosis()
        elif path == "/api/profiles":
            self._send_json({"models": profiles.get_models_list(), "active_model": profiles.get_active_model_id()})
        elif path == "/api/firmwares/available":
            self._send_json({"firmwares": profiles.get_available_firmwares()})
        elif path == "/api/logs":
            self._send_json({"logs": _read_logs()})
        elif path == "/api/boxes/active":
            caja = db.obtener_caja_activa()
            self._send_json({"active_box": caja})
        elif path == "/api/boxes/active_onus":
            caja_code = qs.get("codigo_caja", [None])[0]
            if not caja_code:
                caja = db.obtener_caja_activa()
                caja_code = caja["codigo_caja"] if caja else None
            onus = []
            if caja_code:
                onus = db.consultar_onus_por_caja(caja_code)
            self._send_json({"codigo_caja": caja_code, "onus": onus, "count": len(onus)})
        elif path == "/api/boxes/list":
            cajas = db.listar_cajas(limit=100)
            self._send_json({"boxes": cajas})
        elif path == "/api/inventory/records":
            filtros = {
                "fecha_desde": qs.get("fecha_desde", [None])[0],
                "fecha_hasta": qs.get("fecha_hasta", [None])[0],
                "modelo": qs.get("modelo", [None])[0],
                "codigo_caja": qs.get("codigo_caja", [None])[0],
                "resultado": qs.get("resultado", [None])[0],
                "search": qs.get("search", [None])[0],
                "limit": int(qs.get("limit", [500])[0]),
            }
            records = db.consultar_reporte(**filtros)
            self._send_json({"records": records, "count": len(records)})
        elif path == "/api/inventory/export_excel":
            filtros = {
                "fecha_desde": qs.get("fecha_desde", [None])[0],
                "fecha_hasta": qs.get("fecha_hasta", [None])[0],
                "modelo": qs.get("modelo", [None])[0],
                "codigo_caja": qs.get("codigo_caja", [None])[0],
                "resultado": qs.get("resultado", [None])[0],
                "search": qs.get("search", [None])[0],
            }
            file_bytes, ctype, fname = db.exportar_excel(filtros)
            self._send_file(file_bytes, ctype, fname)
        elif path == "/api/inventory/export_csv":
            filtros = {
                "fecha_desde": qs.get("fecha_desde", [None])[0],
                "fecha_hasta": qs.get("fecha_hasta", [None])[0],
                "modelo": qs.get("modelo", [None])[0],
                "codigo_caja": qs.get("codigo_caja", [None])[0],
                "resultado": qs.get("resultado", [None])[0],
                "search": qs.get("search", [None])[0],
            }
            file_bytes = db.exportar_csv(filtros)
            fname = f"Inventario_ONUs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            self._send_file(file_bytes, "text/csv; charset=utf-8", fname)
        else:
            self.send_error(404, "Ruta no encontrada")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            req_data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            req_data = {}

        if path == "/api/boxes/start":
            codigo = req_data.get("codigo_caja", "")
            modelo_id = req_data.get("modelo_id", "")
            cantidad = int(req_data.get("cantidad_total", 20))
            obs = req_data.get("observaciones", "")

            if not modelo_id:
                self._send_json({"success": False, "message": "Debe seleccionar un modelo de ONU"}, 400)
                return

            prof = profiles.get_active_profile(modelo_id)
            mod_nom = prof.get("name") or prof.get("commercial_name") or modelo_id
            profiles.set_active_model(modelo_id)

            caja = db.crear_o_abrir_caja(codigo, modelo_id, cantidad, mod_nom, obs)

            if req_data.get("auto_start_flash", True):
                ok, msg = _start_flash_process(mode="continuo", model=modelo_id, box_code=caja["codigo_caja"])
            else:
                ok, msg = True, "Caja iniciada"

            self._send_json({"success": True, "caja": caja, "flash_started": ok, "message": msg})

        elif path == "/api/boxes/close":
            caja_id = req_data.get("caja_id")
            codigo = req_data.get("codigo_caja")
            target = caja_id if caja_id else codigo
            if not target:
                caja_act = db.obtener_caja_activa()
                target = caja_act["id"] if caja_act else None

            if target:
                db.cerrar_caja(target, estado="COMPLETADA")
                _stop_flash_process()
                self._send_json({"success": True, "message": "Caja finalizada correctamente"})
            else:
                self._send_json({"success": False, "message": "No hay caja activa para finalizar"}, 400)

        elif path == "/api/boxes/cancel":
            caja_id = req_data.get("caja_id")
            codigo = req_data.get("codigo_caja")
            target = caja_id if caja_id else codigo
            if not target:
                caja_act = db.obtener_caja_activa()
                target = caja_act["id"] if caja_act else None

            if target:
                _stop_flash_process()
                db.cancelar_caja(target)
                self._send_json({"success": True, "message": "Caja cancelada exitosamente"})
            else:
                self._send_json({"success": False, "message": "No hay caja activa para cancelar"}, 400)

        elif path == "/api/action/start_continuo":
            model = req_data.get("model")
            parallel = int(req_data.get("parallel", 20))
            box_code = req_data.get("box_code")
            ok, msg = _start_flash_process(mode="continuo", model=model, parallel=parallel, box_code=box_code)
            self._send_json({"success": ok, "message": msg})

        elif path == "/api/action/stop":
            ok, msg = _stop_flash_process()
            self._send_json({"success": ok, "message": msg})

        elif path == "/api/profiles/active":
            model_id = req_data.get("model_id")
            if not model_id:
                self._send_json({"success": False, "message": "model_id requerido"}, 400)
                return
            ok, msg = profiles.set_active_model(model_id)
            self._send_json({"success": ok, "message": msg})

        elif path == "/api/models/save":
            ok, msg = profiles.create_or_update_model(req_data)
            self._send_json({"success": ok, "message": msg})

        elif path == "/api/models/delete":
            model_id = req_data.get("model_id") or req_data.get("id")
            ok, msg = profiles.delete_model(model_id)
            self._send_json({"success": ok, "message": msg})

        elif path == "/api/action/set_ip":
            ad_name = req_data.get("adapter_name")
            target_ip = req_data.get("ip", netdiag.DEFAULT_LAPTOP_IP)
            mask = req_data.get("mask", netdiag.DEFAULT_LAPTOP_MASK)
            if not ad_name:
                adapters = netdiag.get_network_interfaces()
                ad_name = netdiag.pick_ethernet_adapter(adapters)
            if not ad_name:
                self._send_json({"success": False, "message": "No se encontró adaptador de red Ethernet conectado"}, 400)
                return
            ok, msg = netdiag.set_adapter_ip(ad_name, ip=target_ip, netmask=mask)
            self._send_json({"success": ok, "message": msg})

        else:
            self.send_error(404, "Endpoint no encontrado")

    def _handle_api_status(self):
        status_data = _read_status_json()
        proc_status = _get_process_status()
        active_prof = profiles.get_active_profile()
        caja_activa = db.obtener_caja_activa()

        onus = status_data.get("onus", [])
        counts = {
            "listas": sum(1 for o in onus if o.get("estado") in ("LISTA", "EXITO", "YA_CONFIGURADA")),
            "en_curso": sum(1 for o in onus if o.get("estado") in ("FLASHEANDO", "WIZARD", "REINICIANDO", "VERIFICANDO", "LOGIN", "ESTABILIZANDO")),
            "errores": sum(1 for o in onus if o.get("estado") in ("ERROR", "PAUSA")),
            "sin_onu": sum(1 for o in onus if o.get("estado") in ("SIN_ONU", None)),
            "total": status_data.get("total", len(onus) or 20),
        }

        with CACHE_LOCK:
            mtk_ports = dict(CACHED_MIKROTIK_PORTS)

        self._send_json({
            "status": status_data,
            "counts": counts,
            "process": proc_status,
            "active_profile": active_prof,
            "active_box": caja_activa,
            "mikrotik_active_ports": mtk_ports,
            "server_time": time.time(),
        })

    def _handle_api_diagnosis(self):
        with CACHE_LOCK:
            diag_clean = dict(CACHED_DIAGNOSIS)
        self._send_json({"diagnosis": diag_clean})

    def _serve_dashboard(self):
        html = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Estación de Flasheo & Inventario de ONUs - Powerlink</title>
<style>
:root {
  --bg-main: #070d18;
  --bg-card: #131d31;
  --bg-card-hover: #1e293b;
  --bg-input: #0b1324;
  --primary: #2563eb;
  --primary-hover: #1d4ed8;
  --primary-light: #60a5fa;
  --success: #059669;
  --success-light: #34d399;
  --warning: #d97706;
  --danger: #dc2626;
  --danger-light: #f87171;
  --text-main: #f8fafc;
  --text-muted: #94a3b8;
  --border: #20304c;
  --border-focus: #3b82f6;
  --radius: 10px;
}
* { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
body { background-color: var(--bg-main); color: var(--text-main); min-height: 100vh; display: flex; flex-direction: column; }

#server-offline-banner {
  background: #7f1d1d;
  color: #fecaca;
  padding: 0.5rem 1.5rem;
  font-size: 0.85rem;
  text-align: center;
  font-weight: 700;
  display: none;
  border-bottom: 1px solid #ef4444;
}

header {
  background: #0b1324;
  border-bottom: 1px solid var(--border);
  padding: 0.75rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 50;
}
.brand { display: flex; align-items: center; gap: 0.75rem; font-size: 1.15rem; font-weight: 700; color: #fff; }
.brand span.tag { background: var(--primary); font-size: 0.7rem; padding: 2px 8px; border-radius: 9999px; text-transform: uppercase; }

.nav-tabs { display: flex; gap: 0.5rem; }
.nav-tab {
  background: transparent;
  color: var(--text-muted);
  border: 1px solid transparent;
  padding: 0.5rem 1rem;
  border-radius: var(--radius);
  cursor: pointer;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s;
  user-select: none;
}
.nav-tab:hover { color: #fff; background: rgba(255,255,255,0.05); }
.nav-tab.active { color: #fff; background: var(--primary); border-color: var(--primary); }

.header-actions { display: flex; align-items: center; gap: 0.75rem; }
.badge-status { font-size: 0.8rem; padding: 4px 10px; border-radius: 9999px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; }
.badge-idle { background: #334155; color: #cbd5e1; }
.badge-running { background: #065f46; color: #34d399; animation: pulse 2s infinite; }

@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }

main { flex: 1; padding: 1.25rem; max-width: 1720px; width: 100%; margin: 0 auto; }
.view-section { display: none; }
.view-section.active { display: block; }

/* SECCIÓN 1: APERTURA DE CAJA */
.setup-container {
  max-width: 900px;
  margin: 1rem auto;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.setup-card {
  background: linear-gradient(135deg, #131d31 0%, #0b1324 100%);
  border: 2px solid #3b82f6;
  border-radius: 12px;
  padding: 2rem;
  box-shadow: 0 15px 35px -5px rgba(0, 0, 0, 0.4);
}
.setup-title {
  font-size: 1.5rem;
  font-weight: 800;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}
.setup-desc {
  color: var(--text-muted);
  font-size: 0.95rem;
  margin-bottom: 1.5rem;
  line-height: 1.4;
}

/* SECCIÓN 2: CAJA EN PROCESO (WORKSTATION REDISTRIBUIDA HORIZONTAL) */
.box-banner {
  background: linear-gradient(135deg, #172554 0%, #0b1324 100%);
  border: 1px solid #3b82f6;
  border-radius: var(--radius);
  padding: 1.15rem 1.5rem;
  margin-bottom: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
}
.box-banner-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }
.box-title { font-size: 1.3rem; font-weight: 800; display: flex; align-items: center; gap: 0.5rem; }
.box-stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 0.75rem; }
.stat-pill { background: rgba(11, 19, 36, 0.8); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 0.5rem 0.75rem; }
.stat-pill .lbl { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }
.stat-pill .val { font-size: 1.2rem; font-weight: 800; }

.progress-bar-container { background: rgba(0,0,0,0.5); border-radius: 9999px; height: 18px; width: 100%; overflow: hidden; position: relative; border: 1px solid rgba(255,255,255,0.1); }
.progress-bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #10b981); width: 0%; transition: width 0.4s ease; }
.progress-bar-text { position: absolute; width: 100%; text-align: center; top: 0; line-height: 18px; font-size: 0.75rem; font-weight: 700; color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,0.8); }

.card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.25rem; margin-bottom: 1.25rem; }
.card-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 1rem; display: flex; align-items: center; justify-content: space-between; }

.btn {
  background: var(--bg-card-hover);
  color: #fff;
  border: 1px solid var(--border);
  padding: 0.5rem 1rem;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  transition: all 0.2s;
  font-size: 0.9rem;
  user-select: none;
}
.btn:hover:not(:disabled) { background: #334155; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: var(--primary); border-color: var(--primary); }
.btn-primary:hover:not(:disabled) { background: var(--primary-hover); }
.btn-success { background: var(--success); border-color: var(--success); }
.btn-success:hover:not(:disabled) { background: #047857; }
.btn-danger { background: var(--danger); border-color: var(--danger); }
.btn-danger:hover:not(:disabled) { background: #b91c1c; }
.btn-lg { padding: 0.75rem 1.5rem; font-size: 1.05rem; }
.btn-sm { padding: 0.35rem 0.75rem; font-size: 0.8rem; }

.form-group { margin-bottom: 1.1rem; }
.form-label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.35rem; color: var(--text-muted); }
.form-control {
  width: 100%;
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: #fff;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  font-size: 0.95rem;
  outline: none;
  transition: border-color 0.2s;
}
.form-control:focus { border-color: var(--border-focus); }

.top-cards-row {
  display: grid;
  grid-template-columns: 1fr 1fr 240px;
  gap: 1rem;
  margin-bottom: 1.25rem;
  align-items: stretch;
  width: 100%;
}
@media (max-width: 992px) {
  .top-cards-row {
    grid-template-columns: 1fr;
  }
}

/* MATRIZ DE PUERTOS: 4 COLUMNAS x 5 FILAS (ESTRICTO) */
.ports-matrix-full {
  display: grid !important;
  grid-template-columns: repeat(4, 1fr) !important;
  gap: 0.85rem;
  width: 100%;
}
@media (max-width: 1100px) {
  .ports-matrix-full {
    grid-template-columns: repeat(2, 1fr) !important;
  }
}
@media (max-width: 640px) {
  .ports-matrix-full {
    grid-template-columns: 1fr !important;
  }
}

.port-card {
  background: #09101f;
  border: 1.5px solid #1e293b;
  border-radius: 8px;
  padding: 0.75rem 0.95rem;
  min-height: 80px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.4rem;
  position: relative;
  transition: all 0.2s ease;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.2);
  box-sizing: border-box;
}
.port-card:hover { transform: translateY(-2px); border-color: #3b82f6; box-shadow: 0 8px 15px -3px rgba(0,0,0,0.3); }

/* COLORES DE ESTADO EN ALTO CONTRASTE */
.port-card.status-ok {
  border-color: #10b981;
  background: linear-gradient(135deg, rgba(6, 95, 70, 0.35) 0%, rgba(9, 16, 31, 0.95) 100%);
}
.port-card.status-busy {
  border-color: #3b82f6;
  background: linear-gradient(135deg, rgba(30, 58, 138, 0.45) 0%, rgba(9, 16, 31, 0.95) 100%);
  box-shadow: 0 0 15px rgba(59, 130, 246, 0.2);
}
.port-card.status-err {
  border-color: #ef4444;
  background: linear-gradient(135deg, rgba(127, 29, 29, 0.35) 0%, rgba(9, 16, 31, 0.95) 100%);
}

.port-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
}
.port-num {
  font-weight: 800;
  font-size: 0.95rem;
  color: #fff;
  letter-spacing: 0.5px;
  white-space: nowrap;
  flex-shrink: 0;
}
.port-status-badge {
  font-size: 0.72rem;
  font-weight: 800;
  padding: 2.5px 8px;
  border-radius: 5px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  white-space: nowrap;
  flex-shrink: 0;
}

.status-tag-ok { background: #065f46; color: #34d399; border: 1px solid #10b981; }
.status-tag-busy { background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; animation: pulse 1.5s infinite; }
.status-tag-err { background: #7f1d1d; color: #fca5a5; border: 1px solid #ef4444; }
.status-tag-idle { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }

.port-detail {
  font-size: 0.8rem;
  color: var(--text-muted);
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
}

/* TABLA INFERIOR */
.table-responsive { width: 100%; overflow-x: auto; }
table.data-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; text-align: left; }
table.data-table th { background: #0b1324; color: var(--text-muted); padding: 0.75rem 0.9rem; font-weight: 600; border-bottom: 2px solid var(--border); }
table.data-table td { padding: 0.75rem 0.9rem; border-bottom: 1px solid var(--border); }
table.data-table tr:hover { background: rgba(255,255,255,0.02); }

.tag-badge { font-size: 0.75rem; font-weight: 700; padding: 3px 8px; border-radius: 4px; display: inline-block; }

/* SECCIÓN 3: CAJA COMPLETADA */
.box-complete-card {
  background: linear-gradient(135deg, #065f46 0%, #022c22 100%);
  border: 2px solid #10b981;
  border-radius: 12px;
  padding: 2rem;
  margin-bottom: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  box-shadow: 0 15px 35px rgba(16, 185, 129, 0.3);
}

.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.75);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 1rem;
}
.modal-overlay.active { display: flex; }
.modal-content {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  padding: 1.5rem;
  box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5);
}
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }
.modal-close { background: none; border: none; font-size: 1.5rem; color: var(--text-muted); cursor: pointer; }

.log-box {
  background: #050811;
  color: #38bdf8;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.8rem;
  padding: 1rem;
  border-radius: 8px;
  height: 180px;
  overflow-y: auto;
  border: 1px solid var(--border);
}

.filters-bar {
  background: #0b1324;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  margin-bottom: 1.25rem;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
  align-items: end;
}
</style>
</head>
<body>

<div id="server-offline-banner">
  ⚠️ SIN CONEXIÓN CON EL SERVIDOR. Por favor asegúrate de que 'web_panel.bat' esté en ejecución en la consola.
</div>

<!-- HEADER SUPERIOR -->
<header>
  <div class="brand">
    <span>⚡ Powerlink</span>
    <span style="font-weight: 400; color: var(--text-muted);">| Estación de Flasheo</span>
    <span class="tag">PRO</span>
  </div>

  <nav class="nav-tabs">
    <button type="button" class="nav-tab active" onclick="switchTab('tab-flasheo', this)">⚡ Flasheo de ONUs</button>
    <button type="button" class="nav-tab" onclick="switchTab('tab-inventario', this)">📊 Inventario & Reportes</button>
    <button type="button" class="nav-tab" onclick="switchTab('tab-config', this)">⚙️ Configuración</button>
  </nav>

  <div class="header-actions">
    <div id="badge-engine" class="badge-status badge-idle">● Inactivo</div>
  </div>
</header>

<main>

  <!-- ======================================================== -->
  <!-- 1. PESTAÑA PRINCIPAL: FLASHEO DE ONUS POR LOTES          -->
  <!-- ======================================================== -->
  <div id="tab-flasheo" class="view-section active">

    <!-- ---------------------------------------------------- -->
    <!-- ESTADO 1: FORMULARIO PRINCIPAL DE APERTURA DE LOTE   -->
    <!-- (Se muestra ÚNICAMENTE cuando NO hay caja en curso)  -->
    <!-- ---------------------------------------------------- -->
    <div id="view-no-box" class="setup-container">
      <div class="setup-card">
        <div class="setup-title">
          <span>📦 Iniciar Nuevo Lote de Flasheo</span>
        </div>
        <p class="setup-desc">
          Para garantizar el orden del inventario y asociar cada <strong>PON Serial y MAC</strong> a su caja correspondiente, selecciona el modelo e ingresa los datos de la caja antes de conectar y flashear.
        </p>

        <form onsubmit="handleStartBoxForm(event)">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="form-group">
              <label class="form-label">📡 Modelo de las ONUs a Flashear:</label>
              <select id="setup-input-model" class="form-control" required onchange="handleSetupModelChange()">
                <!-- Opciones dinámicas de modelos -->
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">🔢 Cantidad de ONUs en la Caja:</label>
              <input type="number" id="setup-input-qty" class="form-control" min="1" max="100" value="20" required>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">🏷️ Código de la Caja / Lote:</label>
            <div style="display: flex; gap: 0.5rem;">
              <input type="text" id="setup-input-code" class="form-control" placeholder="Ej: CJ-2804-260921-123" required>
              <button type="button" class="btn" onclick="generateSetupBoxCode()">🎲 Generar Código</button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">📝 Observaciones del Lote (Opcional):</label>
            <input type="text" id="setup-input-obs" class="form-control" placeholder="Ej: Lote importación Septiembre - 20 unidades">
          </div>

          <div style="margin-top: 1.5rem; display: flex; justify-content: flex-end;">
            <button type="submit" id="btn-start-setup-box" class="btn btn-primary btn-lg" style="width: 100%;">
              🚀 Comenzar Lote y Abrir Pantalla de Flasheo
            </button>
          </div>
        </form>
      </div>

      <!-- Resumen de Últimos Lotes Procesados -->
      <div class="card">
        <div class="card-title">
          <span>📋 Últimas Cajas Procesadas</span>
          <button type="button" class="btn btn-sm" onclick="switchTab('tab-inventario')">Ver Todo el Inventario →</button>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Código de Caja</th>
                <th>Modelo</th>
                <th>Progreso</th>
                <th>Estado</th>
                <th>Fecha Cierre</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody id="recent-boxes-tbody">
              <tr><td colspan="6" style="text-align:center; color:var(--text-muted);">Cargando historial reciente...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ---------------------------------------------------- -->
    <!-- ESTADO 2: WORKSTATION ACTIVA DE FLASHEO EN VIVO      -->
    <!-- (Se muestra ÚNICAMENTE cuando la caja está en curso) -->
    <!-- ---------------------------------------------------- -->
    <div id="view-active-box" style="display: none;">

      <!-- Banner Superior de Caja Activa con Barra de Progreso -->
      <div class="box-banner">
        <div class="box-banner-header">
          <div>
            <div class="box-title">
              <span>📦 Caja en Proceso:</span>
              <span id="box-banner-code" style="color: #60a5fa;">CJ-0000</span>
              <span id="box-banner-model" class="tag-badge" style="background:#1e3a8a; margin-left: 0.5rem;">VSOL</span>
            </div>
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 4px;">
              Iniciada: <span id="box-banner-time">--:--:--</span>
            </div>
          </div>

          <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <button type="button" class="btn btn-sm btn-primary" onclick="exportBoxExcel()">📥 Excel de esta Caja</button>
            <button type="button" class="btn btn-sm btn-danger" style="background:#dc2626; border-color:#ef4444;" onclick="cancelActiveBox()">❌ Cancelar Caja</button>
            <button type="button" class="btn btn-sm btn-success" style="background:#059669; border-color:#10b981;" onclick="closeActiveBox()">🏁 Finalizar Caja</button>
          </div>
        </div>

        <!-- Barra de Progreso de la Caja -->
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 600; margin-bottom: 4px;">
            <span>Progreso del Lote: <span id="box-prog-count">0 / 20</span> ONUs</span>
            <span id="box-prog-pct">0%</span>
          </div>
          <div class="progress-bar-container">
            <div id="box-prog-bar" class="progress-bar-fill"></div>
            <div id="box-prog-text" class="progress-bar-text">0 / 20 completadas</div>
          </div>
        </div>

        <!-- Resumen en Píldoras -->
        <div class="box-stats-grid">
          <div class="stat-pill"><div class="lbl">Cantidad Total</div><div id="stat-box-total" class="val">20</div></div>
          <div class="stat-pill"><div class="lbl">Procesadas</div><div id="stat-box-proc" class="val" style="color:#60a5fa;">0</div></div>
          <div class="stat-pill"><div class="lbl">Exitosas (OK)</div><div id="stat-box-ok" class="val" style="color:#34d399;">0</div></div>
          <div class="stat-pill"><div class="lbl">Fallidas / Error</div><div id="stat-box-fail" class="val" style="color:#f87171;">0</div></div>
        </div>
      </div>

      <!-- POSICIÓN 2: FILA SUPERIOR ULTRA-COMPACTA (ALTURA REDUCIDA AL 50%) -->
      <div style="display: flex; gap: 0.65rem; margin-bottom: 0.75rem; align-items: center; width: 100%; flex-wrap: wrap;">
        
        <!-- Indicador 1: Modelo en Flasheo -->
        <div style="flex: 1; min-width: 260px; background: #09101f; border: 1px solid #1e3a8a; border-left: 3px solid #3b82f6; border-radius: 6px; padding: 0.32rem 0.75rem; display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; height: 34px; box-sizing: border-box;">
          <div style="display: flex; align-items: center; gap: 0.45rem; overflow: hidden; white-space: nowrap;">
            <span style="color: var(--text-muted); font-size: 0.72rem; font-weight: 700; text-transform: uppercase;">🎯 Modelo:</span>
            <strong id="mod-name" style="color: #60a5fa; font-size: 0.85rem; font-weight: 800;">VSOL</strong>
            <span id="mod-fw" style="color: #94a3b8; font-size: 0.75rem; font-family: monospace; overflow: hidden; text-overflow: ellipsis; max-width: 240px;">firmware.bin</span>
          </div>
          <span id="mod-vlan" class="tag-badge" style="background:#065f46; color:#34d399; font-size:0.68rem; padding: 1px 6px; white-space: nowrap;">VLAN 3</span>
        </div>

        <!-- Indicador 2: Diagnóstico de Red & Switch -->
        <div style="flex: 1; min-width: 280px; background: #09101f; border: 1px solid #064e3b; border-left: 3px solid #10b981; border-radius: 6px; padding: 0.32rem 0.75rem; display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; height: 34px; box-sizing: border-box;">
          <div style="display: flex; align-items: center; gap: 0.6rem; font-size: 0.78rem; white-space: nowrap;">
            <span>🌐 Switch: <strong id="diag-mtk" style="color:var(--text-muted);">Comprobando...</strong></span>
            <span style="color: var(--border);">|</span>
            <span>IP: <strong id="diag-ip" style="color:#fff;">10.100.0.2</strong></span>
          </div>
          <button type="button" id="btn-fix-ip" class="btn btn-sm" style="padding: 1px 6px; font-size: 0.68rem; height: 22px; line-height: 1;" onclick="fixNetworkIp()">🔧 Auto-IP</button>
        </div>

        <!-- Indicador 3: Control Flasheo -->
        <div style="flex-shrink: 0;">
          <button type="button" id="btn-flash-toggle" class="btn btn-success" style="height: 34px; padding: 0 0.85rem; font-weight: 700; font-size: 0.82rem; border-radius: 6px; white-space: nowrap; box-sizing: border-box;" onclick="toggleEngine()">
            ▶ Continuar Flasheo
          </button>
        </div>

      </div>

      <!-- VENTANA INDEPENDIENTE: MATRIZ DE PUERTOS MIKROTIK (100% ANCHO COMPLETO) -->
      <div class="card" style="margin-bottom: 1.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.25rem; padding-bottom: 0.75rem; border-bottom: 1px solid var(--border);">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <h3 style="font-size: 1.25rem; font-weight: 800; color: #fff; display: flex; align-items: center; gap: 0.5rem; margin: 0;">
              🔌 Matriz de Puertos MikroTik
            </h3>
            <span class="tag-badge" style="background:#1e3a8a; color:#93c5fd; font-size:0.8rem; font-weight:700;">Puertos 1 al 20</span>
          </div>
          
          <!-- Leyenda de Estados para el Operador -->
          <div style="display: flex; align-items: center; gap: 0.75rem; font-size: 0.8rem; flex-wrap: wrap;">
            <span style="display: flex; align-items: center; gap: 5px;"><span style="width:10px; height:10px; border-radius:50%; background:#10b981; display:inline-block;"></span> <span style="color:#cbd5e1;">Lista / OK</span></span>
            <span style="display: flex; align-items: center; gap: 5px;"><span style="width:10px; height:10px; border-radius:50%; background:#3b82f6; display:inline-block;"></span> <span style="color:#cbd5e1;">Flasheando / Reiniciando</span></span>
            <span style="display: flex; align-items: center; gap: 5px;"><span style="width:10px; height:10px; border-radius:50%; background:#ef4444; display:inline-block;"></span> <span style="color:#cbd5e1;">Falla / Error</span></span>
            <span style="display: flex; align-items: center; gap: 5px;"><span style="width:10px; height:10px; border-radius:50%; background:#334155; display:inline-block;"></span> <span style="color:#cbd5e1;">Libre</span></span>
          </div>
        </div>

        <!-- Matriz de Puertos 100% Ancho Completo -->
        <div id="ports-grid" class="ports-matrix-full">
          <!-- Render dinámico ampliado de puertos 1..20 -->
        </div>
      </div>

      <!-- POSICIÓN 1: TABLA FEED EN VIVO DE ONUS FLASHEADAS (ABAJO) -->
      <div class="card">
        <div class="card-title">
          <span>📋 ONUs Flasheadas y Registradas en este Lote (<span id="box-feed-title-code" style="color:#60a5fa;">Caja Activa</span>)</span>
          <span id="box-feed-counter" class="tag-badge" style="background:#065f46; color:#34d399;">0 / 20 Listas</span>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width: 50px;">#</th>
                <th>Caja / Lote</th>
                <th>Modelo</th>
                <th>PON Serial (GPON SN)</th>
                <th>Dirección MAC</th>
                <th>Puerto</th>
                <th>Tiempo</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody id="box-feed-tbody">
              <tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding: 1.5rem;">Esperando que se complete la primera ONU de esta caja...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Visor de Logs de Terminal en Vivo -->
      <div class="card">
        <div class="card-title">📝 Salida de Terminal en Tiempo Real</div>
        <div id="log-viewer" class="log-box">Cargando logs...</div>
      </div>

    </div>

    <!-- ---------------------------------------------------- -->
    <!-- ESTADO 3: CAJA COMPLETADA AL 100%                    -->
    <!-- (Se muestra ÚNICAMENTE cuando la caja finalizó)      -->
    <!-- ---------------------------------------------------- -->
    <div id="view-complete-box" style="display: none;">
      <div class="box-complete-card">
        <div>
          <h2 style="font-size: 1.8rem; font-weight: 800; color: #fff; margin-bottom: 0.5rem;">
            🎉 ¡Caja <span id="complete-view-code">CJ-XXXX</span> Completada al 100%!
          </h2>
          <p style="color: #d1fae5; font-size: 1.05rem; line-height: 1.5;">
            Se han flasheado y registrado exitosamente todas las <strong id="complete-view-qty">20</strong> ONUs con sus números de serie <strong>PON y MAC</strong> listos para sincronizar con el inventario de Powerlink.
          </p>
        </div>

        <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
          <button type="button" class="btn btn-primary btn-lg" onclick="exportCompletedBoxExcel()">
            📥 Descargar Reporte Excel de esta Caja
          </button>
          <button type="button" class="btn btn-success btn-lg" onclick="startNextBoxFlow()">
            📦 Abrir Siguiente Caja para Flashear
          </button>
        </div>
      </div>

      <!-- Tabla con el lote completo terminado -->
      <div class="card">
        <div class="card-title">
          <span>📋 Detalle de las ONUs Registradas en la Caja <span id="complete-table-code" style="color:#60a5fa;">CJ-XXXX</span></span>
          <span class="tag-badge" style="background:#065f46; color:#34d399;">100% COMPLETADA</span>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Modelo</th>
                <th>PON Serial (GPON SN)</th>
                <th>Dirección MAC</th>
                <th>Puerto</th>
                <th>Tiempo</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody id="complete-table-tbody">
              <!-- Detalle de ONUs -->
            </tbody>
          </table>
        </div>
      </div>
    </div>

  </div>

  <!-- ======================================================== -->
  <!-- 2. VISTA: INVENTARIO & REPORTES PERSONALIZADOS           -->
  <!-- ======================================================== -->
  <div id="tab-inventario" class="view-section">
    <div class="card">
      <div class="card-title">
        <span>📊 Base de Datos de Inventario & ONUs Flasheadas</span>
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
          <button type="button" class="btn btn-sm btn-success" onclick="exportFilteredExcel()">📥 Exportar a Excel (.xlsx)</button>
          <button type="button" class="btn btn-sm btn-primary" onclick="exportFilteredCsv()">📄 Exportar a CSV</button>
        </div>
      </div>

      <!-- Barra de Filtros Avanzados -->
      <div class="filters-bar">
        <div class="form-group" style="margin-bottom:0;">
          <label class="form-label">📅 Fecha Desde:</label>
          <input type="date" id="filtro-desde" class="form-control" onchange="loadInventoryTable()">
        </div>
        <div class="form-group" style="margin-bottom:0;">
          <label class="form-label">📅 Fecha Hasta:</label>
          <input type="date" id="filtro-hasta" class="form-control" onchange="loadInventoryTable()">
        </div>
        <div class="form-group" style="margin-bottom:0;">
          <label class="form-label">📡 Modelo:</label>
          <select id="filtro-modelo" class="form-control" onchange="loadInventoryTable()">
            <option value="TODOS">Todos los modelos</option>
          </select>
        </div>
        <div class="form-group" style="margin-bottom:0;">
          <label class="form-label">📦 Código de Caja:</label>
          <select id="filtro-caja" class="form-control" onchange="loadInventoryTable()">
            <option value="TODAS">Todas las cajas</option>
          </select>
        </div>
        <div class="form-group" style="margin-bottom:0;">
          <label class="form-label">🔍 Buscar Serial / MAC / IP:</label>
          <input type="text" id="filtro-search" class="form-control" placeholder="Ej: VSOL00, BC:24..." oninput="loadInventoryTable()">
        </div>
      </div>

      <!-- Tabla de Resultados -->
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Fecha / Hora</th>
              <th>Caja / Lote</th>
              <th>Modelo</th>
              <th>PON Serial (GPON SN)</th>
              <th>Dirección MAC</th>
              <th>Puerto</th>
              <th>Resultado</th>
              <th>VLAN 3</th>
              <th>Detalles</th>
            </tr>
          </thead>
          <tbody id="inventory-tbody">
            <tr><td colspan="9" style="text-align:center; color:var(--text-muted);">Cargando registros...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ======================================================== -->
  <!-- 3. VISTA: CONFIGURACIÓN & GESTOR DE MODELOS              -->
  <!-- ======================================================== -->
  <div id="tab-config" class="view-section">
    <div class="card">
      <div class="card-title">
        <span>🛠️ Modelos de ONUs Configurados</span>
        <button type="button" class="btn btn-sm btn-success" onclick="openNewModelModal()">➕ Registrar Nuevo Modelo</button>
      </div>
      <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1rem;">
        Los modelos aquí configurados aparecerán en el selector de cajas para evitar errores tipográficos en el inventario.
      </p>

      <div id="models-cards-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1rem;">
        <!-- Tarjetas dinámicas de modelos -->
      </div>
    </div>
  </div>

</main>

<!-- ======================================================== -->
<!-- MODAL: REGISTRAR / EDITAR MODELO DE ONU                  -->
<!-- ======================================================== -->
<div id="modal-model" class="modal-overlay" style="display: none;">
  <div class="modal-content">
    <div class="modal-header">
      <h3 style="font-size: 1.2rem;">🛠️ Registrar Nuevo Modelo de ONU</h3>
      <button type="button" class="modal-close" onclick="closeModal('modal-model')">&times;</button>
    </div>

    <form onsubmit="handleSaveModel(event)">
      <div class="form-group">
        <label class="form-label">🆔 ID Técnico Único (Ej: V2804AX30-H):</label>
        <input type="text" id="m-input-id" class="form-control" placeholder="V2804AX30-H" required>
      </div>

      <div class="form-group">
        <label class="form-label">🏷️ Nombre Comercial:</label>
        <input type="text" id="m-input-name" class="form-control" placeholder="VSOL Wi-Fi 6 AX3000 (4GE + 1POTS)" required>
      </div>

      <div class="form-group">
        <label class="form-label">📦 Archivo de Firmware (.bin):</label>
        <select id="m-input-fw" class="form-control" required>
          <!-- Firmwares disponibles en firmwares/ -->
        </select>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
        <div class="form-group">
          <label class="form-label">Usuario Fábrica:</label>
          <input type="text" id="m-input-defuser" class="form-control" value="admin" required>
        </div>
        <div class="form-group">
          <label class="form-label">Clave Fábrica:</label>
          <input type="text" id="m-input-defpass" class="form-control" value="stdONU101" required>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
        <div class="form-group">
          <label class="form-label">Usuario Final (Powerlink):</label>
          <input type="text" id="m-input-finuser" class="form-control" value="Powerlink" required>
        </div>
        <div class="form-group">
          <label class="form-label">Clave Final:</label>
          <input type="text" id="m-input-finpass" class="form-control" value="Powerlink2026*" required>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
        <div class="form-group">
          <label class="form-label">VLAN ID Objetivo:</label>
          <input type="text" id="m-input-vlan" class="form-control" value="3" required>
        </div>
        <div class="form-group">
          <label class="form-label">Cantidad típica por Caja:</label>
          <input type="number" id="m-input-boxqty" class="form-control" value="20" required>
        </div>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1.5rem;">
        <button type="button" class="btn" onclick="closeModal('modal-model')">Cancelar</button>
        <button type="submit" id="btn-save-model" class="btn btn-success">💾 Guardar Modelo</button>
      </div>
    </form>
  </div>
</div>

<script>
let CURRENT_ACTIVE_BOX = null;
let LAST_COMPLETED_BOX_CODE = null;
let ALL_MODELS = [];
let SERVER_ONLINE = true;

function setServerStatus(online) {
  SERVER_ONLINE = online;
  const banner = document.getElementById('server-offline-banner');
  if (banner) {
    banner.style.display = online ? 'none' : 'block';
  }
}

function switchTab(tabId, btn) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));

  if (btn && btn.classList) {
    btn.classList.add('active');
  } else {
    const targetBtn = Array.from(document.querySelectorAll('.nav-tab')).find(b => b.getAttribute('onclick')?.includes(tabId));
    if (targetBtn) targetBtn.classList.add('active');
  }

  const targetSection = document.getElementById(tabId);
  if (targetSection) targetSection.classList.add('active');

  if (tabId === 'tab-inventario') {
    loadInventoryTable();
    loadBoxFilterOptions();
  } else if (tabId === 'tab-config') {
    loadModelsView();
  } else if (tabId === 'tab-flasheo') {
    fetchStatus();
  }
}

function openModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.add('active');
    el.style.display = 'flex';
  }
}
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.remove('active');
    el.style.display = 'none';
  }
}

function generateSetupBoxCode() {
  const modSelect = document.getElementById('setup-input-model');
  const modId = (modSelect && modSelect.value) ? modSelect.value : 'ONU';
  const prefix = modId.substring(0, 5).replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  const ts = new Date().toISOString().slice(2,10).replace(/-/g, '');
  const rnd = Math.floor(100 + Math.random() * 900);
  const el = document.getElementById('setup-input-code');
  if (el) el.value = `CJ-${prefix}-${ts}-${rnd}`;
}

function handleSetupModelChange() {
  const sel = document.getElementById('setup-input-model');
  const modId = sel ? sel.value : null;
  const m = ALL_MODELS.find(x => x.id === modId);
  const qtyInput = document.getElementById('setup-input-qty');
  if (m && m.box_default_qty && qtyInput) {
    qtyInput.value = m.box_default_qty;
  }
  generateSetupBoxCode();
}

async function handleStartBoxForm(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-start-setup-box');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Preparando Lote e Iniciando Flasheo...';
  }

  const payload = {
    modelo_id: document.getElementById('setup-input-model').value,
    codigo_caja: document.getElementById('setup-input-code').value.trim(),
    cantidad_total: parseInt(document.getElementById('setup-input-qty').value) || 20,
    observaciones: document.getElementById('setup-input-obs').value.trim(),
    auto_start_flash: true
  };

  try {
    const res = await fetch('/api/boxes/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      LAST_COMPLETED_BOX_CODE = null;
      await fetchStatus();
    } else {
      alert("⚠️ Error al iniciar caja: " + data.message);
    }
  } catch(err) {
    alert("❌ Error de comunicación con el servidor: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🚀 Comenzar Lote y Abrir Pantalla de Flasheo';
    }
  }
}

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    setServerStatus(true);

    const badge = document.getElementById('badge-engine');
    const btnToggle = document.getElementById('btn-flash-toggle');
    if (data.process && data.process.running) {
      if (badge) {
        badge.className = 'badge-status badge-running';
        badge.textContent = `● Flasheando (${data.process.mode.toUpperCase()})`;
      }
      if (btnToggle) {
        btnToggle.className = 'btn btn-sm btn-danger';
        btnToggle.textContent = '⏹ Pausar Flasheo';
      }
    } else {
      if (badge) {
        badge.className = 'badge-status badge-idle';
        badge.textContent = '● Inactivo';
      }
      if (btnToggle) {
        btnToggle.className = 'btn btn-sm btn-success';
        btnToggle.textContent = '▶ Continuar Flasheo';
      }
    }

    CURRENT_ACTIVE_BOX = data.active_box;
    renderWorkflow(data.active_box);

    if (data.active_profile) {
      const nm = document.getElementById('mod-name');
      const fw = document.getElementById('mod-fw');
      const vl = document.getElementById('mod-vlan');
      if (nm) nm.textContent = data.active_profile.commercial_name || data.active_profile.name;
      if (fw) fw.textContent = data.active_profile.firmware || 'Sin firmware';
      if (vl) vl.textContent = `VLAN ${data.active_profile.target_vlan_id || 3}`;
    }

    if (CURRENT_ACTIVE_BOX) {
      renderPorts(data.status.onus || [], data.mikrotik_active_ports || {});
      fetchActiveBoxFeed();
    }
  } catch (err) {
    setServerStatus(false);
  }
}

function renderWorkflow(box) {
  const vNoBox = document.getElementById('view-no-box');
  const vActive = document.getElementById('view-active-box');
  const vComplete = document.getElementById('view-complete-box');

  if (!box) {
    if (LAST_COMPLETED_BOX_CODE) {
      if (vNoBox) vNoBox.style.display = 'none';
      if (vActive) vActive.style.display = 'none';
      if (vComplete) vComplete.style.display = 'block';
    } else {
      if (vNoBox) vNoBox.style.display = 'block';
      if (vActive) vActive.style.display = 'none';
      if (vComplete) vComplete.style.display = 'none';
      loadRecentBoxes();
    }
    return;
  }

  const total = box.cantidad_total || 20;
  const proc = box.cantidad_procesadas || 0;

  if (proc >= total && total > 0) {
    LAST_COMPLETED_BOX_CODE = box.codigo_caja;
    if (vNoBox) vNoBox.style.display = 'none';
    if (vActive) vActive.style.display = 'none';
    if (vComplete) vComplete.style.display = 'block';
    renderCompletedBoxView(box);
  } else {
    LAST_COMPLETED_BOX_CODE = null;
    if (vNoBox) vNoBox.style.display = 'none';
    if (vActive) vActive.style.display = 'block';
    if (vComplete) vComplete.style.display = 'none';
    renderActiveBoxView(box);
  }
}

function renderActiveBoxView(box) {
  const codeEl = document.getElementById('box-banner-code');
  const modEl = document.getElementById('box-banner-model');
  const timeEl = document.getElementById('box-banner-time');
  if (codeEl) codeEl.textContent = box.codigo_caja;
  if (modEl) modEl.textContent = box.modelo_nombre || box.modelo_id;
  if (timeEl) timeEl.textContent = box.fecha_inicio;

  const total = box.cantidad_total || 20;
  const proc = box.cantidad_procesadas || 0;
  const ok = box.cantidad_exitosas || 0;
  const fail = box.cantidad_fallidas || 0;
  const pct = Math.min(100, Math.round((proc / total) * 100));

  const pCnt = document.getElementById('box-prog-count');
  const pPct = document.getElementById('box-prog-pct');
  const pBar = document.getElementById('box-prog-bar');
  const pTxt = document.getElementById('box-prog-text');

  if (pCnt) pCnt.textContent = `${proc} / ${total}`;
  if (pPct) pPct.textContent = `${pct}%`;
  if (pBar) pBar.style.width = `${pct}%`;
  if (pTxt) pTxt.textContent = `${proc} de ${total} procesadas (${pct}%)`;

  const sTot = document.getElementById('stat-box-total');
  const sPrc = document.getElementById('stat-box-proc');
  const sOk = document.getElementById('stat-box-ok');
  const sFal = document.getElementById('stat-box-fail');

  if (sTot) sTot.textContent = total;
  if (sPrc) sPrc.textContent = proc;
  if (sOk) sOk.textContent = ok;
  if (sFal) sFal.textContent = fail;
}

async function renderCompletedBoxView(box) {
  const cCode = document.getElementById('complete-view-code');
  const cQty = document.getElementById('complete-view-qty');
  const tCode = document.getElementById('complete-table-code');
  const tbody = document.getElementById('complete-table-tbody');

  if (cCode) cCode.textContent = box.codigo_caja;
  if (cQty) cQty.textContent = box.cantidad_procesadas || box.cantidad_total || 20;
  if (tCode) tCode.textContent = box.codigo_caja;

  try {
    const res = await fetch(`/api/boxes/active_onus?codigo_caja=${encodeURIComponent(box.codigo_caja)}`);
    const data = await res.json();
    if (!tbody) return;
    tbody.innerHTML = '';
    const onus = data.onus || [];

    if (onus.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:1rem;">No hay registros cargados para esta caja.</td></tr>';
      return;
    }

    onus.forEach((r, idx) => {
      const isOk = ['EXITO', 'YA_CONFIGURADA', 'CHECK_OK'].includes(r.resultado);
      const tagClass = isOk ? 'status-tag-ok' : 'status-tag-err';
      const durStr = r.duracion_segundos ? `${Math.floor(r.duracion_segundos/60)}m ${r.duracion_segundos%60}s` : '-';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong style="color:var(--primary-light);">#${idx + 1}</strong></td>
        <td>${r.modelo_id}</td>
        <td><strong style="color:#60a5fa; font-family:monospace; font-size:1rem;">${r.pon_sn || r.pon_original || '-'}</strong></td>
        <td><span style="font-family:monospace; color:#cbd5e1;">${r.mac || '-'}</span></td>
        <td><strong>Puerto ${r.puerto}</strong></td>
        <td style="color:var(--text-muted); font-size:0.85rem;">${durStr}</td>
        <td><span class="tag-badge ${tagClass}">${isOk ? '✅ OK' : '❌ ERROR'}</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {}
}

async function startNextBoxFlow() {
  if (CURRENT_ACTIVE_BOX) {
    await fetch('/api/boxes/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo_caja: CURRENT_ACTIVE_BOX.codigo_caja })
    });
  }
  LAST_COMPLETED_BOX_CODE = null;
  CURRENT_ACTIVE_BOX = null;
  generateSetupBoxCode();
  await fetchStatus();
}

async function cancelActiveBox() {
  if (!CURRENT_ACTIVE_BOX) return;
  const code = CURRENT_ACTIVE_BOX.codigo_caja;
  if (!confirm(`⚠️ ¿Deseas CANCELAR la caja ${code}?\n\nSe detendrá el proceso de flasheo y se descartará el lote actual para que puedas volver a iniciar desde cero.`)) {
    return;
  }
  try {
    const res = await fetch('/api/boxes/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo_caja: code })
    });
    const data = await res.json();
    if (data.success) {
      alert("✅ Caja cancelada exitosamente.");
      CURRENT_ACTIVE_BOX = null;
      LAST_COMPLETED_BOX_CODE = null;
      generateSetupBoxCode();
      await fetchStatus();
    } else {
      alert("⚠️ Error al cancelar caja: " + data.message);
    }
  } catch(err) {
    alert("❌ Error: " + err.message);
  }
}

async function closeActiveBox() {
  if (!CURRENT_ACTIVE_BOX) return;
  const code = CURRENT_ACTIVE_BOX.codigo_caja;
  if (!confirm(`¿Deseas dar por FINALIZADA la caja ${code}?`)) return;
  try {
    const res = await fetch('/api/boxes/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo_caja: code })
    });
    const data = await res.json();
    if (data.success) {
      alert("✅ " + data.message);
      LAST_COMPLETED_BOX_CODE = null;
      await fetchStatus();
    } else {
      alert("⚠️ " + data.message);
    }
  } catch(err) {
    alert("❌ Error: " + err.message);
  }
}

async function loadRecentBoxes() {
  try {
    const res = await fetch('/api/boxes/list');
    const data = await res.json();
    const tbody = document.getElementById('recent-boxes-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    const boxes = data.boxes || [];

    if (boxes.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No hay cajas registradas aún</td></tr>';
      return;
    }

    boxes.slice(0, 5).forEach(b => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${b.codigo_caja}</strong></td>
        <td>${b.modelo_id}</td>
        <td>${b.cantidad_procesadas || 0} / ${b.cantidad_total || 20}</td>
        <td><span class="tag-badge ${b.estado === 'COMPLETADA' ? 'status-tag-ok' : 'status-tag-busy'}">${b.estado}</span></td>
        <td style="font-size:0.8rem; color:var(--text-muted);">${b.fecha_cierre || b.fecha_inicio}</td>
        <td>
          <button type="button" class="btn btn-sm btn-primary" onclick="window.location.href='/api/inventory/export_excel?codigo_caja=${encodeURIComponent(b.codigo_caja)}'">📥 Excel</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch(e) {}
}

async function fetchActiveBoxFeed() {
  const tbody = document.getElementById('box-feed-tbody');
  const counter = document.getElementById('box-feed-counter');
  const titleCode = document.getElementById('box-feed-title-code');

  if (!CURRENT_ACTIVE_BOX) return;

  if (titleCode) titleCode.textContent = `${CURRENT_ACTIVE_BOX.codigo_caja} (${CURRENT_ACTIVE_BOX.modelo_id})`;

  try {
    const res = await fetch('/api/boxes/active_onus');
    const data = await res.json();
    if (!tbody) return;
    tbody.innerHTML = '';

    const onus = data.onus || [];
    const total = CURRENT_ACTIVE_BOX.cantidad_total || 20;
    if (counter) counter.textContent = `${onus.length} / ${total} Listas`;

    if (onus.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding: 1.5rem;">Esperando que se complete la primera ONU de esta caja...</td></tr>';
      return;
    }

    onus.forEach((r, idx) => {
      const isOk = ['EXITO', 'YA_CONFIGURADA', 'CHECK_OK'].includes(r.resultado);
      const tagClass = isOk ? 'status-tag-ok' : 'status-tag-err';
      const durStr = r.duracion_segundos ? `${Math.floor(r.duracion_segundos/60)}m ${r.duracion_segundos%60}s` : '-';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong style="color:var(--primary-light);">#${idx + 1}</strong></td>
        <td><strong>${r.codigo_caja}</strong></td>
        <td>${r.modelo_id}</td>
        <td><strong style="color:#60a5fa; font-family:monospace; font-size:1rem;">${r.pon_sn || r.pon_original || '-'}</strong></td>
        <td><span style="font-family:monospace; color:#cbd5e1;">${r.mac || '-'}</span></td>
        <td><strong>Puerto ${r.puerto}</strong></td>
        <td style="color:var(--text-muted); font-size:0.85rem;">${durStr}</td>
        <td><span class="tag-badge ${tagClass}">${isOk ? '✅ FLASHEADA OK' : '❌ ERROR'}</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch(e) {}
}

function renderPorts(onus, mtkPorts) {
  const grid = document.getElementById('ports-grid');
  if (!grid) return;
  grid.innerHTML = '';

  for (let p = 1; p <= 20; p++) {
    const onu = onus.find(o => String(o.puerto) === String(p)) || {};
    const hasMtk = mtkPorts && mtkPorts[p];
    const estado = onu.estado || (hasMtk ? 'CONECTADA' : 'SIN_ONU');

    let stClass = 'status-tag-idle';
    let cardClass = '';
    if (['LISTA', 'EXITO', 'YA_CONFIGURADA'].includes(estado)) {
      stClass = 'status-tag-ok'; cardClass = 'status-ok';
    } else if (['FLASHEANDO', 'WIZARD', 'REINICIANDO', 'VERIFICANDO', 'ESTABILIZANDO'].includes(estado)) {
      stClass = 'status-tag-busy'; cardClass = 'status-busy';
    } else if (['ERROR', 'PAUSA'].includes(estado)) {
      stClass = 'status-tag-err'; cardClass = 'status-err';
    }

    let detailText = onu.detalle || (hasMtk ? 'MAC: ' + hasMtk : 'Sin respuesta HTTP (esperando ONU nueva)');

    const card = document.createElement('div');
    card.className = `port-card ${cardClass}`;
    card.innerHTML = `
      <div class="port-header">
        <span class="port-num">Puerto ${p}</span>
        <span class="port-status-badge ${stClass}">${estado}</span>
      </div>
      <div class="port-detail" title="${detailText}">${detailText}</div>
    `;
    grid.appendChild(card);
  }
}

async function fetchLogs() {
  if (!CURRENT_ACTIVE_BOX) return;
  try {
    const res = await fetch('/api/logs');
    const data = await res.json();
    const box = document.getElementById('log-viewer');
    if (box) {
      box.textContent = (data.logs || []).join('\n');
      box.scrollTop = box.scrollHeight;
    }
  } catch(e) {}
}

async function fetchDiagnosis() {
  try {
    const res = await fetch('/api/diagnosis');
    const data = await res.json();
    const d = data.diagnosis || {};
    const mtkEl = document.getElementById('diag-mtk');
    const ipEl = document.getElementById('diag-ip');
    if (mtkEl) mtkEl.innerHTML = d.api_auth_ok ? '<span style="color:#34d399;">Conectado OK</span>' : '<span style="color:#f87171;">Sin Conexión</span>';
    if (ipEl) ipEl.textContent = d.current_ip || 'No asignada';
  } catch(e) {}
}

async function toggleEngine() {
  const btn = document.getElementById('btn-flash-toggle');
  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/status');
    const st = await res.json();
    if (st.process && st.process.running) {
      await fetch('/api/action/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    } else {
      const boxCode = CURRENT_ACTIVE_BOX ? CURRENT_ACTIVE_BOX.codigo_caja : null;
      await fetch('/api/action/start_continuo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ box_code: boxCode })
      });
    }
    await fetchStatus();
  } catch(err) {
    alert("❌ Error comunicando con el motor: " + err.message);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function fixNetworkIp() {
  const btn = document.getElementById('btn-fix-ip');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Configurando IP...';
  }
  try {
    const res = await fetch('/api/action/set_ip', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    });
    const data = await res.json();
    alert((data.success ? "✅ " : "⚠️ ") + data.message);
    fetchDiagnosis();
  } catch (err) {
    alert("❌ Error: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🔧 Auto-IP';
    }
  }
}

// INVENTARIO Y REPORTES
async function loadInventoryTable() {
  const desde = document.getElementById('filtro-desde')?.value;
  const hasta = document.getElementById('filtro-hasta')?.value;
  const modelo = document.getElementById('filtro-modelo')?.value;
  const caja = document.getElementById('filtro-caja')?.value;
  const search = document.getElementById('filtro-search')?.value;

  const q = new URLSearchParams();
  if (desde) q.append('fecha_desde', desde);
  if (hasta) q.append('fecha_hasta', hasta);
  if (modelo && modelo !== 'TODOS') q.append('modelo', modelo);
  if (caja && caja !== 'TODAS') q.append('codigo_caja', caja);
  if (search) q.append('search', search);

  try {
    const res = await fetch(`/api/inventory/records?${q.toString()}`);
    const data = await res.json();
    const tbody = document.getElementById('inventory-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!data.records || data.records.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:var(--text-muted);">No se encontraron registros coincidentes</td></tr>';
      return;
    }

    data.records.forEach(r => {
      const isOk = ['EXITO', 'YA_CONFIGURADA', 'CHECK_OK'].includes(r.resultado);
      const tagClass = isOk ? 'status-tag-ok' : 'status-tag-err';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-size:0.8rem; color:var(--text-muted);">${r.fecha_hora}</td>
        <td><strong>${r.codigo_caja || '-'}</strong></td>
        <td>${r.modelo_id}</td>
        <td><strong style="color:#60a5fa; font-family:monospace;">${r.pon_sn || r.pon_original || '-'}</strong></td>
        <td><span style="font-family:monospace;">${r.mac || '-'}</span></td>
        <td>P${r.puerto}</td>
        <td><span class="tag-badge ${tagClass}">${r.resultado}</span></td>
        <td>${r.vlan_ok === 'SI' ? '✅ SI' : '❌ NO'}</td>
        <td style="font-size:0.8rem; color:var(--text-muted);">${r.detalles || ''}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch(err) {
    console.error("Error cargando inventario:", err);
  }
}

async function loadBoxFilterOptions() {
  try {
    const res = await fetch('/api/boxes/list');
    const data = await res.json();
    const select = document.getElementById('filtro-caja');
    if (!select) return;
    const curVal = select.value;
    select.innerHTML = '<option value="TODAS">Todas las cajas</option>';
    (data.boxes || []).forEach(b => {
      const opt = document.createElement('option');
      opt.value = b.codigo_caja;
      opt.textContent = `${b.codigo_caja} (${b.modelo_id}) - ${b.cantidad_procesadas}/${b.cantidad_total}`;
      select.appendChild(opt);
    });
    if (curVal) select.value = curVal;
  } catch(e) {}
}

function exportFilteredExcel() {
  const desde = document.getElementById('filtro-desde')?.value;
  const hasta = document.getElementById('filtro-hasta')?.value;
  const modelo = document.getElementById('filtro-modelo')?.value;
  const caja = document.getElementById('filtro-caja')?.value;
  const search = document.getElementById('filtro-search')?.value;

  const q = new URLSearchParams();
  if (desde) q.append('fecha_desde', desde);
  if (hasta) q.append('fecha_hasta', hasta);
  if (modelo && modelo !== 'TODOS') q.append('modelo', modelo);
  if (caja && caja !== 'TODAS') q.append('codigo_caja', caja);
  if (search) q.append('search', search);

  window.location.href = `/api/inventory/export_excel?${q.toString()}`;
}

function exportFilteredCsv() {
  const desde = document.getElementById('filtro-desde')?.value;
  const hasta = document.getElementById('filtro-hasta')?.value;
  const modelo = document.getElementById('filtro-modelo')?.value;
  const caja = document.getElementById('filtro-caja')?.value;
  const search = document.getElementById('filtro-search')?.value;

  const q = new URLSearchParams();
  if (desde) q.append('fecha_desde', desde);
  if (hasta) q.append('fecha_hasta', hasta);
  if (modelo && modelo !== 'TODOS') q.append('modelo', modelo);
  if (caja && caja !== 'TODAS') q.append('codigo_caja', caja);
  if (search) q.append('search', search);

  window.location.href = `/api/inventory/export_csv?${q.toString()}`;
}

function exportBoxExcel() {
  if (!CURRENT_ACTIVE_BOX) {
    alert("⚠️ No hay una caja activa seleccionada.");
    return;
  }
  window.location.href = `/api/inventory/export_excel?codigo_caja=${encodeURIComponent(CURRENT_ACTIVE_BOX.codigo_caja)}`;
}

function exportCompletedBoxExcel() {
  const code = LAST_COMPLETED_BOX_CODE || (CURRENT_ACTIVE_BOX ? CURRENT_ACTIVE_BOX.codigo_caja : null);
  if (!code) {
    alert("⚠️ No se encontró código de caja completada.");
    return;
  }
  window.location.href = `/api/inventory/export_excel?codigo_caja=${encodeURIComponent(code)}`;
}

// MODELOS & CONFIG
async function loadModelsView() {
  try {
    const res = await fetch('/api/profiles');
    const data = await res.json();
    ALL_MODELS = data.models || [];

    const container = document.getElementById('models-cards-grid');
    if (container) {
      container.innerHTML = '';
      ALL_MODELS.forEach(m => {
        const card = document.createElement('div');
        card.className = 'card';
        card.style.background = 'var(--bg-input)';
        card.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.5rem;">
            <h4 style="font-size:1.1rem; color:#60a5fa;">${m.id}</h4>
            <span class="tag-badge" style="background:#1e3a8a; color:#93c5fd;">${m.hardware_type || 'G/EPON'}</span>
          </div>
          <div style="font-size:0.9rem; font-weight:600; margin-bottom:0.5rem;">${m.commercial_name || m.name}</div>
          <div style="font-size:0.8rem; color:var(--text-muted); margin-bottom:0.75rem;">
            Firmware: <span style="color:#fff;">${m.firmware}</span> (${m.firmware_exists ? '✅ ' + m.firmware_size_mb + 'MB' : '❌ Falta'})
          </div>
          <div style="font-size:0.8rem; color:var(--text-muted); margin-bottom:1rem;">
            VLAN: <strong>${m.target_vlan_id || 3}</strong> | Def Qty: <strong>${m.box_default_qty || 20}</strong>
          </div>
          <div style="display:flex; justify-content:space-between; gap:0.5rem;">
            <button type="button" class="btn btn-sm ${m.is_active ? 'btn-success' : 'btn-primary'}" onclick="setActiveModel('${m.id}')">
              ${m.is_active ? '⭐ Activo' : 'Seleccionar'}
            </button>
            <button type="button" class="btn btn-sm btn-danger" onclick="deleteModel('${m.id}')">🗑️ Eliminar</button>
          </div>
        `;
        container.appendChild(card);
      });
    }

    const setupSelect = document.getElementById('setup-input-model');
    const filSelect = document.getElementById('filtro-modelo');
    if (setupSelect) {
      setupSelect.innerHTML = '';
      ALL_MODELS.forEach(m => {
        const opt1 = document.createElement('option');
        opt1.value = m.id;
        opt1.textContent = `${m.id} - ${m.commercial_name || m.name}`;
        if (m.is_active) opt1.selected = true;
        setupSelect.appendChild(opt1);
      });
      handleSetupModelChange();
    }

    if (filSelect) {
      const curFil = filSelect.value;
      filSelect.innerHTML = '<option value="TODOS">Todos los modelos</option>';
      ALL_MODELS.forEach(m => {
        const opt2 = document.createElement('option');
        opt2.value = m.id;
        opt2.textContent = m.id;
        filSelect.appendChild(opt2);
      });
      if (curFil) filSelect.value = curFil;
    }
  } catch(err) {
    console.error("Error cargando modelos:", err);
  }
}

async function openNewModelModal() {
  openModal('modal-model');
  const select = document.getElementById('m-input-fw');
  if (select) {
    select.innerHTML = '<option value="">Cargando firmwares disponibles...</option>';
    try {
      const res = await fetch('/api/firmwares/available');
      const data = await res.json();
      select.innerHTML = '';
      if (data.firmwares && data.firmwares.length > 0) {
        data.firmwares.forEach(f => {
          const opt = document.createElement('option');
          opt.value = f.filename;
          opt.textContent = `${f.filename} (${f.size_mb} MB)`;
          select.appendChild(opt);
        });
      } else {
        select.innerHTML = '<option value="">No hay archivos .bin en firmwares/</option>';
      }
    } catch (err) {
      console.error("Error cargando firmwares:", err);
    }
  }

  const idIn = document.getElementById('m-input-id');
  const nmIn = document.getElementById('m-input-name');
  if (idIn) idIn.value = '';
  if (nmIn) nmIn.value = '';
  const defU = document.getElementById('m-input-defuser');
  const defP = document.getElementById('m-input-defpass');
  const finU = document.getElementById('m-input-finuser');
  const finP = document.getElementById('m-input-finpass');
  const vlanIn = document.getElementById('m-input-vlan');
  const qtyIn = document.getElementById('m-input-boxqty');

  if (defU) defU.value = 'admin';
  if (defP) defP.value = 'stdONU101';
  if (finU) finU.value = 'Powerlink';
  if (finP) finP.value = 'Powerlink2026*';
  if (vlanIn) vlanIn.value = '3';
  if (qtyIn) qtyIn.value = '20';
}

async function handleSaveModel(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-save-model') || (e.target ? e.target.querySelector('button[type="submit"]') : null);
  const oldText = btn ? btn.innerHTML : '💾 Guardar Modelo';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Guardando...';
  }

  const payload = {
    id: document.getElementById('m-input-id').value.trim(),
    commercial_name: document.getElementById('m-input-name').value.trim(),
    firmware: document.getElementById('m-input-fw').value,
    default_user: document.getElementById('m-input-defuser').value.trim(),
    default_pass: document.getElementById('m-input-defpass').value.trim(),
    final_user: document.getElementById('m-input-finuser').value.trim(),
    final_pass: document.getElementById('m-input-finpass').value.trim(),
    target_vlan_id: document.getElementById('m-input-vlan').value.trim(),
    box_default_qty: parseInt(document.getElementById('m-input-boxqty').value) || 20,
  };

  try {
    const res = await fetch('/api/models/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      alert("✅ " + data.message);
      closeModal('modal-model');
      await loadModelsView();
      await fetchStatus();
    } else {
      alert("⚠️ Error al guardar: " + (data.message || 'No se pudo guardar el modelo'));
    }
  } catch (err) {
    alert("❌ Error de comunicación con el servidor: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = oldText;
    }
  }
}

async function setActiveModel(modelId) {
  try {
    const res = await fetch('/api/profiles/active', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId })
    });
    const data = await res.json();
    if (data.success) {
      await loadModelsView();
      await fetchStatus();
    } else {
      alert("⚠️ " + data.message);
    }
  } catch(err) {
    alert("❌ Error: " + err.message);
  }
}

async function deleteModel(modelId) {
  if (!confirm(`¿Estás seguro de eliminar el modelo ${modelId}?`)) return;
  try {
    const res = await fetch('/api/models/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId })
    });
    const data = await res.json();
    if (data.success) {
      alert("✅ " + data.message);
      await loadModelsView();
      await fetchStatus();
    } else {
      alert("⚠️ " + data.message);
    }
  } catch(err) {
    alert("❌ Error: " + err.message);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  loadModelsView();
  fetchStatus();
  fetchDiagnosis();
  setInterval(fetchStatus, 2000);
  setInterval(fetchLogs, 2500);
});
</script>
</body>
</html>
"""
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_web_server(port=DEFAULT_PORT, open_browser=False):
    db.init_db()
    mon_t = threading.Thread(target=_background_monitor_loop, daemon=True)
    mon_t.start()

    server_address = ("", port)
    httpd = ThreadedHTTPServer(server_address, StationAPIHandler)
    url = f"http://localhost:{port}/"
    print(f"\n=======================================================")
    print(f"  Estación de Flasheo e Inventario Powerlink Iniciada")
    print(f"  Panel Web Multi-hilo: {url}")
    print(f"=======================================================")
    if open_browser:
        try:
            import webbrowser
            threading.Timer(0.8, lambda: webbrowser.open(url)).start()
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        _stop_flash_process()
        print("\nServidor web detenido.")


run_server = run_web_server


if __name__ == "__main__":
    p = DEFAULT_PORT
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        p = int(sys.argv[1])
    run_web_server(p, open_browser=True)
