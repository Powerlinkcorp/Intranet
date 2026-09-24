import sys, time, urllib.request, urllib.error, tempfile, os
from datetime import datetime

LOG_FILE = os.path.join(tempfile.gettempdir(), "fleet_monitor.log")
PORTS = list(range(1, 21))
INTERVAL = 30

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def log(msg):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(line, flush=True)

def check(ip):
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(f"http://{ip}/", method="GET",
                                 headers={"Host": "192.168.1.1",
                                          "User-Agent": "Mozilla/5.0"})
    try:
        r = opener.open(req, timeout=6)
        body = r.read(200).decode("utf-8", "replace")
        return "OK" if "<html" in body.lower() or "doctype" in body.lower() else "OK?"
    except urllib.error.HTTPError as ex:
        loc = ex.headers.get("Location", "")
        if ex.code == 302 and "conn-fail" in loc:
            return "CONN_FAIL"
        return f"HTTP{ex.code}"
    except Exception:
        return "SIN_RESP"

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    log("monitor iniciado: sondeo cada %ds de puertos %s" % (INTERVAL, PORTS))
    prev = {p: None for p in PORTS}
    first = True
    while True:
        states = {}
        for p in PORTS:
            states[p] = check(f"10.100.{p}.1")
        if first:
            first = False
            log("estado inicial: " + ", ".join(f"P{p}={states[p]}" for p in PORTS))
        for p in PORTS:
            if prev[p] is not None and prev[p] != states[p]:
                if prev[p] == "CONN_FAIL" and states[p] == "OK":
                    log(f"ALERTA: P{p} (10.100.{p}.1) VOLVIO A NORMAL - lista para flashear/verificar")
                elif states[p] == "CONN_FAIL":
                    log(f"P{p} (10.100.{p}.1) entro en CONN_FAIL (antes {prev[p]})")
                else:
                    log(f"P{p} (10.100.{p}.1): {prev[p]} -> {states[p]}")
            prev[p] = states[p]
        ok = [p for p in PORTS if states[p] == "OK"]
        if ok:
            log("RESUMEN: puertos NORMAL: " + ", ".join(f"P{p}" for p in ok))
        else:
            log("RESUMEN: sin puertos en NORMAL (todo conn-fail)")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
