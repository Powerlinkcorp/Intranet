# -*- coding: utf-8 -*-
"""
api_smartolt.py — Controladores de endpoints para la integración con SmartOLT.
"""
import json
import os
from aprovisionamiento.core.services.smartolt_service import SmartOLTService

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_FILE = os.path.join(PROJECT_ROOT, "config", "settings.json")


def handle_get_unconfigured() -> tuple:
    res = SmartOLTService.get_unconfigured_onus(filter_vsol=True)
    if res.get("status"):
        vsol_onus = res.get("onus") or []
        total_raw = res.get("total_raw", len(vsol_onus))
        return ({"success": True, "onus": vsol_onus, "total_vsol": len(vsol_onus), "total_raw": total_raw}, 200)
    return ({"success": False, "error": res.get("error", "Error al consultar SmartOLT")}, 400)


def handle_get_onu_status(sn: str) -> tuple:
    sn_clean = (sn or "").strip().upper()
    if not sn_clean:
        return ({"success": False, "error": "Número de serie PON requerido"}, 400)
    
    res = SmartOLTService.get_onu_details(sn_clean)
    if res.get("status"):
        onus = res.get("onus") or []
        if onus:
            onu = dict(onus[0])
            # Intentar obtener la MAC aprendida en VLAN 3, IP e info Wi-Fi desde SmartOLT
            mac_info = SmartOLTService.get_onu_learned_mac_vlan3(sn_clean)
            if mac_info.get("mac"):
                onu["mac_vlan3"] = mac_info.get("mac")
                onu["all_macs"] = mac_info.get("all_macs", [])
            if mac_info.get("ip"):
                onu["ip"] = mac_info.get("ip")
            onu["has_wifi"] = mac_info.get("has_wifi", True)
            if mac_info.get("model"):
                onu["detected_model"] = mac_info.get("model")
            return ({"success": True, "configured": True, "onu": onu}, 200)
        return ({"success": True, "configured": False, "message": "ONU no registrada como configurada"}, 200)
    return ({"success": False, "error": res.get("error", "Error al consultar detalles en SmartOLT")}, 400)


def handle_get_onu_mac(sn: str) -> tuple:
    sn_clean = (sn or "").strip().upper()
    if not sn_clean:
        return ({"success": False, "error": "Número de serie PON requerido"}, 400)
    res = SmartOLTService.get_onu_learned_mac_vlan3(sn_clean)
    if res.get("status"):
        return ({
            "success": True,
            "mac": res.get("mac"),
            "vlan": res.get("vlan", "3"),
            "all_macs": res.get("all_macs", []),
            "ip": res.get("ip"),
            "has_wifi": res.get("has_wifi", True),
            "model": res.get("model", "VSOL")
        }, 200)
    # Si aún no aprende MAC pero ya tiene IP o información del modelo
    return ({
        "success": False,
        "error": res.get("error", "MAC no disponible aún en la OLT"),
        "ip": res.get("ip"),
        "has_wifi": res.get("has_wifi", True),
        "model": res.get("model", "VSOL")
    }, 404)



def handle_smartolt_authorize(req_data: dict) -> tuple:
    sn = (req_data.get("sn") or "").strip().upper()
    dba_profile = (req_data.get("dba_profile") or "").strip()
    zone = req_data.get("zone")
    odb = req_data.get("odb")
    name = req_data.get("name")
    address = req_data.get("address")

    if not sn:
        return ({"success": False, "error": "El número de serie PON (SN) es obligatorio"}, 400)
    if not dba_profile:
        return ({"success": False, "error": "El perfil DBA / Velocidad es obligatorio"}, 400)

    res = SmartOLTService.authorize_vsol_vlan3(
        sn=sn,
        dba_profile=dba_profile,
        zone=zone,
        odb=odb,
        name=name,
        address=address
    )

    if res.get("status"):
        return ({"success": True, "message": f"ONU {sn} autorizada en SmartOLT con VLAN 3 y perfil {dba_profile}", "data": res}, 200)
    return ({"success": False, "error": res.get("error", "Fallo al autorizar en SmartOLT")}, 400)


def handle_smartolt_migrate_vlan(req_data: dict, auth_user: dict = None) -> tuple:
    sn = (req_data.get("sn") or "").strip().upper()
    target_vlan = str(req_data.get("target_vlan") or "").strip()
    ip = str(req_data.get("ip") or "").strip()
    mac = str(req_data.get("mac") or "").strip()
    ssid_2g = str(req_data.get("ssid_2g") or "").strip()
    ssid_5g = str(req_data.get("ssid_5g") or "").strip()
    username = (auth_user.get("username") if auth_user else "admin") or "admin"

    if not sn:
        return ({"success": False, "error": "El número de serie PON (SN) es obligatorio"}, 400)
    if not target_vlan:
        return ({"success": False, "error": "La VLAN destino del Hub es obligatoria"}, 400)

    res = SmartOLTService.update_onu_vlan(sn=sn, target_vlan=target_vlan)
    if res.get("status"):
        try:
            from core.services.history_service import HistoryService
            HistoryService.log(
                ip=ip, mac=mac, pon_serial=sn, modelo="VSOLVD64",
                vlan=target_vlan, ssid_2g=ssid_2g, ssid_5g=ssid_5g,
                resultado="EXITO", detalles=f"Migrada a VLAN {target_vlan} en SmartOLT",
                usuario=username
            )
        except Exception:
            pass
        return ({"success": True, "message": f"VLAN de la ONU {sn} migrada exitosamente a VLAN {target_vlan}", "data": res}, 200)
    return ({"success": False, "error": res.get("error", "Fallo al migrar VLAN en SmartOLT")}, 400)


def handle_smartolt_release_onu(req_data: dict, auth_user: dict = None) -> tuple:
    sn = (req_data.get("sn") or "").strip().upper()
    target_vlan = str(req_data.get("target_vlan") or "").strip()
    ip = str(req_data.get("ip") or "").strip()
    mac = str(req_data.get("mac") or "").strip()
    ssid_2g = str(req_data.get("ssid_2g") or "").strip()
    ssid_5g = str(req_data.get("ssid_5g") or "").strip()
    username = (auth_user.get("username") if auth_user else "admin") or "admin"

    if not sn:
        return ({"success": False, "error": "El número de serie PON (SN) es obligatorio"}, 400)

    res = SmartOLTService.delete_onu(sn=sn)
    if res.get("status"):
        try:
            from core.services.history_service import HistoryService
            HistoryService.log(
                ip=ip, mac=mac, pon_serial=sn, modelo="VSOLVD64",
                vlan=target_vlan or "Desconfigurada", ssid_2g=ssid_2g, ssid_5g=ssid_5g,
                resultado="EXITO (Liberada)",
                detalles=f"VLAN {target_vlan} grabada en ONU. Liberada en SmartOLT para aprovisionamiento por Rubpi.",
                usuario=username
            )
        except Exception:
            pass
        return ({"success": True, "message": f"ONU {sn} liberada exitosamente en SmartOLT. Ya se encuentra en desconfiguradas para ser aprovisionada por Rubpi.", "data": res}, 200)
    return ({"success": False, "error": res.get("error", "Fallo al liberar ONU en SmartOLT")}, 400)



def handle_get_smartolt_profiles() -> tuple:
    dbas = SmartOLTService.get_dba_profiles()
    speeds = SmartOLTService.get_speed_profiles()
    return ({"success": True, "dba_profiles": dbas, "speed_profiles": speeds}, 200)


def handle_save_smartolt_config(req_data: dict) -> tuple:
    api_key = (req_data.get("api_key") or "").strip()
    base_url = (req_data.get("base_url") or "https://powerlinkcorp.telecomti.net/api").strip()

    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    current_settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                current_settings = json.load(f)
        except Exception:
            pass

    current_settings.setdefault("smartolt", {})
    if api_key:
        current_settings["smartolt"]["api_key"] = api_key
    if base_url:
        current_settings["smartolt"]["base_url"] = base_url

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current_settings, f, indent=2, ensure_ascii=False)

    return ({"success": True, "message": "Configuración de SmartOLT guardada exitosamente"}, 200)
