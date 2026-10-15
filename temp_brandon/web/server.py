# -*- coding: utf-8 -*-
"""
server.py — Servidor HTTP nativo con enrutamiento REST, autenticación por roles,
filtrado de IPs y despacho de archivos estáticos.
"""
import cgi
import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import urllib.parse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.services.auth_service import AuthService

try:
    from web.routes import (
        handle_probe,
        handle_provision,
        handle_provision_onu_only,
        handle_progress,
        handle_history,
        handle_export_excel,
        handle_get_config,
        handle_save_config,
        handle_get_credentials,
        handle_save_credentials,
        handle_system_status,
        handle_get_vlans_catalog,
        handle_flasheo_traceability,
        handle_get_unconfigured,
        handle_get_onu_status,
        handle_get_onu_mac,
        handle_smartolt_authorize,
        handle_smartolt_migrate_vlan,
        handle_smartolt_release_onu,
        handle_get_smartolt_profiles,
        handle_save_smartolt_config,
        handle_login,
        handle_get_session,
        handle_logout,
        handle_list_users,
        handle_create_user,
        handle_delete_user,
        handle_get_ips,
        handle_save_ips
    )
except ImportError:
    from routes import (
        handle_probe,
        handle_provision,
        handle_provision_onu_only,
        handle_progress,
        handle_history,
        handle_export_excel,
        handle_get_config,
        handle_save_config,
        handle_get_credentials,
        handle_save_credentials,
        handle_system_status,
        handle_get_vlans_catalog,
        handle_flasheo_traceability,
        handle_get_unconfigured,
        handle_get_onu_status,
        handle_get_onu_mac,
        handle_smartolt_authorize,
        handle_smartolt_migrate_vlan,
        handle_smartolt_release_onu,
        handle_get_smartolt_profiles,
        handle_save_smartolt_config,
        handle_login,
        handle_get_session,
        handle_logout,
        handle_list_users,
        handle_create_user,
        handle_delete_user,
        handle_get_ips,
        handle_save_ips
    )

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class AppRequestHandler(BaseHTTPRequestHandler):
    server_version = "PowerlinkProvisionServer/2.5"
    timeout = 60

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}
        return {}

    def _check_ip_allowed(self) -> bool:
        client_ip = self.client_address[0]
        return AuthService.is_ip_allowed(client_ip)

    def _get_auth_user(self):
        auth_header = self.headers.get("Authorization") or self.headers.get("X-Auth-Token") or ""
        if not auth_header:
            return None
        return AuthService.validate_session(auth_header)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
        self.end_headers()

    def do_GET(self):
        # 1. Validar Filtro de IP
        if not self._check_ip_allowed():
            return self._send_json({
                "success": False,
                "error": f"Acceso denegado: Su dirección IP ({self.client_address[0]}) no está en la lista blanca."
            }, 403)

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Rutas públicas / de sesión
        if path == "/api/auth/session":
            user = self._get_auth_user()
            res, code = handle_get_session(user)
            return self._send_json(res, code)

        # Si es una ruta de API (excepto sesión), requiere autenticación
        if path.startswith("/api/"):
            user = self._get_auth_user()
            if not user:
                return self._send_json({
                    "success": False,
                    "error": "Sesión no válida o expirada. Por favor inicie sesión.",
                    "auth_required": True
                }, 401)

            # Rutas de administración
            if path == "/api/auth/users":
                res, code = handle_list_users(user)
                return self._send_json(res, code)

            if path == "/api/auth/ips":
                res, code = handle_get_ips(user)
                return self._send_json(res, code)

            # Rutas de consulta / telemetría accesibles para todos los roles autenticados
            if path == "/api/status":
                res, code = handle_system_status()
                return self._send_json(res, code)

            if path == "/api/progress":
                job_id = query.get("job_id", [""])[0]
                res, code = handle_progress(job_id)
                return self._send_json(res, code)

            if path == "/api/history":
                limit = int(query.get("limit", [50])[0])
                res, code = handle_history(limit)
                return self._send_json(res, code)

            if path == "/api/export_excel":
                file_path, mime, filename, code = handle_export_excel()
                if code == 200 and os.path.exists(file_path):
                    try:
                        with open(file_path, "rb") as f:
                            content = f.read()
                        self.send_response(200)
                        self.send_header("Content-Type", mime)
                        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                        self.send_header("Content-Length", str(len(content)))
                        self.end_headers()
                        self.wfile.write(content)
                        return
                    except Exception as e:
                        return self._send_json({"error": str(e)}, 500)
                return self._send_json({"error": "Archivo no encontrado"}, 404)

            if path == "/api/config":
                res, code = handle_get_config()
                return self._send_json(res, code)

            if path == "/api/credentials":
                res, code = handle_get_credentials()
                return self._send_json(res, code)

            if path == "/api/smartolt/unconfigured":
                res, code = handle_get_unconfigured()
                return self._send_json(res, code)

            if path == "/api/smartolt/status":
                sn = query.get("sn", [""])[0]
                try:
                    res, code = handle_get_onu_status(sn)
                    return self._send_json(res, code)
                except Exception as exc:
                    return self._send_json({"success": False, "error": f"Error interno: {str(exc)}"}, 500)

            if path == "/api/smartolt/mac_vlan3":
                sn = query.get("sn", [""])[0]
                try:
                    res, code = handle_get_onu_mac(sn)
                    return self._send_json(res, code)
                except Exception as exc:
                    return self._send_json({"success": False, "error": f"Error interno: {str(exc)}"}, 500)

            if path == "/api/smartolt/profiles":
                res, code = handle_get_smartolt_profiles()
                return self._send_json(res, code)

            if path == "/api/vlans/catalog":
                olt_id = query.get("olt_id", [""])[0] or None
                res, code = handle_get_vlans_catalog(olt_id=olt_id)
                return self._send_json(res, code)

            if path == "/api/flasheo/onu_traceability":
                q = query.get("query", [""])[0] or query.get("sn", [""])[0] or query.get("mac", [""])[0]
                res, code = handle_flasheo_traceability(q)
                return self._send_json(res, code)

            return self._send_json({"error": "Ruta API no encontrada"}, 404)

        # Servir Archivos Estáticos (HTML, CSS, JS)
        req_path = path.lstrip("/")
        if not req_path or req_path == "index.html":
            file_path = os.path.join(STATIC_DIR, "index.html")
        elif req_path in ("login", "login.html"):
            file_path = os.path.join(STATIC_DIR, "login.html")
        else:
            file_path = os.path.join(STATIC_DIR, req_path)

        if os.path.exists(file_path) and os.path.isfile(file_path):
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "application/octet-stream"
            if mime_type.startswith("text/") or "javascript" in mime_type or "json" in mime_type:
                mime_type += "; charset=utf-8"

            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception as e:
                return self._send_json({"error": str(e)}, 500)

        self.send_error(404, f"Archivo no encontrado: {path}")

    def do_POST(self):
        # 1. Validar Filtro de IP
        if not self._check_ip_allowed():
            return self._send_json({
                "success": False,
                "error": f"Acceso denegado: Su dirección IP ({self.client_address[0]}) no está en la lista blanca."
            }, 403)

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        # Login público
        if path == "/api/auth/login":
            res, code = handle_login(body)
            return self._send_json(res, code)

        # Rutas que requieren autenticación
        user = self._get_auth_user()
        if not user:
            return self._send_json({
                "success": False,
                "error": "Sesión no válida o expirada. Por favor inicie sesión.",
                "auth_required": True
            }, 401)

        role = user.get("role", "lectura")

        # Logout
        if path == "/api/auth/logout":
            token = self.headers.get("Authorization") or self.headers.get("X-Auth-Token") or ""
            res, code = handle_logout(token)
            return self._send_json(res, code)

        # Gestión de administración (solo rol 'admin')
        if path == "/api/auth/users":
            res, code = handle_create_user(body, user)
            return self._send_json(res, code)

        if path == "/api/auth/ips":
            res, code = handle_save_ips(body, user)
            return self._send_json(res, code)

        if path == "/api/smartolt/config":
            if role != "admin":
                return self._send_json({
                    "success": False,
                    "error": "Permiso denegado: Solo el administrador puede modificar la configuración de la API de SmartOLT."
                }, 403)
            res, code = handle_save_smartolt_config(body)
            return self._send_json(res, code)

        # Acciones de Aprovisionamiento / Modificación (requieren rol 'admin' o 'aprovisionador')
        if role == "lectura":
            return self._send_json({
                "success": False,
                "error": "Permiso denegado: Los usuarios con rol de Solo Lectura no pueden realizar acciones de aprovisionamiento o modificación."
            }, 403)

        if path == "/api/probe":
            res, code = handle_probe(body)
            return self._send_json(res, code)

        if path == "/api/provision":
            res, code = handle_provision(body)
            return self._send_json(res, code)

        if path == "/api/provision/onu_only":
            res, code = handle_provision_onu_only(body)
            return self._send_json(res, code)

        if path == "/api/smartolt/authorize":
            res, code = handle_smartolt_authorize(body)
            return self._send_json(res, code)

        if path == "/api/smartolt/migrate_vlan":
            res, code = handle_smartolt_migrate_vlan(body, auth_user=user)
            return self._send_json(res, code)

        if path == "/api/smartolt/release_onu":
            res, code = handle_smartolt_release_onu(body, auth_user=user)
            return self._send_json(res, code)

        if path == "/api/config":
            res, code = handle_save_config(body)
            return self._send_json(res, code)

        if path == "/api/credentials":
            res, code = handle_save_credentials(body)
            return self._send_json(res, code)

        self.send_error(404, f"Endpoint no encontrado: {path}")

    def do_DELETE(self):
        if not self._check_ip_allowed():
            return self._send_json({
                "success": False,
                "error": f"Acceso denegado: Su dirección IP ({self.client_address[0]}) no está en la lista blanca."
            }, 403)

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        user = self._get_auth_user()
        if not user:
            return self._send_json({
                "success": False,
                "error": "Sesión no válida o expirada. Por favor inicie sesión.",
                "auth_required": True
            }, 401)

        # Eliminar usuario: /api/auth/users/{username}
        if path.startswith("/api/auth/users/"):
            target_username = path.replace("/api/auth/users/", "").strip()
            res, code = handle_delete_user(target_username, user)
            return self._send_json(res, code)

        self.send_error(404, f"Endpoint no encontrado: {path}")

    def log_message(self, format, *args):
        try:
            msg = format % args
            if "GET /api/progress" in msg or "GET /api/status" in msg or "GET /api/auth/session" in msg:
                return
        except Exception:
            pass
        super().log_message(format, *args)


def run_server(host="0.0.0.0", port=8088):
    server_address = (host, port)
    try:
        httpd = ThreadedHTTPServer(server_address, AppRequestHandler)
    except OSError as e:
        print(f"\n[AVISO] No se pudo iniciar el servidor en el puerto {port}: {e}")
        print(f"[INFO] Compruebe si el servidor ya se encuentra ejecutándose en http://localhost:{port}/")
        return

    print(f"[Powerlink Server] Escuchando en http://localhost:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido por el usuario.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_server()
