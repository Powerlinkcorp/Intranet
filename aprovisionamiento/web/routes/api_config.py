# -*- coding: utf-8 -*-
"""
api_config.py — Controladores de endpoints para configuración del sistema y credenciales.
"""
import json
import os
from aprovisionamiento.core.services.credentials_service import CredentialsService

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_FILE = os.path.join(PROJECT_ROOT, "config", "settings.json")


def _load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "server": {"host": "0.0.0.0", "port": 8088},
        "default_onu_ip": "3.3.",
        "default_vlan": "3",
        "common_vlans": ["3", "100", "200", "300", "1000"]
    }


def handle_get_config() -> tuple:
    return ({"success": True, "config": _load_settings()}, 200)


def handle_save_config(data: dict) -> tuple:
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return ({"success": True, "message": "Configuración guardada"}, 200)


def handle_get_credentials() -> tuple:
    creds = CredentialsService.load()
    return ({"success": True, "active_user": creds.get("active_credentials", {}).get("username", "Powerlink"), "total_candidates": len(creds.get("candidate_credentials", []))}, 200)


def handle_save_credentials(data: dict) -> tuple:
    CredentialsService.save(data)
    return ({"success": True, "message": "Credenciales actualizadas"}, 200)


def handle_system_status() -> tuple:
    return ({"status": "online", "app": "Aprovisionamiento Automático", "version": "2.0.0"}, 200)


def handle_get_vlans_catalog(olt_id: str = None) -> tuple:
    import re
    from core.services.history_service import HistoryService
    from core.services.smartolt_service import SmartOLTService

    cfg = _load_settings()
    hub_vlans = cfg.get("hub_vlans", [])
    counts = HistoryService.get_vlan_usage_counts()

    catalog = []
    seen_vlans = set()

    # 1. Obtener catálogo dinámico desde SmartOLT con descripciones (planes de velocidad)
    smart_vlans = SmartOLTService.get_vlans(olt_id=olt_id)
    for v in smart_vlans:
        raw_vlan = str(v.get("vlan") or "").strip()
        desc = str(v.get("description") or "").strip()
        if desc == "None" or desc.lower() == "null":
            desc = ""

        if " - " in raw_vlan:
            parts = raw_vlan.split(" - ", 1)
            vlan_str = parts[0].strip()
            display_desc = desc if desc else parts[1].strip()
        else:
            vlan_str = raw_vlan
            display_desc = desc

        m = re.match(r"^(\d+)", vlan_str)
        vlan_num = m.group(1) if m else vlan_str

        # Omitir VLAN 3 (reservada para gestión inicial)
        if not vlan_num or vlan_num == "3":
            continue

        dedup_key = (vlan_num, display_desc) if olt_id else (vlan_num, display_desc, str(v.get("olt_id")))
        if dedup_key in seen_vlans:
            continue
        seen_vlans.add(dedup_key)

        used = counts.get(vlan_num, 0)
        max_cap = 100
        available = max(0, max_cap - used)

        label = f"{vlan_num} - {display_desc}" if display_desc else f"VLAN {vlan_num}"

        catalog.append({
            "vlan": vlan_num,
            "hub": label,
            "description": display_desc,
            "label": label,
            "olt_id": v.get("olt_id"),
            "olt_name": v.get("olt_name", ""),
            "used": used,
            "max_capacity": max_cap,
            "available": available
        })

    # 2. Agregar los HUBs configurados manualmente en settings que no estén ya en la lista
    configured_vlan_nums = {c["vlan"] for c in catalog}
    for item in hub_vlans:
        vlan = str(item.get("vlan", "")).strip()
        if vlan and vlan not in configured_vlan_nums and vlan != "3":
            hub = item.get("hub", f"HUB VLAN {vlan}")
            desc = item.get("description", hub)
            max_cap = int(item.get("max_capacity", 100))
            used = counts.get(vlan, 0)
            available = max(0, max_cap - used)
            configured_vlan_nums.add(vlan)
            label = f"{vlan} - {hub}" if not hub.startswith(vlan) else hub
            catalog.append({
                "vlan": vlan,
                "hub": label,
                "description": desc,
                "label": label,
                "olt_id": None,
                "olt_name": "",
                "used": used,
                "max_capacity": max_cap,
                "available": available
            })

    # 3. Agregar cualquier otra VLAN que haya sido usada en el historial
    for vlan, used in counts.items():
        if vlan not in configured_vlan_nums and vlan != "3":
            label = f"{vlan} - Histórica"
            catalog.append({
                "vlan": vlan,
                "hub": label,
                "description": "Histórica",
                "label": label,
                "olt_id": None,
                "olt_name": "",
                "used": used,
                "max_capacity": 100,
                "available": max(0, 100 - used)
            })

    # Ordenar numéricamente por VLAN ID
    catalog.sort(key=lambda x: int(x["vlan"]) if x["vlan"].isdigit() else 999999)

    return ({"success": True, "vlans": catalog, "catalog": catalog, "total": len(catalog)}, 200)


def handle_flasheo_traceability(query_str: str) -> tuple:
    """
    Consulta la trazabilidad y credenciales del lote de una ONU en la Estación de Flasheo.
    """
    try:
        from aprovisionamiento.core.services.flasheo_integration_service import FlasheoIntegrationService
    except ImportError:
        try:
            from core.services.flasheo_integration_service import FlasheoIntegrationService
        except ImportError:
            FlasheoIntegrationService = None

    if not query_str or not str(query_str).strip():
        return ({"success": False, "encontrado": False, "error": "Parámetro query (MAC o Serial) es requerido"}, 400)
    if FlasheoIntegrationService:
        data = FlasheoIntegrationService.lookup(str(query_str).strip())
        if not data or not data.get("encontrado"):
            return ({"success": True, "encontrado": False, "mensaje": "ONU no registrada en la base de datos de Estación de Flasheo"}, 200)
        return ({"success": True, "encontrado": True, **data}, 200)
    return ({"success": True, "encontrado": False, "mensaje": "Servicio de integración no disponible"}, 200)

