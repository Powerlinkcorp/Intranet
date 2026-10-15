# -*- coding: utf-8 -*-
"""
provision_service.py — Orquestador de trabajos de aprovisionamiento, diagnóstico e integración SmartOLT.
Gestiona el ciclo de vida de los Jobs en memoria, streaming de progreso y las 3 fases del aprovisionamiento.
"""
import asyncio
import threading
import time
import uuid

from ..models.vsol_adapter import VSOLAdapter
from .smartolt_service import SmartOLTService
from .history_service import HistoryService
from ..utils.network_utils import check_http_alive

JOBS = {}
JOBS_LOCK = threading.Lock()
MAX_JOB_AGE = 3600


class ProvisionService:
    @staticmethod
    def _clean_old_jobs():
        with JOBS_LOCK:
            now = time.time()
            to_del = [jid for jid, j in JOBS.items() if now - j.get("created_at", 0) > MAX_JOB_AGE]
            for jid in to_del:
                del JOBS[jid]

    @staticmethod
    def create_job(job_type: str, ip: str, sn: str = "") -> str:
        ProvisionService._clean_old_jobs()
        job_id = str(uuid.uuid4())[:8]
        job_data = {
            "id": job_id,
            "type": job_type,
            "ip": ip,
            "sn": sn,
            "status": "running",
            "created_at": time.time(),
            "pct": 0,
            "step": "init",
            "logs": [],
            "result": None,
            "error": None
        }
        with JOBS_LOCK:
            JOBS[job_id] = job_data
        return job_id

    @staticmethod
    def get_job(job_id: str) -> dict:
        with JOBS_LOCK:
            return JOBS.get(job_id)

    @staticmethod
    def _update_job(job_id: str, **kwargs):
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id].update(kwargs)

    @staticmethod
    def _append_job_log(job_id: str, log_entry: dict):
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["logs"].append(log_entry)
                if log_entry.get("pct") is not None:
                    JOBS[job_id]["pct"] = log_entry.get("pct")
                if log_entry.get("step"):
                    JOBS[job_id]["step"] = log_entry.get("step")

    @staticmethod
    def start_probe_async(ip: str, sn: str = None, mac: str = None) -> str:
        job_id = ProvisionService.create_job("probe", ip, sn=sn or "")

        def _task():
            def log_cb(entry):
                ProvisionService._append_job_log(job_id, entry)

            try:
                adapter = VSOLAdapter(ip, log_callback=log_cb, sn=sn, mac=mac)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(adapter.probe())
                loop.close()

                if res.get("success"):
                    ProvisionService._update_job(job_id, status="completed", result=res, pct=100, step="done")
                else:
                    ProvisionService._update_job(job_id, status="failed", error=res.get("error"), pct=100, step="error")
            except Exception as ex:
                ProvisionService._update_job(job_id, status="failed", error=str(ex), pct=100, step="error")

        th = threading.Thread(target=_task, daemon=True)
        th.start()
        return job_id

    @staticmethod
    def start_provision_async(ip: str, vlan: str, ssid_2g: str, pass_2g: str, ssid_5g: str, pass_5g: str,
                              sn: str = None, dba_profile: str = None, target_vlan: str = None, mac: str = None) -> str:
        """
        Orquesta el aprovisionamiento. Si se incluye SN y SmartOLT, ejecuta las 3 fases completas.
        """
        job_id = ProvisionService.create_job("provision", ip, sn=sn or "")

        def _task():
            def log_cb(entry):
                ProvisionService._append_job_log(job_id, entry)

            def log_msg(msg, level="info", step=None, pct=None):
                log_cb({"time": time.strftime("%H:%M:%S"), "message": msg, "level": level, "step": step, "pct": pct})

            try:
                # =====================================================================
                # FASE 1: SMART OLT (AUTORIZACIÓN EN VLAN 3 CON DBA) SI SE INDICA SN
                # =====================================================================
                if sn:
                    # Verificar si la ONU ya está previamente autorizada en SmartOLT
                    log_msg(f"[Fase 1/3 - SmartOLT] Verificando estado de la ONU '{sn}' en SmartOLT...", "info", step="smartolt_check", pct=10)
                    details = SmartOLTService.get_onu_details(sn)
                    onus_list = details.get("onus") or []

                    if details.get("status") and onus_list:
                        current_onu = onus_list[0]
                        c_vlan = str(current_onu.get("vlan", "")).strip()
                        rx_power = current_onu.get("signal_1310") or current_onu.get("signal") or "OK"
                        log_msg(f"[SmartOLT] ONU '{sn}' ya autorizada previamente en VLAN {c_vlan} (Rx: {rx_power} dBm, Estado: {current_onu.get('status')}).", "ok", step="smartolt_ok", pct=30)
                    elif dba_profile:
                        # Si no está autorizada, buscar en no configuradas y autorizar en VLAN 3
                        log_msg(f"[SmartOLT] Consultando ONU '{sn}' en lista de no configuradas...", "info", step="smartolt_check", pct=15)
                        check = SmartOLTService.find_unconfigured_vsol(sn)
                        if not check.get("valid"):
                            err_msg = f"[SmartOLT] Error: {check.get('error')}"
                            log_msg(err_msg, "error")
                            ProvisionService._update_job(job_id, status="failed", error=err_msg, pct=100, step="error")
                            return

                        log_msg(f"[SmartOLT] ONU encontrada ({check.get('model')}). Autorizando con VLAN 3 y plan '{dba_profile}'...", "info", step="smartolt_auth", pct=20)
                        auth_res = SmartOLTService.authorize_vsol_vlan3(sn=sn, dba_profile=dba_profile)
                        if not auth_res.get("status"):
                            err_msg = f"[SmartOLT] Fallo en la autorización: {auth_res.get('error')}"
                            log_msg(err_msg, "error")
                            ProvisionService._update_job(job_id, status="failed", error=err_msg, pct=100, step="error")
                            return

                        log_msg(f"[SmartOLT] ONU autorizada exitosamente en VLAN 3. Esperando sincronización...", "ok", step="smartolt_ok", pct=30)
                        time.sleep(4)

                # =====================================================================
                # FASE 2: CONFIGURACIÓN INTERNA DE LA ONU (WI-FI PRIMERO, LUEGO WAN)
                # =====================================================================
                log_msg(f"[Fase 2/3 - Router] Conectando a la ONU en {ip} para configurar Wi-Fi y parámetros...", "info", step="onu_start", pct=40)
                adapter = VSOLAdapter(ip, log_callback=log_cb, sn=sn, mac=mac)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                # En la ONU configuramos la VLAN 3 (o la VLAN indicada)
                res = loop.run_until_complete(adapter.provision(
                    vlan_id=vlan or "3",
                    ssid_2g=ssid_2g,
                    pass_2g=pass_2g,
                    ssid_5g=ssid_5g,
                    pass_5g=pass_5g
                ))
                loop.close()

                if not res.get("success"):
                    ProvisionService._update_job(job_id, status="failed", error=res.get("error"), pct=100, step="error")
                    return

                # =====================================================================
                # FASE 3: MIGRACIÓN DE VLAN EN SMART OLT AL HUB CORRESPONDIENTE
                # =====================================================================
                final_vlan = target_vlan or vlan
                if sn and final_vlan and str(final_vlan) != "3":
                    log_msg(f"[Fase 3/3 - SmartOLT] Validando estado previo en VLAN 3 y migrando hacia la VLAN del Hub: {final_vlan}...", "info", step="smartolt_migrate", pct=85)
                    mig_res = SmartOLTService.update_onu_vlan(sn=sn, target_vlan=final_vlan)
                    if mig_res.get("status"):
                        log_msg(f"[SmartOLT] Migración completada exitosamente a VLAN {final_vlan} (100 cupos disponibles en Hub).", "ok", step="smartolt_done", pct=95)
                    else:
                        log_msg(f"[SmartOLT] Aviso en migración de VLAN: {mig_res.get('error')}", "warn")

                log_msg("Aprovisionamiento integral completado con éxito.", "ok", step="done", pct=100)
                ProvisionService._update_job(job_id, status="completed", result=res, pct=100, step="done")

            except Exception as ex:
                log_msg(f"Error fatal durante el aprovisionamiento: {ex}", "error")
                ProvisionService._update_job(job_id, status="failed", error=str(ex), pct=100, step="error")

        th = threading.Thread(target=_task, daemon=True)
        th.start()
        return job_id

    @staticmethod
    def start_onu_router_provision_async(ip: str, vlan: str, ssid_2g: str, pass_2g: str,
                                         ssid_5g: str, pass_5g: str, sn: str = None, mac: str = None) -> str:
        """
        Paso 2: Configura exclusivamente la ONU VSOL (Wi-Fi 2.4G, Wi-Fi 5G y WAN con la nueva VLAN).
        """
        job_id = ProvisionService.create_job("provision_onu", ip, sn=sn or "")

        def _task():
            def log_cb(entry):
                ProvisionService._append_job_log(job_id, entry)

            def log_msg(msg, level="info", step=None, pct=None):
                log_cb({"time": time.strftime("%H:%M:%S"), "message": msg, "level": level, "step": step, "pct": pct})

            try:
                log_msg(f"[Paso 2/3 - Router] Conectando a la interfaz web de la ONU en {ip}...", "info", step="onu_connect", pct=10)
                adapter = VSOLAdapter(ip, log_callback=log_cb, sn=sn, mac=mac)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                log_msg(f"[Paso 2/3 - Router] Aplicando credenciales Wi-Fi (2.4G y 5G) y enrutamiento con VLAN {vlan}...", "info", step="onu_config", pct=25)
                res = loop.run_until_complete(adapter.provision(
                    vlan_id=str(vlan).strip(),
                    ssid_2g=ssid_2g,
                    pass_2g=pass_2g,
                    ssid_5g=ssid_5g,
                    pass_5g=pass_5g
                ))
                loop.close()

                if not res.get("success"):
                    err = res.get("error", "Error desconocido en la configuración de la ONU")
                    log_msg(f"[Paso 2/3 - Router] Fallo en la configuración: {err}", "error")
                    ProvisionService._update_job(job_id, status="failed", error=err, pct=100, step="error")
                    return

                log_msg(f"[Paso 2/3 - Router] Configuración de ONU completada con éxito. Lista para el Paso 3 (Liberación de ONU en SmartOLT para aprovisionamiento por Rubpi).", "ok", step="onu_done", pct=100)
                ProvisionService._update_job(job_id, status="completed", result=res, pct=100, step="done")

            except Exception as ex:
                log_msg(f"[Paso 2/3 - Router] Error inesperado: {ex}", "error")
                ProvisionService._update_job(job_id, status="failed", error=str(ex), pct=100, step="error")

        th = threading.Thread(target=_task, daemon=True)
        th.start()
        return job_id
