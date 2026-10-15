# -*- coding: utf-8 -*-
"""
smartolt_service.py — Servicio de integración con la API REST de SmartOLT.
Permite consultar ONUs no configuradas, autorizar equipos específicos en VLAN 3 con perfil DBA,
y migrar la VLAN en SmartOLT hacia la VLAN del Hub tras la verificación previa.
"""
import json
import os
import urllib.request
import urllib.parse
import urllib.error
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_FILE = os.path.join(PROJECT_ROOT, "config", "settings.json")


class SmartOLTService:
    @staticmethod
    def _get_config():
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("smartolt", {})
            except Exception:
                pass
        return {}

    @staticmethod
    def _get_api_key():
        cfg = SmartOLTService._get_config()
        return cfg.get("api_key", "6e78554e1d2153b39507fecb3797f895")

    @staticmethod
    def _get_base_url():
        cfg = SmartOLTService._get_config()
        return cfg.get("base_url", "https://powerlinkcorp.telecomti.net/api").rstrip("/")

    @staticmethod
    def is_configured() -> bool:
        return bool(SmartOLTService._get_api_key())

    @staticmethod
    def _api_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
        api_key = SmartOLTService._get_api_key()
        base_url = SmartOLTService._get_base_url()

        if not api_key:
            return {"status": False, "error": "SmartOLT API Key no configurada."}

        url = f"{base_url}/{endpoint.lstrip('/')}"
        headers = {
            "X-Token": api_key,
            "Accept": "application/json"
        }

        body_bytes = None
        if method in ("POST", "PUT", "PATCH") and data is not None:
            body_bytes = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=18) as resp:
                resp_text = resp.read().decode("utf-8", errors="replace")
                try:
                    return json.loads(resp_text)
                except Exception:
                    return {"status": True, "raw_response": resp_text}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                return {
                    "status": False,
                    "error": err_json.get("error") or err_json.get("message") or f"HTTP {e.code}",
                    "response_code": err_json.get("response_code"),
                    "http_code": e.code
                }
            except Exception:
                return {"status": False, "error": f"Error HTTP {e.code}: {err_body[:100]}"}
        except Exception as ex:
            return {"status": False, "error": f"Error de conexión con SmartOLT: {str(ex)}"}

    @staticmethod
    def get_unconfigured_onus(olt_id: str = None, filter_vsol: bool = True) -> dict:
        """Obtiene la lista de ONUs no configuradas pendientes de autorización, filtrando por defecto solo equipos VSOL."""
        endpoint = "onu/unconfigured_onus"
        params = {}
        if olt_id:
            params["olt_id"] = olt_id
        res = SmartOLTService._api_request(endpoint, method="GET", data=params if params else None)
        if not res.get("status"):
            return res

        raw_onus = res.get("onus") or res.get("response") or []
        if filter_vsol:
            vsol_onus = []
            for o in raw_onus:
                sn = str(o.get("sn") or "").strip().upper()
                m_type = str(o.get("onu_type_name") or "").strip().lower()
                vendor = str(o.get("vendor") or "").strip().lower()
                model = str(o.get("model") or "").strip().lower()
                if sn.startswith("VSOL") or "vsol" in m_type or "vsol" in vendor or "vsol" in model:
                    vsol_onus.append(o)
            return {"status": True, "onus": vsol_onus, "total_raw": len(raw_onus)}
        return res

    @staticmethod
    def find_unconfigured_vsol(sn: str, expected_models=("VSOLVD64", "VSOLD64", "V2804AX30-H", "V2804AX30", "HG3232AXT-H", "VSOL")) -> dict:
        """
        Busca una ONU por PON/SN y valida que esté no configurada y sea del modelo esperado.
        Retorna: {"valid": True/False, "onu": {...}, "error": "..."}
        """
        sn_clean = sn.strip().upper()
        res = SmartOLTService.get_unconfigured_onus()
        if not res.get("status"):
            return {"valid": False, "error": res.get("error", "Error consultando SmartOLT")}

        onus = res.get("response") or res.get("onus") or []
        target_onu = None
        for o in onus:
            o_sn = str(o.get("sn", "")).strip().upper()
            if o_sn == sn_clean:
                target_onu = o
                break

        if not target_onu:
            return {
                "valid": False,
                "error": f"La ONU con SN/PON '{sn_clean}' no fue encontrada en la lista de equipos no configurados de SmartOLT."
            }

        detected_model = str(target_onu.get("onu_type_name") or target_onu.get("onu_type", "")).strip()
        is_model_match = any(m.upper() in detected_model.upper() or detected_model.upper() in m.upper() for m in expected_models)

        if not is_model_match and detected_model:
            return {
                "valid": False,
                "error": f"El modelo detectado '{detected_model}' no coincide con los modelos VSOL autorizados ({', '.join(expected_models)}).",
                "onu": target_onu
            }

        return {
            "valid": True,
            "onu": target_onu,
            "model": detected_model
        }

    @staticmethod
    def _clean_zone_string(val: str) -> str:
        """
        Sanitiza cadenas enviadas a SmartOLT (especialmente zonas, nombres y direcciones).
        Solo permite caracteres alfanuméricos, espacios, guión bajo (_), punto (.) y guión (-).
        """
        if not val:
            return ""
        import unicodedata
        # Normalizar acentos y unicode a ASCII
        normalized = unicodedata.normalize('NFKD', str(val)).encode('ASCII', 'ignore').decode('utf-8')
        # Reemplazar caracteres prohibidos por espacios
        clean = re.sub(r'[^a-zA-Z0-9 _.-]', ' ', normalized)
        # Limpiar espacios múltiples sobrantes
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    @staticmethod
    def authorize_vsol_vlan3(sn: str, dba_profile: str, zone: str = None, odb: str = None, name: str = None, address: str = None) -> dict:
        """
        Fase 1: Autoriza una ONU en SmartOLT asignándole exclusivamente la VLAN 3 y el perfil de velocidad / DBA indicado.
        Sanitiza la Zona y parámetros obligatorios para evitar rechazos por caracteres especiales.
        """
        check = SmartOLTService.find_unconfigured_vsol(sn)
        if not check.get("valid"):
            return {"status": False, "error": check.get("error")}

        onu = check["onu"]
        olt_id = onu.get("olt_id")
        pon_type = onu.get("pon_type", "gpon")
        board = onu.get("board")
        port = onu.get("port")
        # En SmartOLT el tipo registrado en el sistema es VSOLD64
        onu_type = "VSOLD64"
        
        raw_zone = zone or onu.get("pon_description") or onu.get("zone") or "Zona-1"
        clean_zone = SmartOLTService._clean_zone_string(raw_zone) or "Zona-1"
        clean_name = SmartOLTService._clean_zone_string(name or f"VSOL-{sn[-4:]}") or f"VSOL-{sn[-4:]}"
        clean_address = SmartOLTService._clean_zone_string(address or raw_zone or "Aprovisionamiento Automatico") or "Aprovisionamiento Automatico"

        payload = {
            "olt_id": olt_id,
            "pon_type": pon_type,
            "board": board,
            "port": port,
            "sn": sn.strip().upper(),
            "vlan": "3",  # Forzado a VLAN 3 inicial
            "onu_type": onu_type,
            "onu_mode": "Routing",  # Modo Router
            "name": clean_name,
            "address": clean_address,
            "zone": clean_zone
        }

        if dba_profile:
            payload["upload_speed_profile_name"] = dba_profile
            payload["download_speed_profile_name"] = dba_profile

        res = SmartOLTService._api_request("onu/authorize_onu", method="POST", data=payload)
        
        # Resiliencia: Si SmartOLT rechaza el parámetro de Zona, se realizan reintentos automáticos
        if not res.get("status"):
            err_msg = str(res.get("error") or "").lower()
            if "zone" in err_msg or "invalid parameters" in err_msg:
                # Reintento 1: Probar con la zona por defecto 'Zona-1'
                payload["zone"] = "Zona-1"
                res_retry = SmartOLTService._api_request("onu/authorize_onu", method="POST", data=payload)
                if res_retry.get("status"):
                    return res_retry
                
                # Reintento 2: Si persiste, remover la clave 'zone' del payload
                payload.pop("zone", None)
                res_retry2 = SmartOLTService._api_request("onu/authorize_onu", method="POST", data=payload)
                if res_retry2.get("status"):
                    return res_retry2

        return res

    @staticmethod
    def get_onu_details(sn: str) -> dict:
        """Obtiene detalles de una ONU configurada en SmartOLT para verificar su VLAN y telemetría actual."""
        sn_clean = sn.strip().upper()
        res = SmartOLTService._api_request(f"onu/get_onu_details/{sn_clean}", method="GET")
        if res.get("status") and res.get("onu_details"):
            onu_info = res["onu_details"]
            return {
                "status": True,
                "onu": onu_info,
                "onus": [onu_info],
                "response": [onu_info],
                "response_code": "success"
            }
        return res

    @staticmethod
    def update_onu_vlan(sn: str, target_vlan: str) -> dict:
        """
        Fase 3: Migra la ONU de la VLAN 3 hacia la VLAN destino del Hub,
        comprobando previamente la condición estricta de que la ONU estaba autorizada en VLAN 3.
        """
        sn_clean = sn.strip().upper()
        details_resp = SmartOLTService.get_onu_details(sn_clean)
        
        if not details_resp.get("status"):
            return {
                "status": False,
                "error": f"No se pudo consultar el estado actual de la ONU en SmartOLT: {details_resp.get('error')}"
            }

        onus = details_resp.get("onus") or details_resp.get("response") or []
        if not onus:
            return {"status": False, "error": f"ONU con SN '{sn_clean}' no encontrada en SmartOLT"}

        current_onu = onus[0]
        current_vlan = str(current_onu.get("vlan", "")).strip()
        unique_ext_id = current_onu.get("unique_external_id") or sn_clean
        target_vlan_str = str(target_vlan).strip()

        # Condición estricta: Debe haber estado en VLAN 3
        if current_vlan and current_vlan != "3":
            # Si ya se encuentra en la VLAN destino, considerarlo completado
            if current_vlan == target_vlan_str:
                return {
                    "status": True,
                    "response_code": "success",
                    "message": f"La ONU ya se encuentra configurada en la VLAN destino {target_vlan_str}."
                }
            return {
                "status": False,
                "error": f"Condición no cumplida: La ONU se encuentra actualmente en VLAN {current_vlan}, pero se requiere que estuviese previamente en VLAN 3 para migrar."
            }

        # 1. Actualizar la VLAN principal (Routing WAN VLAN en SmartOLT)
        res_main = SmartOLTService._api_request(
            f"onu/update_main_vlan/{unique_ext_id}",
            method="POST",
            data={"vlan": target_vlan_str}
        )

        if not res_main.get("status"):
            err_msg = res_main.get("error") or res_main.get("response") or "Error al actualizar la VLAN principal en SmartOLT"
            return {"status": False, "error": f"SmartOLT update_main_vlan falló: {err_msg}"}

        # 2. Actualizar también el service port para asegurar sincronización de perfiles de velocidad
        service_ports = current_onu.get("service_ports") or [{}]
        s_port = service_ports[0].get("service_port", "1")
        up_speed = service_ports[0].get("upload_speed", "100M")
        down_speed = service_ports[0].get("download_speed", "100M")

        payload_sp = {
            "service_port": str(s_port),
            "vlan": target_vlan_str,
            "upload_speed_profile_name": up_speed,
            "download_speed_profile_name": down_speed
        }
        SmartOLTService._api_request(f"onu/update_service_port/{unique_ext_id}", method="POST", data=payload_sp)

        # 3. Validación de comprobación real: consultar SmartOLT para certificar el cambio efectivo
        verify_resp = SmartOLTService.get_onu_details(sn_clean)
        verify_onus = verify_resp.get("onus") or verify_resp.get("response") or []
        if verify_onus:
            verified_vlan = str(verify_onus[0].get("vlan", "")).strip()
            if verified_vlan != target_vlan_str:
                return {
                    "status": False,
                    "error": f"SmartOLT procesó la solicitud pero la VLAN reportada sigue siendo '{verified_vlan}' en vez de '{target_vlan_str}'."
                }

        return {
            "status": True,
            "response_code": "success",
            "message": f"VLAN actualizada y verificada exitosamente a {target_vlan_str} en SmartOLT.",
            "response": res_main.get("response")
        }

    @staticmethod
    def get_speed_profiles() -> list:
        res = SmartOLTService._api_request("system/get_speed_profiles", method="GET")
        if res.get("status"):
            return res.get("response") or res.get("speed_profiles") or []
        return []

    @staticmethod
    def get_dba_profiles() -> list:
        res = SmartOLTService._api_request("system/get_dba_profiles", method="GET")
        if res.get("status"):
            return res.get("response") or res.get("dba_profiles") or []
        return SmartOLTService.get_speed_profiles()

    _vlans_cache = None
    _vlans_cache_time = 0

    @staticmethod
    def get_vlans(olt_id: str = None, force_refresh: bool = False) -> list:
        """
        Obtiene el catálogo de VLANs desde SmartOLT vía endpoint onu/get_vlans.
        Opcionalmente filtra por olt_id y cuenta con caché en memoria de 5 minutos.
        """
        import time
        if not SmartOLTService.is_configured():
            return []

        now = time.time()
        if force_refresh or SmartOLTService._vlans_cache is None or (now - SmartOLTService._vlans_cache_time) > 300:
            res = SmartOLTService._api_request("onu/get_vlans", method="GET")
            if res.get("status"):
                SmartOLTService._vlans_cache = res.get("response") or res.get("vlans") or []
                SmartOLTService._vlans_cache_time = now
            else:
                if SmartOLTService._vlans_cache is None:
                    SmartOLTService._vlans_cache = []

        raw_vlans = SmartOLTService._vlans_cache or []
        if olt_id:
            raw_vlans = [v for v in raw_vlans if str(v.get("olt_id")) == str(olt_id)]
        return raw_vlans

    @staticmethod
    def delete_onu(sn: str) -> dict:
        """
        Paso 3 (Liberación): Borra la ONU configurada en SmartOLT para que retorne al estado
        de desconfigurada/no autorizada en el puerto PON correspondiente.
        Esto permite que el equipo de soporte técnico la aprovisione definitivamente mediante el sistema Rubpi.
        """
        if not SmartOLTService.is_configured():
            return {"status": False, "error": "SmartOLT API no está configurada o habilitada."}

        sn_clean = str(sn).strip().upper()
        # Llamar al endpoint oficial POST /api/onu/delete/{onu_external_id}
        res = SmartOLTService._api_request(f"onu/delete/{sn_clean}", method="POST")

        if res.get("status"):
            return {
                "status": True,
                "response_code": "success",
                "message": f"ONU {sn_clean} eliminada exitosamente de configuradas en SmartOLT. Ahora aparecerá como no configurada y disponible para aprovisionamiento por Rubpi.",
                "response": res.get("response")
            }
        else:
            err_str = str(res.get("error") or res.get("response") or "")
            if "not found" in err_str.lower() or "no encontrada" in err_str.lower():
                return {
                    "status": True,
                    "response_code": "already_deleted",
                    "message": f"La ONU con SN '{sn_clean}' ya no se encuentra configurada en SmartOLT (lista para Rubpi)."
                }
            return {
                "status": False,
                "error": f"Fallo al liberar ONU en SmartOLT: {err_str}"
            }

    @staticmethod
    def get_onu_learned_mac_vlan3(sn: str) -> dict:
        """
        Consulta el estado completo de la ONU en SmartOLT y extrae la dirección MAC
        aprendida en la OLT para la VLAN 3 (usada para ubicar la IP asignada en el DHCP de MikroTik),
        así como la IP de gestión WAN reportada y la discriminación de capacidades (ej. sin Wi-Fi).
        """
        sn_clean = str(sn).strip().upper()
        res = SmartOLTService._api_request(f"onu/get_onu_full_status_info/{sn_clean}", method="GET")
        if not res.get("status", True) and res.get("error"):
            return {"status": False, "error": res.get("error")}

        full_info = res.get("full_status_info") or ""
        full_json = res.get("full_status_json") or {}
        if not full_info and not full_json:
            return {"status": False, "error": "No se obtuvo información de estado completo de la ONU"}

        pattern = re.compile(r'([0-9a-fA-F]{2}(?:[:\-][0-9a-fA-F]{2}){5})\s+(\d+)', re.IGNORECASE)
        matches = pattern.findall(full_info)
        mac_vlan3 = None
        all_macs = []
        for mac_str, vlan_str in matches:
            norm_mac = mac_str.lower().replace("-", ":")
            all_macs.append({"mac": norm_mac, "vlan": vlan_str})
            if vlan_str == "3" and not mac_vlan3:
                mac_vlan3 = norm_mac

        # Extraer IP de gestión WAN si la OLT ya la reporta
        wan_ip = None
        if isinstance(full_json, dict):
            wan_iface = full_json.get("ONU WAN Interfaces", {})
            if isinstance(wan_iface, dict):
                cand_ip = str(wan_iface.get("IPv4 address", "")).strip()
                if cand_ip and cand_ip not in ("0.0.0.0", "N/A"):
                    wan_ip = cand_ip

        if not wan_ip and full_info:
            m_ip = re.search(r'IPv4 address:\s*([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})', full_info)
            if m_ip and m_ip.group(1) not in ("0.0.0.0", "N/A"):
                wan_ip = m_ip.group(1)

        # Detectar modelo y si posee Wi-Fi
        model = ""
        has_wifi = True
        if isinstance(full_json, dict):
            onu_d = full_json.get("ONU details", {})
            if isinstance(onu_d, dict):
                model = onu_d.get("Detected ONU type") or onu_d.get("Type") or ""

        # Modelos monopuerto / Ethernet conocidos sin interfaz Wi-Fi
        if any(x in str(model).upper() for x in ["V2801", "VSOLD64", "VSOLD501", "1GE", "SFU"]):
            has_wifi = False
        else:
            try:
                details = SmartOLTService.get_onu_details(sn_clean)
                onu_info = (details.get("onus") or [{}])[0]
                wifi_ports = onu_info.get("wifi_ports")
                if wifi_ports is not None and len(wifi_ports) == 0:
                    has_wifi = False
                det_model = onu_info.get("onu_type_name") or onu_info.get("model") or ""
                if det_model:
                    model = det_model
                    if any(x in str(det_model).upper() for x in ["V2801", "VSOLD64", "VSOLD501", "1GE", "SFU"]):
                        has_wifi = False
            except Exception:
                pass

        target_mac = mac_vlan3 or (all_macs[0]["mac"] if all_macs else None)
        if target_mac:
            return {
                "status": True,
                "mac": target_mac,
                "vlan": "3",
                "all_macs": all_macs,
                "ip": wan_ip,
                "has_wifi": has_wifi,
                "model": model or "VSOL"
            }
        else:
            return {
                "status": False,
                "error": "La OLT aún no ha reportado ninguna dirección MAC aprendida para esta ONU",
                "ip": wan_ip,
                "has_wifi": has_wifi,
                "model": model or "VSOL"
            }

