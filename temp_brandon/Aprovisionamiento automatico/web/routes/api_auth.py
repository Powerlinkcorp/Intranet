# -*- coding: utf-8 -*-
"""
api_auth.py — Rutas de la API para autenticación, gestión de usuarios y filtro de IPs.
"""
from core.services.auth_service import AuthService


def handle_login(req_data: dict) -> tuple:
    username = req_data.get("username", "")
    password = req_data.get("password", "")
    res = AuthService.authenticate(username, password)
    if res.get("success"):
        return (res, 200)
    return (res, 401)


def handle_get_session(auth_user: dict) -> tuple:
    if not auth_user:
        return ({"success": False, "error": "No hay sesión activa"}, 401)
    return ({
        "success": True,
        "username": auth_user.get("username"),
        "role": auth_user.get("role")
    }, 200)


def handle_logout(token: str) -> tuple:
    AuthService.logout(token)
    return ({"success": True, "message": "Sesión finalizada exitosamente"}, 200)


def handle_list_users(auth_user: dict) -> tuple:
    if not auth_user or auth_user.get("role") != "admin":
        return ({"success": False, "error": "Permiso denegado: solo administradores"}, 403)
    users = AuthService.list_users()
    return ({"success": True, "users": users}, 200)


def handle_create_user(req_data: dict, auth_user: dict) -> tuple:
    if not auth_user or auth_user.get("role") != "admin":
        return ({"success": False, "error": "Permiso denegado: solo administradores"}, 403)

    username = req_data.get("username", "")
    password = req_data.get("password", "")
    role = req_data.get("role", "lectura")

    res = AuthService.create_user(username, password, role)
    status_code = 200 if res.get("success") else 400
    return (res, status_code)


def handle_delete_user(username: str, auth_user: dict) -> tuple:
    if not auth_user or auth_user.get("role") != "admin":
        return ({"success": False, "error": "Permiso denegado: solo administradores"}, 403)

    requester = auth_user.get("username", "")
    res = AuthService.delete_user(username, requester)
    status_code = 200 if res.get("success") else 400
    return (res, status_code)


def handle_get_ips(auth_user: dict) -> tuple:
    if not auth_user or auth_user.get("role") != "admin":
        return ({"success": False, "error": "Permiso denegado: solo administradores"}, 403)
    whitelist = AuthService.get_ip_whitelist()
    return ({"success": True, "ip_whitelist": whitelist}, 200)


def handle_save_ips(req_data: dict, auth_user: dict) -> tuple:
    if not auth_user or auth_user.get("role") != "admin":
        return ({"success": False, "error": "Permiso denegado: solo administradores"}, 403)

    ip_list = req_data.get("ip_whitelist") or []
    res = AuthService.set_ip_whitelist(ip_list)
    status_code = 200 if res.get("success") else 400
    return (res, status_code)
