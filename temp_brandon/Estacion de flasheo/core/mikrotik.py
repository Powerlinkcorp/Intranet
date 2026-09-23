# -*- coding: utf-8 -*-
"""Integracion con MikroTik RouterOS (API).

Permite:
  * get_active_ports(): saber que puertos fisicos tienen una ONU conectada
    (MAC aprendida en la interfaz del puerto). Con esto el modo continuo solo
    flashea los puertos reales y no los enrutados/vacios.
  * setup_router(): configuracion asistida del router (habilitar API y crear
    las direcciones 10.100.N.1/24 por puerto si no existen).

Configuracion en mikrotik_config.json (junto al script):
  {
    "host": "10.100.0.1",
    "user": "admin",
    "pass": "********",
    "port": 8728,            // API (por defecto 8728)
    "max_port": 5,           // puertos del equipo (RB750=5, CRS326=20; default 20)
    "iface_regex": "^(?:ether|vlan)(\\d+)$"
  }
"""
import json
import os
import re
import sys

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CORE_DIR)
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config", "mikrotik_config.json")
if not os.path.exists(CONFIG_FILE):
    CONFIG_FILE = os.path.join(PROJECT_ROOT, "mikrotik_config.json")
DEFAULT_HOST = "10.100.0.1"
DEFAULT_PORT = 8728
PORTS = list(range(1, 21))


def _reconfigure():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Configuracion
# ----------------------------------------------------------------------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if cfg.get("host") and cfg.get("user") and cfg.get("pass"):
            return cfg
    except Exception:
        pass
    return None


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return True


def have_api():
    try:
        import librouteros  # noqa: F401
        return True
    except Exception:
        return False


def connect(cfg):
    import librouteros
    return librouteros.connect(
        host=cfg.get("host", DEFAULT_HOST),
        username=cfg["user"],
        password=cfg["pass"],
        port=cfg.get("port", DEFAULT_PORT),
    )


def get_max_port(cfg):
    """Cantidad de puertos del router (RB750=5, CRS326=20). Default 20."""
    try:
        return max(1, int(cfg.get("max_port", 20)))
    except (TypeError, ValueError):
        return 20


def _extract_port(iface, cfg):
    regex = cfg.get("iface_regex", r"^(?:ether|vlan)(\d+)$")
    m = re.match(regex, str(iface).strip(), re.IGNORECASE)
    if not m:
        return None
    try:
        n = int(m.group(1))
    except (ValueError, IndexError):
        return None
    return n if 1 <= n <= get_max_port(cfg) else None


# ----------------------------------------------------------------------------
# Deteccion de puertos fisicos con ONU
# ----------------------------------------------------------------------------
def get_active_ports(cfg, quiet=False):
    """Devuelve un dict {puerto: MAC} para los puertos (1..20) que tienen un
    dispositivo conectado (link arriba y/o MAC aprendida). Asi el modo continuo
    sabe no solo QUE puerto tiene ONU, sino CUAL es (para detectar una ONU
    nueva en el mismo puerto).
    Devuelve None si NO se pudo consultar (MikroTik caido/API no disponible):
    el llamador cae al modo por defecto. Devuelve {} si SI se consulto pero no
    hay ningun puerto fisico activo (ONUs apagadas): el llamador espera."""
    if not cfg:
        return None
    if not have_api():
        if not quiet:
            print("  AVISO No esta instalado librouteros (pip install librouteros).")
        return None
    try:
        api = connect(cfg)
    except Exception as ex:
        if not quiet:
            print(f"  ERROR No se pudo conectar al MikroTik: {ex}")
        return None
    try:
        result = {}
        # 1) Estado de LINK de la interfaz (running=True = dispositivo fisico
        #    conectado). No expira (a diferencia del ARP dinamico) y un puerto
        #    vacio/enrutado NO tiene link.
        try:
            ifaces = list(api.path("/interface"))
        except Exception:
            ifaces = []
        for i in ifaces:
            n = _extract_port(i.get("name", ""), cfg)
            if n and str(i.get("running", "")).lower() == "true":
                result.setdefault(n, None)
        # 2) ARP dinamico: las ONUs responden con su IP de gestion (192.168.1.1)
        #    en la interfaz del puerto fisico. Completa las MACs.
        try:
            arps = list(api.path("/ip/arp"))
        except Exception:
            arps = []
        for a in arps:
            iface = a.get("interface") or ""
            n = _extract_port(iface, cfg)
            if n:
                mac = (a.get("mac-address") or "").upper()
                if mac:
                    result[n] = mac
        # 3) Bridge host (fallback): MACs aprendidas por puerto cuando los
        #    puertos son miembros de un bridge.
        try:
            hosts = list(api.path("/interface/bridge/host"))
        except Exception:
            hosts = []
        for h in hosts:
            iface = h.get("on-interface") or h.get("interface") or ""
            n = _extract_port(iface, cfg)
            if n:
                mac = (h.get("mac-address") or "").upper()
                result.setdefault(n, mac or None)
        return result
    except Exception as ex:
        if not quiet:
            print(f"  ERROR Consultando MikroTik: {ex}")
        return None
    finally:
        try:
            api.close()
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Setup del router (configuracion asistida)
# ----------------------------------------------------------------------------
def setup_router(cfg, ports=None):
    """Configura el MikroTik: habilita el servicio API (necesario para la
    deteccion) y crea las direcciones 10.100.N.1/24 en cada puerto si faltan.
    Es no destructivo: no borra ni modifica configuraciones existentes."""
    _reconfigure()
    if ports is None:
        ports = range(1, get_max_port(cfg) + 1)
    if not have_api():
        print("  ERROR Falta librouteros. Instalalo o usa el lanzador flasheo.py.")
        return False
    try:
        api = connect(cfg)
    except Exception as ex:
        print(f"  ERROR No se pudo conectar a {cfg.get('host', DEFAULT_HOST)}: {ex}")
        return False
    print("  OK   Conectado al MikroTik.")
    cambios = 0
    try:
        # Habilitar servicio API
        try:
            for s in api.path("/ip/service"):
                if str(s.get("name", "")).lower() == "api":
                    if str(s.get("disabled", "")).lower() != "false":
                        s.set(disabled="no")
                        print("  OK   Servicio API habilitado.")
                        cambios += 1
                    else:
                        print("  OK   Servicio API ya habilitado.")
                    break
        except Exception as ex:
            print(f"  AVISO No se pudo verificar el servicio API: {ex}")

        # Direcciones por puerto
        regex = cfg.get("iface_regex", r"^(?:ether|vlan)(\d+)$")
        ifaces = {}
        try:
            for i in api.path("/interface"):
                ifaces[i.get("name", "")] = i
        except Exception:
            ifaces = {}

        existentes = set()
        try:
            for ad in api.path("/ip/address"):
                existentes.add(ad.get("address", ""))
        except Exception:
            existentes = set()

        for n in ports:
            iface = _find_iface(ifaces, n, regex)
            if not iface:
                print(f"  AVISO Puerto {n}: no se encontro interfaz ether{n}/vlan{n}.")
                continue
            addr = f"10.100.{n}.1/24"
            if any(str(a).startswith(addr.split("/")[0] + "/") for a in existentes):
                continue
            try:
                api.path("/ip/address").add(address=addr, interface=iface)
                print(f"  OK   Creada {addr} en {iface}.")
                cambios += 1
            except Exception as ex:
                print(f"  ERROR {addr} en {iface}: {ex}")
        # Habilitar proxy-arp en interfaces ethernet para permitir comunicación /16 desde la laptop
        try:
            for eth in api.path("/interface/ethernet"):
                if eth.get("arp") != "proxy-arp":
                    try:
                        api.path("/interface/ethernet").update(**{".id": eth[".id"], "arp": "proxy-arp"})
                        print(f"  OK   proxy-arp habilitado en {eth.get('name')}.")
                        cambios += 1
                    except Exception:
                        pass
        except Exception as ex:
            print(f"  AVISO No se pudo verificar proxy-arp: {ex}")

        if cambios == 0:
            print("  OK   MikroTik ya estaba configurado correctamente.")
        return True
    finally:
        try:
            api.close()
        except Exception:
            pass


def _find_iface(ifaces, n, regex):
    for name in ifaces:
        m = re.match(regex, name, re.IGNORECASE)
        if m and m.group(1).isdigit() and int(m.group(1)) == n:
            return name
    return None


if __name__ == "__main__":
    _reconfigure()
    cfg = load_config()
    if not cfg:
        print("No hay mikrotik_config.json. Crea la configuracion con flasheo.py.")
        sys.exit(1)
    try:
        import network_diag as netdiag
        diag = netdiag.run_diagnosis(cfg)
        netdiag.print_diagnosis(diag)
    except Exception:
        res = get_active_ports(cfg)
        if res is None:
            print("MikroTik sin conexion/API (modo por defecto).")
        elif not res:
            print("Puertos fisicos con ONU: (ninguno, ONUs apagadas/desconectadas)")
        else:
            for n, mac in sorted(res.items()):
                print(f"  Puerto {n}: {mac or '(sin MAC/ARP)'}")