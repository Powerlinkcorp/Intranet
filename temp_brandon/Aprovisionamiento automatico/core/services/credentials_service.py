# -*- coding: utf-8 -*-
"""
credentials_service.py — Servicio seguro de gestión de credenciales para ONUs.
"""
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config", "credentials.json")

DEFAULT_CREDENTIALS = {
    "active_credentials": {
        "username": "Powerlink",
        "password": "Powerlink2026*"
    },
    "candidate_credentials": [
        ["Powerlink", "Powerlink2026*"],
        ["admin", "stdONU101"],
        ["admin", "Redes2010"],
        ["admin", "admin123"],
        ["user", "user"],
        ["admin", "admin"]
    ]
}


class CredentialsService:
    @staticmethod
    def load() -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return DEFAULT_CREDENTIALS.copy()

    @staticmethod
    def save(data: dict) -> bool:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True

    @staticmethod
    def get_candidates(sn: str = None, mac: str = None) -> list:
        """
        Retorna la lista ordenada de credenciales a probar.
        Si se pasa sn o mac, consulta primero la Estación de Flasheo para colocar
        la clave exacta del lote en la primera posición.
        """
        data = CredentialsService.load()
        candidates = data.get("candidate_credentials", [])
        active = data.get("active_credentials")
        
        result = []

        # 1. Consultar base de datos / API de Estación de Flasheo si hay SN o MAC
        for q in [sn, mac]:
            if q and str(q).strip():
                try:
                    from .flasheo_integration_service import FlasheoIntegrationService
                    flasheo_match = FlasheoIntegrationService.lookup(str(q).strip())
                    if flasheo_match and flasheo_match.get("encontrado"):
                        creds = flasheo_match.get("credenciales", {})
                        u = creds.get("usuario")
                        p = creds.get("clave")
                        if u and p:
                            pair = (u, p)
                            if pair not in result:
                                result.append(pair)
                            break
                except Exception:
                    pass

        # 2. Credencial activa configurada localmente
        if active and "username" in active and "password" in active:
            pair = (active["username"], active["password"])
            if pair not in result:
                result.append(pair)
        
        # 3. Candidatos estándar de respaldo
        for item in candidates:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                pair = (item[0], item[1])
                if pair not in result:
                    result.append(pair)
        return result
