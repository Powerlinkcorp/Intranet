"""Proxy web local para acceder a la web de las ONUs desde el navegador.

Las ONUs solo sirven su web si el header Host es su IP de gestion (192.168.1.1).
Este proxy fuerza ese Host y reescribe las URLs absolutas a localhost, de modo
que puedes abrir en tu navegador:

    http://localhost:8090/        -> indice con acceso a las 20 ONUs
    http://localhost:8091/        -> web de la ONU del puerto 1 (10.100.1.1)
    http://localhost:8092/        -> web de la ONU del puerto 2 (10.100.2.1)
    ...
    http://localhost:8110/        -> web de la ONU del puerto 20

Uso:
    python onu_web_proxy.py                # base 8090 (8090=indice, 8091..8110=ONUs)
    python onu_web_proxy.py --port 9000    # 9000=indice, 9001..9020=ONUs
"""

import http.server
import sys
import json
import gzip
import re
import urllib.request
import urllib.error

TARGET_HOST = "192.168.1.1"
BASE_PORT = 8090

# Puertos que realmente tienen ONU fisica conectada. El switch enruta todos los
# IPs virtuales 10.100.N.1 hacia las ONUs reales, por lo que puertos sin ONU
# tambien "responden". El indice solo lista estos puertos.
# Se puede sobreescribir con:  --ports "1-4,7-8"   o   --ports "1,2,3,4"
ACTIVE_PORTS = [1, 2, 3, 4]

INDEX = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>ONUs VSOL</title>
<style>body{font-family:monospace;background:#111;color:#ddd;padding:20px}
a{color:#4af;text-decoration:none;display:block;padding:4px}
a:hover{color:#8cf}</style></head><body>
<h2>Acceso web a las ONUs (proxy Host: 192.168.1.1)</h2>
<h3>Puertos con ONU conectada:</h3>
{links}<h3>Credenciales:</h3>
<p>Estado final: <b>Powerlink</b> / <b>Powerlink2026*</b></p>
<p>Factory default: <b>admin</b> / <b>stdONU101</b></p>
<p>Estado intermedio: <b>admin</b> / <b>admin123</b></p>
</body></html>"""


def _is_text(ctype):
    c = (ctype or "").lower()
    return any(k in c for k in ("html", "javascript", "json", "xml", "text/", "svg"))


def make_handler(onu_port):
    """onu_port: None = indice, N = ONU del puerto N."""

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            self._proxy("GET")

        def do_POST(self):
            self._proxy("POST")

        def do_PUT(self):
            self._proxy("PUT")

        def do_DELETE(self):
            self._proxy("DELETE")

        def _send_index(self):
            links = "".join(
                f'<a href="http://localhost:{BASE_PORT + n}/">Puerto {n} '
                f'- 10.100.{n}.1</a>' for n in ACTIVE_PORTS)
            body = INDEX.replace("{links}", links).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _proxy(self, method):
            if onu_port is None:
                return self._send_index()
            port = onu_port
            local = f"http://localhost:{self.server.server_address[1]}"
            target = f"http://10.100.{port}.1{self.path}"

            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else None

            hdrs = {k: v for k, v in self.headers.items()
                    if k.lower() not in ("host", "content-length", "connection",
                                         "accept-encoding", "transfer-encoding")}
            hdrs["Host"] = TARGET_HOST

            req = urllib.request.Request(target, data=body, method=method,
                                         headers=hdrs)
            try:
                r = urllib.request.urlopen(req, timeout=60)
                resp = r.read()
                enc = (r.headers.get("Content-Encoding") or "").lower()
                if enc == "gzip":
                    resp = gzip.decompress(resp)
                    enc = ""
                rewrote = False
                if _is_text(r.headers.get("Content-Type", "")):
                    txt = resp.decode("utf-8", "replace")
                    txt = txt.replace("http://192.168.1.1", local)
                    if "web_custom_show" in self.path:
                        try:
                            obj = json.loads(txt)
                            obj.setdefault("data", {})["web_captcha"] = "0"
                            obj["data"]["show_captcha"] = "0"
                            txt = json.dumps(obj)
                        except Exception:
                            pass
                    resp = txt.encode("utf-8", "replace")
                    rewrote = True
                self.send_response(r.status)
                for k, v in r.headers.items():
                    kl = k.lower()
                    if kl in ("content-length", "connection", "transfer-encoding",
                              "content-encoding", "accept-encoding"):
                        continue
                    if kl == "location":
                        v = v.replace("http://192.168.1.1", local)
                    self.send_header(k, v)
                if not rewrote and enc == "gzip":
                    self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            except urllib.error.HTTPError as ex:
                try:
                    b = ex.read()
                    if _is_text(ex.headers.get("Content-Type", "")):
                        b = b.decode("utf-8", "replace").replace(
                            "http://192.168.1.1", local).encode()
                    self.send_response(ex.code)
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                except Exception:
                    self.send_response(ex.code)
                    self.end_headers()
            except Exception as ex:
                msg = f"Error al acceder a 10.100.{port}.1: {ex}".encode()
                self.send_response(502)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)

    return Handler


def _parse_ports(spec):
    """'1,2,3,4' o '1-4,7-8' -> [1,2,3,4,7,8]"""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return sorted(set(out))


def main():
    global BASE_PORT, ACTIVE_PORTS
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--port" and i + 1 < len(args):
            try:
                BASE_PORT = int(args[i + 1])
            except ValueError:
                pass
        if a == "--ports" and i + 1 < len(args):
            try:
                ACTIVE_PORTS = _parse_ports(args[i + 1])
            except Exception:
                pass
    servers = []
    try:
        # BASE = indice, BASE+1..BASE+20 = ONUs 1..20
        servers.append(http.server.ThreadingHTTPServer(
            ("127.0.0.1", BASE_PORT), make_handler(None)))
        for n in range(1, 21):
            servers.append(http.server.ThreadingHTTPServer(
                ("127.0.0.1", BASE_PORT + n), make_handler(n)))
    except OSError as ex:
        print(f"[proxy] ERROR al abrir puertos: {ex}")
        sys.exit(1)
    for s in servers:
        import threading
        threading.Thread(target=s.serve_forever, daemon=True).start()
    print(f"[proxy] Indice : http://localhost:{BASE_PORT}/")
    print(f"[proxy] Puertos activos (con ONU): {ACTIVE_PORTS}")
    for n in ACTIVE_PORTS:
        print(f"[proxy]   ONU P{n} : http://localhost:{BASE_PORT + n}/  (10.100.{n}.1)")
    print(f"[proxy] Forzando Host: {TARGET_HOST}")
    try:
        while True:
            import time
            time.sleep(3600)
    except KeyboardInterrupt:
        for s in servers:
            s.shutdown()
        print("\n[proxy] detenido.")


if __name__ == "__main__":
    main()
