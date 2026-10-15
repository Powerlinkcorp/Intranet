# -*- coding: utf-8 -*-
"""
auth_service.py — Servicio de autenticación, control de roles y filtrado de IPs.
Gestiona usuarios persistidos en config/users.json y tokens de sesión en memoria.
"""
import hashlib
import ipaddress
import json
import os
import secrets
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
USERS_FILE = os.path.join(CONFIG_DIR, "users.json")

AUTH_LOCK = threading.Lock()

# Duración de las sesiones: 24 horas en segundos
SESSION_DURATION_SECONDS = 24 * 3600

# Sesiones en memoria: token -> { "username": str, "role": str, "expires_at": float }
ACTIVE_SESSIONS: Dict[str, dict] = {}


def _hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return hashed, salt


class AuthService:
    @staticmethod
    def _load_data() -> dict:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if not os.path.exists(USERS_FILE):
            # Crear configuración inicial con admin / Redes2010
            admin_hash, admin_salt = _hash_password("Redes2010")
            initial_data = {
                "users": {
                    "admin": {
                        "password_hash": admin_hash,
                        "salt": admin_salt,
                        "role": "admin",
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                },
                "ip_whitelist": []  # Vacío = permitir todas las conexiones
            }
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2, ensure_ascii=False)
            return initial_data

        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("users", {})
                data.setdefault("ip_whitelist", [])
                if "admin" not in data["users"]:
                    admin_hash, admin_salt = _hash_password("Redes2010")
                    data["users"]["admin"] = {
                        "password_hash": admin_hash,
                        "salt": admin_salt,
                        "role": "admin",
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    AuthService._save_data(data)
                return data
        except Exception:
            return {"users": {}, "ip_whitelist": []}

    @staticmethod
    def _save_data(data: dict) -> None:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def authenticate(username: str, password: str) -> dict:
        """
        Valida credenciales de usuario. Retorna un token de sesión si es válido.
        """
        username_clean = (username or "").strip().lower()
        password_clean = (password or "").strip()

        with AUTH_LOCK:
            data = AuthService._load_data()
            users = data.get("users", {})
            user = users.get(username_clean)

            if not user:
                return {"success": False, "error": "Usuario o contraseña incorrectos"}

            stored_hash = user.get("password_hash")
            salt = user.get("salt")
            computed_hash, _ = _hash_password(password_clean, salt)

            if computed_hash != stored_hash:
                return {"success": False, "error": "Usuario o contraseña incorrectos"}

            token = secrets.token_hex(32)
            now = time.time()
            role = user.get("role", "lectura")
            ACTIVE_SESSIONS[token] = {
                "username": username_clean,
                "role": role,
                "expires_at": now + SESSION_DURATION_SECONDS
            }

            return {
                "success": True,
                "token": token,
                "username": username_clean,
                "role": role,
                "expires_at": now + SESSION_DURATION_SECONDS
            }

    @staticmethod
    def validate_session(token: str) -> Optional[dict]:
        """
        Verifica si un token de sesión es válido y no ha expirado.
        """
        if not token:
            return None

        token_clean = token.replace("Bearer ", "").strip()
        with AUTH_LOCK:
            session = ACTIVE_SESSIONS.get(token_clean)
            if not session:
                return None

            if time.time() > session.get("expires_at", 0):
                del ACTIVE_SESSIONS[token_clean]
                return None

            return session

    @staticmethod
    def logout(token: str) -> bool:
        if not token:
            return True
        token_clean = token.replace("Bearer ", "").strip()
        with AUTH_LOCK:
            if token_clean in ACTIVE_SESSIONS:
                del ACTIVE_SESSIONS[token_clean]
        return True

    @staticmethod
    def list_users() -> List[dict]:
        with AUTH_LOCK:
            data = AuthService._load_data()
            users = data.get("users", {})
            result = []
            for username, uinfo in users.items():
                result.append({
                    "username": username,
                    "role": uinfo.get("role", "lectura"),
                    "created_at": uinfo.get("created_at", "")
                })
            return sorted(result, key=lambda x: x["username"])

    @staticmethod
    def create_user(username: str, password: str, role: str) -> dict:
        username_clean = (username or "").strip().lower()
        password_clean = (password or "").strip()
        role_clean = (role or "").strip().lower()

        if not username_clean or len(username_clean) < 3:
            return {"success": False, "error": "El nombre de usuario debe tener al menos 3 caracteres"}
        if not password_clean or len(password_clean) < 4:
            return {"success": False, "error": "La contraseña debe tener al menos 4 caracteres"}
        if role_clean not in ["admin", "aprovisionador", "lectura"]:
            return {"success": False, "error": "Rol inválido. Opciones: admin, aprovisionador, lectura"}

        with AUTH_LOCK:
            data = AuthService._load_data()
            users = data.get("users", {})
            if username_clean in users:
                return {"success": False, "error": f"El usuario '{username_clean}' ya existe"}

            hashed, salt = _hash_password(password_clean)
            users[username_clean] = {
                "password_hash": hashed,
                "salt": salt,
                "role": role_clean,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            AuthService._save_data(data)

        return {"success": True, "message": f"Usuario '{username_clean}' creado exitosamente con rol '{role_clean}'"}

    @staticmethod
    def delete_user(username: str, requester_username: str) -> dict:
        username_clean = (username or "").strip().lower()
        if username_clean == "admin":
            return {"success": False, "error": "No se puede eliminar el usuario administrador principal 'admin'"}
        if username_clean == requester_username.lower():
            return {"success": False, "error": "No puedes eliminar tu propio usuario mientras tienes sesión activa"}

        with AUTH_LOCK:
            data = AuthService._load_data()
            users = data.get("users", {})
            if username_clean not in users:
                return {"success": False, "error": f"El usuario '{username_clean}' no existe"}

            del users[username_clean]
            AuthService._save_data(data)

            for token, s in list(ACTIVE_SESSIONS.items()):
                if s.get("username") == username_clean:
                    del ACTIVE_SESSIONS[token]

        return {"success": True, "message": f"Usuario '{username_clean}' eliminado correctamente"}

    # ================= IP WHITELIST / FILTRADO =================
    @staticmethod
    def get_ip_whitelist() -> List[str]:
        with AUTH_LOCK:
            data = AuthService._load_data()
            return data.get("ip_whitelist", [])

    @staticmethod
    def set_ip_whitelist(ip_list: List[str]) -> dict:
        validated_ips = []
        for raw_entry in ip_list:
            entry = str(raw_entry).strip()
            if not entry:
                continue
            try:
                ipaddress.ip_network(entry, strict=False)
                validated_ips.append(entry)
            except ValueError:
                return {"success": False, "error": f"Formato de IP o rango CIDR inválido: '{entry}'"}

        with AUTH_LOCK:
            data = AuthService._load_data()
            data["ip_whitelist"] = validated_ips
            AuthService._save_data(data)

        return {"success": True, "message": "Lista de IPs permitidas actualizada correctamente", "whitelist": validated_ips}

    @staticmethod
    def is_ip_allowed(client_ip: str) -> bool:
        if not client_ip:
            return True

        if client_ip in ["127.0.0.1", "::1", "localhost"]:
            return True

        whitelist = AuthService.get_ip_whitelist()
        if not whitelist:
            return True

        try:
            ip_obj = ipaddress.ip_address(client_ip)
            for rule in whitelist:
                net = ipaddress.ip_network(rule, strict=False)
                if ip_obj in net:
                    return True
            return False
        except Exception:
            return False
