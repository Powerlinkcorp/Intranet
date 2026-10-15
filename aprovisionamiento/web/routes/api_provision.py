# -*- coding: utf-8 -*-
"""
api_provision.py — Controladores de endpoints para sondeo y aprovisionamiento.
"""
from aprovisionamiento.core.services.provision_service import ProvisionService


def handle_probe(req_data: dict) -> tuple:
    ip = (req_data.get("ip") or "").strip()
    sn = (req_data.get("sn") or "").strip().upper()
    mac = (req_data.get("mac") or "").strip().upper()
    if not ip:
        return ({"success": False, "error": "IP de la ONU es requerida"}, 400)
    
    job_id = ProvisionService.start_probe_async(ip, sn=sn if sn else None, mac=mac if mac else None)
    return ({"success": True, "job_id": job_id, "message": f"Sondeo iniciado en {ip}"}, 200)


def handle_provision(req_data: dict) -> tuple:
    ip = (req_data.get("ip") or "").strip()
    vlan = str(req_data.get("vlan") or "3").strip()
    ssid_2g = (req_data.get("ssid_2g") or "").strip()
    pass_2g = (req_data.get("pass_2g") or "").strip()
    ssid_5g = (req_data.get("ssid_5g") or "").strip()
    pass_5g = (req_data.get("pass_5g") or pass_2g).strip()
    sn = (req_data.get("sn") or "").strip().upper()
    mac = (req_data.get("mac") or "").strip().upper()
    dba_profile = (req_data.get("dba_profile") or "").strip()
    target_vlan = str(req_data.get("target_vlan") or vlan).strip()

    if not ip:
        return ({"success": False, "error": "IP requerida"}, 400)
    if not vlan:
        return ({"success": False, "error": "VLAN requerida"}, 400)
    if not ssid_2g:
        return ({"success": False, "error": "Nombre de red Wi-Fi 2.4G requerido"}, 400)
    if not pass_2g or len(pass_2g) < 8:
        return ({"success": False, "error": "Contraseña Wi-Fi debe contener al menos 8 caracteres"}, 400)

    job_id = ProvisionService.start_provision_async(
        ip=ip, vlan=vlan,
        ssid_2g=ssid_2g, pass_2g=pass_2g,
        ssid_5g=ssid_5g, pass_5g=pass_5g,
        sn=sn if sn else None,
        dba_profile=dba_profile if dba_profile else None,
        target_vlan=target_vlan if target_vlan else None,
        mac=mac if mac else None
    )
    return ({"success": True, "job_id": job_id, "message": f"Aprovisionamiento iniciado en {ip}"}, 200)


def handle_provision_onu_only(req_data: dict) -> tuple:
    """Maneja la configuración exclusiva del router ONU (Paso 2)."""
    ip = (req_data.get("ip") or "").strip()
    vlan = str(req_data.get("vlan") or "").strip()
    ssid_2g = (req_data.get("ssid_2g") or "").strip()
    pass_2g = (req_data.get("pass_2g") or "").strip()
    ssid_5g = (req_data.get("ssid_5g") or "").strip()
    pass_5g = (req_data.get("pass_5g") or pass_2g).strip()
    sn = (req_data.get("sn") or "").strip().upper()
    mac = (req_data.get("mac") or "").strip().upper()
    has_wifi = req_data.get("has_wifi", True)

    if not ip:
        return ({"success": False, "error": "Dirección IP de la ONU es requerida"}, 400)
    if not vlan:
        return ({"success": False, "error": "VLAN del HUB es requerida"}, 400)

    # Si es modelo sin Wi-Fi (monopuerto/Ethernet puro), omitir validación de contraseñas inalámbricas
    if not has_wifi or ssid_2g in ("N/A", "", None):
        ssid_2g = "N/A"
        pass_2g = "N/A"
        ssid_5g = "N/A"
        pass_5g = "N/A"
    else:
        if not ssid_2g:
            return ({"success": False, "error": "Nombre de red Wi-Fi 2.4G es requerido"}, 400)
        if not pass_2g or len(pass_2g) < 8:
            return ({"success": False, "error": "Contraseña Wi-Fi 2.4G debe contener al menos 8 caracteres"}, 400)

    job_id = ProvisionService.start_onu_router_provision_async(
        ip=ip,
        vlan=vlan,
        ssid_2g=ssid_2g,
        pass_2g=pass_2g,
        ssid_5g=ssid_5g,
        pass_5g=pass_5g,
        sn=sn if sn else None,
        mac=mac if mac else None
    )
    return ({"success": True, "job_id": job_id, "message": f"Configuración de router iniciada en {ip}"}, 200)


def handle_progress(job_id: str) -> tuple:
    job = ProvisionService.get_job(job_id)
    if job:
        res = dict(job)
        res["success"] = True
        res["progress"] = job.get("pct", 0)
        return (res, 200)
    return ({"success": False, "error": "Job no encontrado"}, 404)
