# -*- coding: utf-8 -*-
"""
api.v1.endpoints.flasheo — Rutas de Control de Flasheo (Continuo, Masivo, Individual).
"""
import json
import os
import subprocess
import sys
import threading
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
import mikrotik as mtk
import network_diag as netdiag
import profiles
from core import database
from core.schemas import FlasheoContinuoRequest, FlasheoSingleRequest
from api.v1.endpoints.auth import require_operator

router = APIRouter(prefix="/flasheo", tags=["Control de Flasheo"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
STATUS_FILE = os.path.join(LOGS_DIR, "estado.json")
LOG_FILE = os.path.join(LOGS_DIR, "continuo.log")
AUTOPILOT = os.path.join(PROJECT_ROOT, "core", "vsol_autopilot.py")
if not os.path.exists(AUTOPILOT):
    AUTOPILOT = os.path.join(PROJECT_ROOT, "vsol_autopilot.py")

FLASH_PROCESS = None
FLASH_PROCESS_LOCK = threading.Lock()
FLASH_INFO = {
    "running": False,
    "mode": None,
    "pid": None,
    "start_time": None,
    "model": None,
    "target_ip": None,
}


def get_process_status():
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


def start_flash_process(mode="continuo", model=None, ip=None, parallel=20, action="full"):
    global FLASH_PROCESS, FLASH_INFO
    with FLASH_PROCESS_LOCK:
        if FLASH_PROCESS is not None and FLASH_PROCESS.poll() is None:
            return False, "Ya hay un proceso de flasheo en ejecución."

        active_prof = profiles.get_active_profile(model)
        model_id = active_prof.get("id", "V2801S-B") if active_prof else "V2801S-B"
        profiles.set_active_model(model_id)

        cmd = [
            sys.executable,
            "-u",
            AUTOPILOT,
            "--headless",
            "--model",
            model_id,
        ]

        if action == "factory_reset":
            cmd.append("--factory-reset-only")
        elif action == "verify_vlan":
            cmd.append("--check")

        if mode == "continuo":
            cmd.extend(["--continuo", "--final-first", "--parallel", str(parallel)])
        elif mode == "masivo":
            cmd.extend(["--mass", "--parallel", str(parallel)])
        elif mode == "individual":
            target = ip or "192.168.1.1"
            cmd.extend(["--ip", target, "--final-first"])

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando flasheo ({mode}, acción={action}) modelo={model_id} paralelo={parallel} ip={ip}\n")

            log_out = open(LOG_FILE, "a", encoding="utf-8")
            FLASH_PROCESS = subprocess.Popen(
                cmd,
                stdout=log_out,
                stderr=subprocess.STDOUT,
                cwd=PROJECT_ROOT,
                shell=False
            )
            FLASH_INFO = {
                "running": True,
                "mode": mode,
                "pid": FLASH_PROCESS.pid,
                "start_time": time.time(),
                "model": model_id,
                "target_ip": ip,
            }
            return True, f"Proceso de flasheo ({mode}) iniciado con éxito (PID {FLASH_PROCESS.pid})"
        except Exception as ex:
            return False, f"Error iniciando proceso: {ex}"


def stop_flash_process():
    global FLASH_PROCESS, FLASH_INFO
    with FLASH_PROCESS_LOCK:
        if FLASH_PROCESS is not None and FLASH_PROCESS.poll() is None:
            try:
                FLASH_PROCESS.terminate()
                try:
                    FLASH_PROCESS.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    FLASH_PROCESS.kill()
                FLASH_PROCESS = None
                FLASH_INFO["running"] = False
                return True, "Proceso de flasheo detenido exitosamente."
            except Exception as ex:
                return False, f"Error al detener: {ex}"
        FLASH_PROCESS = None
        FLASH_INFO["running"] = False
        return True, "No había ningún proceso en ejecución."


def read_status_json():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"running": False, "onus": [], "total": 20, "timestamp": time.time()}


@router.get("/status", summary="Obtener estado consolidado de la estación y puertos")
def get_status():
    status_data = read_status_json()
    proc = get_process_status()
    lote = database.get_active_lote()
    
    # Mikrotik activo (solo consultar si el host responde en <200ms)
    active_ports = {}
    try:
        mtk_cfg = mtk.load_config()
        if mtk_cfg:
            import socket
            host = mtk_cfg.get("host", "10.100.0.1")
            port = int(mtk_cfg.get("port", 8728))
            test_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_s.settimeout(0.2)
            mtk_online = (test_s.connect_ex((host, port)) == 0)
            test_s.close()
            if mtk_online:
                active_ports = mtk.get_active_ports(mtk_cfg, quiet=True) or {}
    except Exception:
        pass

    onus = status_data.get("onus", [])
    counts = {
        "listas": sum(1 for o in onus if o.get("estado") in ("LISTA", "EXITO", "YA_CONFIGURADA")),
        "en_curso": sum(1 for o in onus if o.get("estado") in ("FLASHEANDO", "WIZARD", "REINICIANDO", "VERIFICANDO", "LOGIN")),
        "errores": sum(1 for o in onus if o.get("estado") in ("ERROR", "PAUSA")),
        "sin_onu": sum(1 for o in onus if o.get("estado") in ("SIN_ONU", None)),
        "total": status_data.get("total", len(onus) or 20),
    }

    # Comprobación de ONU directa en 192.168.1.1
    onu_direct_online = False
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        onu_direct_online = (s.connect_ex(("192.168.1.1", 80)) == 0)
        s.close()
    except Exception:
        pass

    return {
        "status": status_data,
        "counts": counts,
        "process": proc,
        "active_lote": lote,
        "mikrotik_active_ports": active_ports,
        "onu_direct_online": onu_direct_online,
        "server_time": time.time(),
    }


@router.post("/start_continuo", summary="Iniciar modo continuo para las 20 ONUs")
def start_continuo(req: FlasheoContinuoRequest, operator: dict = Depends(require_operator)):
    ok, msg = start_flash_process(mode="continuo", model=req.model, parallel=req.parallel)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.post("/start_single", summary="Iniciar acción de flasheo individual de una ONU")
def start_single(req: FlasheoSingleRequest, operator: dict = Depends(require_operator)):
    ip = req.ip
    if req.direct or not ip:
        if req.direct:
            ip = "192.168.1.1"
        elif req.puerto:
            ip = f"10.100.{req.puerto}.1"
        else:
            ip = "192.168.1.1"
    ok, msg = start_flash_process(mode="individual", model=req.model, ip=ip, action=req.action or "full")
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.post("/stop", summary="Detener inmediatamente el proceso de flasheo")
def stop_process(operator: dict = Depends(require_operator)):
    ok, msg = stop_flash_process()
    return {"success": ok, "message": msg}


@router.get("/logs", summary="Obtener registros de consola recientes")
def get_logs(max_lines: int = 250):
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                return {"logs": [ln.rstrip() for ln in lines[-max_lines:]]}
        except Exception:
            pass
    return {"logs": ["Esperando inicio del proceso de flasheo..."]}
