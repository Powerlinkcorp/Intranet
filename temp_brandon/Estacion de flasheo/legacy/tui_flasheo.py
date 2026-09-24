# -*- coding: utf-8 -*-
"""TUI estatica de seguimiento del flasheo de ONUs VSOL (V2804AX30-H).

Lee el archivo compartido `estado.json` (escrito por vsol_autopilot.py) y
dibuja en pantalla un panel fijo con la lista de puertos del MikroTik
(ether1..ether20 -> 10.100.1.1..10.100.20.1), su estado con iconos y colores,
progreso y leyenda. Se actualiza en el lugar (no hace scroll) y se cierra
con Ctrl+C.
"""
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(BASE_DIR, "estado.json")

# Puertos del MikroTik: ether1..ether20 -> 10.100.1.1..10.100.20.1
PORTS = ["10.100.%d.1" % i for i in range(1, 21)]

# estado -> (icono, codigo color ANSI)
MAP = {
    "YA_CONFIGURADA":   ("\u2713", "32"),
    "EXITO":            ("\u2713", "32"),
    "CHECK_OK":         ("\u2713", "32"),
    "CHECK_OK_SIN_VLAN":("\u26a0", "33"),
    "EXITO_LOGIN_FINAL":("\u26a0", "33"),
    "PARCIAL":          ("\u26a0", "33"),
    "SIN_ONU":          ("\u25cb", "90"),
    "ESPERANDO":        ("\u23f3", "33"),
    "CONECTADO":        ("\u25cf", "32"),
    "LOGIN":            ("\u270e", "33"),
    "LOGIN_OK":         ("\u2713", "32"),
    "WIZARD":           ("\u2699", "36"),
    "FLASHEANDO":       ("\u2b06", "36"),
    "REINICIANDO":      ("\u21bb", "33"),
    "VERIFICANDO":      ("\u25c9", "34"),
    "LISTA":            ("\u2714", "1;32"),
    "PAUSA":            ("\u23f8", "33"),
    "ERROR":            ("\u2717", "31"),
}
DEFAULT = ("\u00b7", "90")

# Estados considerados "terminados" (cuentan como configuradas en el panel)
OK_STATES = ("YA_CONFIGURADA", "EXITO", "CHECK_OK", "EXITO_LOGIN_FINAL",
             "PARCIAL", "LISTA")
PROC_STATES = ("ESPERANDO", "CONECTADO", "LOGIN", "LOGIN_OK", "WIZARD",
               "FLASHEANDO", "REINICIANDO", "VERIFICANDO")

W = 70
N_LINES = 5 + len(PORTS) + 3


def enable_vt():
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)
            mode = k.GetConsoleMode(h)
            k.SetConsoleMode(h, mode | 0x0004)
        except Exception:
            pass


def c(text, code):
    if code:
        return "\x1b[%sm%s\x1b[0m" % (code, text)
    return text


def load_status():
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"onus": [], "total": len(PORTS), "procesadas": 0, "en_curso": 0}


def build_frame(status):
    now = time.strftime("%H:%M:%S")
    total = status.get("total", len(PORTS))
    onus = {}
    for o in status.get("onus", []):
        onus[str(o.get("puerto"))] = o

    ok_n = sum(1 for o in onus.values() if o.get("estado") in OK_STATES)
    proc_n = sum(1 for o in onus.values() if o.get("estado") in PROC_STATES)
    err_n = sum(1 for o in onus.values() if o.get("estado") == "ERROR")

    lines = []
    lines.append(c("=" * W, "1;36"))
    lines.append(c("  VSOL FLASHEO  |  ONUs V2804AX30-H (Powerlink)", "1;37"))
    lines.append(c("  Hora: %s   Listas: %s   En proceso: %s   Errores: %s"
                   % (now, ok_n, proc_n, err_n), "37"))
    lines.append(c("=" * W, "1;36"))
    for idx, ip in enumerate(PORTS, start=1):
        p = "P%02d" % idx
        o = onus.get(str(idx))
        if not o or o.get("estado") == "SIN_ONU":
            base = "  %s  %-14s  %s  esperando ONU nueva ..." % (p, ip, "\u25cb")
            lines.append(c(base, "90"))
        else:
            estado = o.get("estado", "?")
            icon, col = MAP.get(estado, DEFAULT)
            det = (o.get("detalle") or "").replace("Fallo: ", "")[:20]
            # Tiempo transcurrido en el estado actual
            desde = o.get("desde")
            if desde:
                mins = int((time.time() - desde) // 60)
                secs = int((time.time() - desde) % 60)
                det = "%s [%dm%02ds]" % (det, mins, secs)
            base = "  %s  %-14s  %s  %-15s  %s" % (p, ip, icon, estado, det)
            lines.append(c(base, col))
    lines.append(c("=" * W, "1;36"))
    lines.append("  LEYENDA:  \u2714 LISTA (retirar/conectar otra)  \u2713 flasheada  "
                 "\u23f3/\u25cf/\u270e/\u2699/\u2b06/\u21bb/\u25c9 proceso  "
                 "\u26a0 parcial  \u2717 error  \u25cb sin ONU / esperando")
    lines.append("  Conecta una ONU nueva a un puerto y se configurara sola.  (Ctrl+C para salir)")
    while len(lines) < N_LINES:
        lines.append("")
    return lines


def draw(lines):
    out = "\x1b[2J\x1b[H"
    for line in lines:
        out += line.ljust(W) + "\n"
    sys.stdout.write(out)
    sys.stdout.flush()


def run():
    enable_vt()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        while True:
            draw(build_frame(load_status()))
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()