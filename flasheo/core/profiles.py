# -*- coding: utf-8 -*-
"""
core.profiles — Gestión de perfiles multi-modelo de ONUs y resolución de firmwares.
Soporta arquitecturas modulares: VSOL V2801S-B, V2804AX30-H, Huawei, ZTE, etc.
Incluye creación, edición y validación de modelos desde la interfaz web/CLI.
"""
import copy
import json
import os
import sys

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CORE_DIR) if os.path.basename(CORE_DIR) == "core" else CORE_DIR
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
FIRMWARES_DIR = os.path.join(PROJECT_ROOT, "firmwares")
PROFILES_FILE = os.path.join(CONFIG_DIR, "onu_profiles.json")
LEGACY_PROFILES_FILE = os.path.join(PROJECT_ROOT, "onu_profiles.json")

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(FIRMWARES_DIR, exist_ok=True)

DEFAULT_PROFILES = {
    "active_model": "V2801S-B",
    "models": {
        "V2801S-B": {
            "id": "V2801S-B",
            "name": "VSOL V2801S-B / V2801D-B",
            "commercial_name": "VSOL 1GE G/EPON (Bridge / Router)",
            "description": "ONU 1 Puerto Gigabit Ethernet para conexión Bridge o Router",
            "hardware_type": "1GE G/EPON",
            "icon": "⚡",
            "badge_color": "#3b82f6",
            "firmware": "V2801D-B_all_V6.1.4-260914_powerlink_GPON.bin",
            "default_user": "admin",
            "default_pass": "stdONU101",
            "admin_user": "admin",
            "admin_pass": "stdONU101",
            "candidate_credentials": [
                ["admin", "Powerlink2026*"],
                ["Powerlink", "Powerlink2026*"],
                ["admin", "stdONUi0i"],
                ["admin", "stdONU101"],
                ["user", "Powerlink2026*"],
                ["user", "user"],
                ["admin", "admin"],
                ["admin", "CorpPowerLink**2026"],
                ["admin", "admin123"],
                ["admin", "Redes2010"],
                ["admin", "123456"],
                ["admin", "ClaveSecreta99*"]
            ],
            "new_user": "admin",
            "new_pass": "admin123",
            "final_user": "Powerlink",
            "final_pass": "Powerlink2026*",
            "has_wizard": False,
            "arch": "zte_cortina",
            "upgrade_page": "/getpage.gch?pid=1002&nextpage=manager_dev_version_t.gch",
            "config_page": "/getpage.gch?pid=1002&nextpage=manager_dev_conf_t.gch",
            "upload_endpoint": "/getpage.gch?pid=100",
            "target_wan_name": "1_TR069_INTERNET_R_VID_3",
            "target_vlan_id": "3",
            "box_default_qty": 20
        },
        "V2801D-B": {
            "id": "V2801D-B",
            "name": "VSOL V2801D-B ONU 1GE",
            "commercial_name": "VSOL 1GE G/EPON (Bridge / Router)",
            "description": "ONU 1 Puerto Gigabit Ethernet GPON/EPON",
            "hardware_type": "1GE G/EPON",
            "icon": "⚡",
            "badge_color": "#3b82f6",
            "firmware": "V2801D-B_all_V6.1.4-260914_powerlink_GPON.bin",
            "default_user": "admin",
            "default_pass": "stdONU101",
            "admin_user": "admin",
            "admin_pass": "stdONU101",
            "candidate_credentials": [
                ["admin", "Powerlink2026*"],
                ["Powerlink", "Powerlink2026*"],
                ["admin", "stdONUi0i"],
                ["admin", "stdONU101"],
                ["user", "Powerlink2026*"],
                ["user", "user"],
                ["admin", "admin"],
                ["admin", "CorpPowerLink**2026"],
                ["admin", "admin123"],
                ["admin", "Redes2010"],
                ["admin", "123456"]
            ],
            "new_user": "admin",
            "new_pass": "admin123",
            "final_user": "Powerlink",
            "final_pass": "Powerlink2026*",
            "has_wizard": False,
            "arch": "zte_cortina",
            "upgrade_page": "/getpage.gch?pid=1002&nextpage=manager_dev_version_t.gch",
            "config_page": "/getpage.gch?pid=1002&nextpage=manager_dev_conf_t.gch",
            "upload_endpoint": "/getpage.gch?pid=100",
            "target_wan_name": "1_TR069_INTERNET_R_VID_3",
            "target_vlan_id": "3",
            "box_default_qty": 20
        },
        "V2804AX30-H": {
            "id": "V2804AX30-H",
            "name": "VSOL V2804AX30-H / HG3232AXT-H",
            "commercial_name": "VSOL Wi-Fi 6 AX3000 (4GE + 1POTS)",
            "description": "Router ONU Wi-Fi 6 Doble Banda 3000Mbps con 4 puertos Gigabit y Telefonía",
            "hardware_type": "Wi-Fi 6 AX3000",
            "icon": "📡",
            "badge_color": "#8b5cf6",
            "firmware": "HG3232AXT-H_all_V1.1.00-20260610_LupoverPowerlinkver.bin",
            "default_user": "admin",
            "default_pass": "stdONU101",
            "admin_user": "admin",
            "admin_pass": "stdONU101",
            "candidate_credentials": [
                ["admin", "stdONU101"],
                ["admin", "admin123"],
                ["Powerlink", "Powerlink2026*"],
                ["user", "user"],
                ["admin", "admin"]
            ],
            "new_user": "admin",
            "new_pass": "admin123",
            "final_user": "Powerlink",
            "final_pass": "Powerlink2026*",
            "has_wizard": True,
            "upload_endpoint": "/boaform/web_form_upload_file.cgi",
            "target_wan_name": "1_TR069_INTERNET_R_VID_3",
            "target_vlan_id": "3",
            "box_default_qty": 20
        }
    }
}


def get_profiles_file_path():
    if os.path.exists(PROFILES_FILE):
        return PROFILES_FILE
    if os.path.exists(LEGACY_PROFILES_FILE):
        return LEGACY_PROFILES_FILE
    return PROFILES_FILE


def resolve_firmware_path(firmware_filename):
    """Busca el archivo de firmware en la carpeta firmwares/ o en el directorio raíz."""
    if not firmware_filename:
        return None
    path1 = os.path.join(FIRMWARES_DIR, firmware_filename)
    if os.path.exists(path1):
        return path1
    path2 = os.path.join(PROJECT_ROOT, firmware_filename)
    if os.path.exists(path2):
        return path2
    if os.path.isabs(firmware_filename) and os.path.exists(firmware_filename):
        return firmware_filename
    return path1


def get_available_firmwares():
    """Lista todos los archivos .bin de firmware disponibles en la carpeta firmwares/."""
    firmwares = []
    seen = set()
    for search_dir in [FIRMWARES_DIR, PROJECT_ROOT]:
        if os.path.exists(search_dir):
            try:
                for f in os.listdir(search_dir):
                    if f.lower().endswith(".bin") and f not in seen:
                        seen.add(f)
                        full = os.path.join(search_dir, f)
                        size_mb = round(os.path.getsize(full) / (1024 * 1024), 2)
                        firmwares.append({
                            "filename": f,
                            "size_mb": size_mb,
                            "path": full
                        })
            except Exception:
                pass
    return sorted(firmwares, key=lambda x: x["filename"])


def load_profiles():
    """Carga los perfiles de modelos desde el archivo JSON."""
    file_path = get_profiles_file_path()
    data = None
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None

    if not data or "models" not in data:
        data = copy.deepcopy(DEFAULT_PROFILES)
        save_profiles(data)

    models = data.get("models", {})
    for mid, def_prof in DEFAULT_PROFILES["models"].items():
        if mid not in models:
            models[mid] = copy.deepcopy(def_prof)
        else:
            for k, v in def_prof.items():
                if k not in models[mid]:
                    models[mid][k] = v

    data["models"] = models
    return data


def save_profiles(data):
    """Guarda los perfiles actualizados en config/onu_profiles.json y en la raíz."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    saved = False
    for target in [PROFILES_FILE, LEGACY_PROFILES_FILE]:
        try:
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            saved = True
        except Exception as ex:
            print(f"[Profiles] Error guardando en {target}: {ex}", file=sys.stderr)
    return saved


def get_active_model_id():
    data = load_profiles()
    return data.get("active_model", "V2801S-B")


get_active_model = get_active_model_id


def get_active_profile(override_model_id=None):
    """Obtiene el perfil enriquecido con ruta de firmware y tamaños."""
    data = load_profiles()
    model_id = override_model_id or data.get("active_model", "V2801S-B")
    models = data.get("models", {})
    prof = models.get(model_id)
    if not prof:
        prof = models.get("V2801S-B") or (list(models.values())[0] if models else {})

    prof_copy = copy.deepcopy(prof)
    fw_name = prof_copy.get("firmware", "")
    fw_path = resolve_firmware_path(fw_name)
    prof_copy["firmware_path"] = fw_path
    prof_copy["firmware_exists"] = os.path.exists(fw_path) if fw_path else False
    if prof_copy["firmware_exists"]:
        prof_copy["firmware_size_mb"] = round(os.path.getsize(fw_path) / (1024 * 1024), 2)
    else:
        prof_copy["firmware_size_mb"] = 0.0

    return prof_copy


def set_active_model(model_id):
    data = load_profiles()
    if model_id not in data.get("models", {}):
        return False, f"Modelo no reconocido: {model_id}"
    data["active_model"] = model_id
    if save_profiles(data):
        return True, f"Modelo activo cambiado a {model_id}"
    return False, "Error al guardar perfil activo"


def get_models_list():
    """Lista todos los modelos disponibles con metadatos completos y estado de firmware."""
    data = load_profiles()
    active_id = data.get("active_model", "V2801S-B")
    result = []
    for mid, m in data.get("models", {}).items():
        m_copy = copy.deepcopy(m)
        m_copy["is_active"] = (mid == active_id)
        fw_name = m_copy.get("firmware", "")
        fw_path = resolve_firmware_path(fw_name)
        m_copy["firmware_path"] = fw_path
        m_copy["firmware_exists"] = os.path.exists(fw_path) if fw_path else False
        if m_copy["firmware_exists"]:
            m_copy["firmware_size_mb"] = round(os.path.getsize(fw_path) / (1024 * 1024), 2)
        else:
            m_copy["firmware_size_mb"] = 0.0
        result.append(m_copy)
    return result


def create_or_update_model(model_data):
    """Crea o actualiza un modelo en la configuración."""
    if not isinstance(model_data, dict):
        return False, "Datos de modelo inválidos"

    model_id = str(model_data.get("id", "")).strip().upper()
    if not model_id:
        return False, "El ID del modelo es obligatorio (ej: V2801S-B)"

    data = load_profiles()
    models = data.setdefault("models", {})

    existing = models.get(model_id, {})
    name = model_data.get("name") or existing.get("name") or model_id
    comm_name = model_data.get("commercial_name") or existing.get("commercial_name") or name
    firmware = model_data.get("firmware") or existing.get("firmware", "")
    hw_type = model_data.get("hardware_type") or existing.get("hardware_type", "G/EPON")
    icon = model_data.get("icon") or existing.get("icon", "📡")
    badge_color = model_data.get("badge_color") or existing.get("badge_color", "#3b82f6")

    def_user = model_data.get("default_user") or existing.get("default_user", "admin")
    def_pass = model_data.get("default_pass") or existing.get("default_pass", "stdONU101")
    new_user = model_data.get("new_user") or existing.get("new_user", "admin")
    new_pass = model_data.get("new_pass") or existing.get("new_pass", "admin123")
    final_user = model_data.get("final_user") or existing.get("final_user", "Powerlink")
    final_pass = model_data.get("final_pass") or existing.get("final_pass", "Powerlink2026*")

    candidates = model_data.get("candidate_credentials") or existing.get("candidate_credentials") or [
        [def_user, def_pass],
        [new_user, new_pass],
        [final_user, final_pass],
        ["user", "user"],
        ["admin", "admin"]
    ]

    has_wizard = bool(model_data.get("has_wizard", existing.get("has_wizard", False)))
    target_vlan = str(model_data.get("target_vlan_id") or existing.get("target_vlan_id", "3"))
    target_wan = model_data.get("target_wan_name") or existing.get("target_wan_name", f"1_TR069_INTERNET_R_VID_{target_vlan}")
    upload_ep = model_data.get("upload_endpoint") or existing.get("upload_endpoint", "/boaform/web_form_upload_file.cgi")
    box_qty = int(model_data.get("box_default_qty") or existing.get("box_default_qty", 20))

    new_model_entry = {
        "id": model_id,
        "name": name,
        "commercial_name": comm_name,
        "description": model_data.get("description") or existing.get("description", f"Modelo {comm_name}"),
        "hardware_type": hw_type,
        "icon": icon,
        "badge_color": badge_color,
        "firmware": firmware,
        "default_user": def_user,
        "default_pass": def_pass,
        "admin_user": def_user,
        "admin_pass": def_pass,
        "candidate_credentials": candidates,
        "new_user": new_user,
        "new_pass": new_pass,
        "final_user": final_user,
        "final_pass": final_pass,
        "has_wizard": has_wizard,
        "upload_endpoint": upload_ep,
        "target_wan_name": target_wan,
        "target_vlan_id": target_vlan,
        "box_default_qty": box_qty
    }

    models[model_id] = new_model_entry
    data["models"] = models

    if save_profiles(data):
        return True, f"Modelo {model_id} guardado correctamente"
    return False, "Error al escribir config/onu_profiles.json"


def delete_model(model_id):
    """Elimina un modelo si no es el único restante."""
    data = load_profiles()
    models = data.get("models", {})
    if model_id not in models:
        return False, f"El modelo {model_id} no existe"

    if len(models) <= 1:
        return False, "No se puede eliminar el único modelo configurado"

    del models[model_id]
    if data.get("active_model") == model_id:
        data["active_model"] = list(models.keys())[0]

    data["models"] = models
    if save_profiles(data):
        return True, f"Modelo {model_id} eliminado"
    return False, "Error al guardar perfiles"
