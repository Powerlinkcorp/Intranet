# -*- coding: utf-8 -*-
"""
test_e2e.py — Prueba de integración y aprovisionamiento extremo a extremo.
"""
import asyncio
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from aprovisionamiento.core.services.provision_service import ProvisionService
from aprovisionamiento.core.services.history_service import HistoryService


def test_modular_provision():
    print("Iniciando prueba e2e con la nueva arquitectura modular...")
    ip = "3.3.2.19"
    vlan = "3"
    ssid_2g = "Powerlink_E2E"
    pass_2g = "Powerlink2026*"
    ssid_5g = "Powerlink_E2E_5G"
    pass_5g = "Powerlink2026*"

    job_id = ProvisionService.start_provision_async(
        ip=ip, vlan=vlan,
        ssid_2g=ssid_2g, pass_2g=pass_2g,
        ssid_5g=ssid_5g, pass_5g=pass_5g
    )
    print(f"Job ID generado: {job_id}")

    import time
    for _ in range(60):
        time.sleep(1)
        job = ProvisionService.get_job(job_id)
        if not job:
            continue
        status = job.get("status")
        pct = job.get("pct", 0)
        step = job.get("step", "")
        if job.get("logs"):
            latest_msg = job["logs"][-1]["message"]
            print(f"[{pct}% - {step}] {latest_msg}")
        
        if status in ("completed", "failed"):
            print(f"\nResultado final: {status.upper()}")
            print(f"Detalle: {job.get('result') or job.get('error')}")
            assert status == "completed", f"El job falló: {job.get('error')}"
            assert job.get("result", {}).get("success") is True
            print("¡Prueba de integración exitosa!")
            return

    raise TimeoutError("La prueba excedió el tiempo límite")


if __name__ == "__main__":
    test_modular_provision()
