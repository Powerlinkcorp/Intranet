# -*- coding: utf-8 -*-
"""
network_diag.py — Diagnóstico y configuración de red para la Estación de Flasheo.

Funciones:
  * Diagnóstico de adaptadores de red (Ethernet / USB Ethernet / Wi-Fi).
  * Verificación de estado del cable (Link Up / Down) y velocidad.
  * Verificación de IP de la laptop en el rango correcto (10.100.0.0/16).
  * Prueba de conectividad con MikroTik (Ping, Puerto API 8728, Login API).
  * Auto-configuración de IP estática y restauración a DHCP con elevación UAC limpia.
"""
import base64
import ctypes
import ipaddress
import json
import os
import socket
import subprocess
import sys
import time

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CORE_DIR)
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config", "mikrotik_config.json")
if not os.path.exists(CONFIG_FILE):
    CONFIG_FILE = os.path.join(PROJECT_ROOT, "mikrotik_config.json")
DEFAULT_HOST = "10.100.0.1"
DEFAULT_PORT = 8728
DEFAULT_LAPTOP_IP = "10.100.0.100"
DEFAULT_LAPTOP_MASK = "255.255.0.0"
DEFAULT_ONU_DIRECT_IP = "192.168.1.100"
DEFAULT_ONU_DIRECT_MASK = "255.255.255.0"


def _reconfigure():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def is_admin():
    """Comprueba si el proceso actual tiene permisos de Administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


# ----------------------------------------------------------------------------
# 1) Obtención de adaptadores y direcciones IP
# ----------------------------------------------------------------------------
def get_raw_adapters():
    """Obtiene la lista de adaptadores de red mediante PowerShell."""
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        "Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, LinkSpeed, InterfaceIndex, MacAddress | ConvertTo-Json -Depth 2",
    ]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=6
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            if isinstance(data, dict):
                return [data]
            elif isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def get_raw_ips():
    """Obtiene las direcciones IPv4 asignadas mediante PowerShell."""
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        "Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress, PrefixLength, InterfaceIndex | ConvertTo-Json -Depth 2",
    ]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=6
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            if isinstance(data, dict):
                return [data]
            elif isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def prefix_to_mask(prefix):
    """Convierte longitud de prefijo (ej: 16 o 24) a máscara de red (ej: 255.255.0.0)."""
    try:
        net = ipaddress.IPv4Network(f"0.0.0.0/{prefix}")
        return str(net.netmask)
    except Exception:
        return ""


def is_in_subnet(ip_str, subnet_str="10.100.0.0/16"):
    """Comprueba si una IP pertenece a una subred dada."""
    try:
        ip = ipaddress.IPv4Address(ip_str)
        net = ipaddress.IPv4Network(subnet_str, strict=False)
        return ip in net
    except Exception:
        return False


def get_network_interfaces():
    """Retorna una lista detallada de adaptadores con sus IPs y características."""
    raw_adapters = get_raw_adapters()
    raw_ips = get_raw_ips()

    # Mapear IPs por InterfaceAlias o InterfaceIndex
    ips_by_alias = {}
    ips_by_index = {}
    for item in raw_ips:
        alias = item.get("InterfaceAlias")
        idx = item.get("InterfaceIndex")
        ip = item.get("IPAddress")
        prefix = item.get("PrefixLength", 24)
        if not ip:
            continue
        entry = {
            "ip": ip,
            "prefix": prefix,
            "mask": prefix_to_mask(prefix),
            "is_apipa": ip.startswith("169.254."),
            "is_loopback": ip.startswith("127."),
        }
        if alias:
            ips_by_alias.setdefault(alias, []).append(entry)
        if idx is not None:
            ips_by_index.setdefault(idx, []).append(entry)

    adapters = []
    for a in raw_adapters:
        name = a.get("Name", "")
        desc = a.get("InterfaceDescription", "")
        status = str(a.get("Status", "Unknown"))
        speed = str(a.get("LinkSpeed", ""))
        idx = a.get("InterfaceIndex")
        mac = a.get("MacAddress", "")

        adapter_ips = ips_by_alias.get(name) or ips_by_index.get(idx) or []

        # Clasificación
        name_lower = name.lower()
        desc_lower = desc.lower()
        is_wifi = "wi-fi" in name_lower or "wireless" in desc_lower or "wlan" in desc_lower or "802.11" in desc_lower
        is_bluetooth = "bluetooth" in name_lower or "bluetooth" in desc_lower
        is_virtual = "virtual" in desc_lower or "vpn" in desc_lower or "loopback" in desc_lower

        is_ethernet = (not is_wifi and not is_bluetooth and not is_virtual) or ("ethernet" in name_lower or "gigabit" in desc_lower or "lan" in desc_lower or "asix" in desc_lower or "realtek" in desc_lower)

        has_target_ip = any(is_in_subnet(item["ip"], "10.100.0.0/16") for item in adapter_ips)
        has_direct_onu_ip = any(is_in_subnet(item["ip"], "192.168.1.0/24") for item in adapter_ips)
        has_apipa = any(item["is_apipa"] for item in adapter_ips)

        adapters.append({
            "name": name,
            "desc": desc,
            "status": status,  # "Up", "Disconnected", "Disabled"
            "speed": speed,
            "index": idx,
            "mac": mac,
            "ips": adapter_ips,
            "is_ethernet": is_ethernet,
            "is_wifi": is_wifi,
            "has_target_ip": has_target_ip,
            "has_direct_onu_ip": has_direct_onu_ip,
            "has_apipa": has_apipa,
        })

    return adapters


# ----------------------------------------------------------------------------
# 2) Pruebas de conectividad
# ----------------------------------------------------------------------------
def test_ping(host, timeout_ms=1000):
    """Realiza un ping rápido a un host."""
    try:
        res = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout_ms), host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2.0,
        )
        return res.returncode == 0
    except Exception:
        return False


def test_tcp_port(host, port, timeout=1.2):
    """Verifica si un puerto TCP está abierto y responde."""
    try:
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.close()
        return True, "Abierto"
    except socket.timeout:
        return False, "Tiempo de espera agotado (Timeout)"
    except ConnectionRefusedError:
        return False, "Conexión rechazada (Puerto cerrado)"
    except Exception as ex:
        return False, str(ex)


def test_mikrotik_api(cfg, timeout=3.0):
    """Prueba autenticación con el servicio API de MikroTik."""
    try:
        import librouteros
    except ImportError:
        return False, "Falta la librería librouteros"

    host = cfg.get("host", DEFAULT_HOST)
    user = cfg.get("user", "admin")
    password = cfg.get("pass", "")
    port = int(cfg.get("port", DEFAULT_PORT))

    try:
        api = librouteros.connect(
            host=host,
            username=user,
            password=password,
            port=port,
            timeout=timeout,
        )
        # Consultar recursos básicos para confirmar que la sesión responde
        identity = "MikroTik"
        try:
            for item in api.path("/system/identity"):
                identity = item.get("name", identity)
        except Exception:
            pass

        # Consultar puertos
        active_ports = {}
        try:
            from mikrotik import get_active_ports
            active_ports = get_active_ports(cfg, quiet=True) or {}
        except Exception:
            pass

        api.close()
        return True, {
            "identity": identity,
            "active_ports": active_ports,
        }
    except Exception as ex:
        return False, str(ex)


# ----------------------------------------------------------------------------
# 3) Diagnóstico integral de la estación de flasheo
# ----------------------------------------------------------------------------
def run_diagnosis(cfg=None):
    """Ejecuta el diagnóstico completo de adaptadores, IP y MikroTik."""
    if cfg is None:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                cfg = {}
        else:
            cfg = {}

    host = cfg.get("host", DEFAULT_HOST)
    api_port = int(cfg.get("port", DEFAULT_PORT))

    adapters = get_network_interfaces()
    ethernet_adapters = [a for a in adapters if a["is_ethernet"]]

    # Buscar si algún adaptador Ethernet está Up
    connected_ethernets = [a for a in ethernet_adapters if a["status"].lower() == "up"]
    
    # Buscar si la laptop tiene IP 10.100.x.x
    has_target_ip = any(a["has_target_ip"] for a in adapters)
    target_adapters = [a for a in adapters if a["has_target_ip"]]

    # Probar MikroTik
    ping_ok = test_ping(host, timeout_ms=1000)
    api_port_ok, api_port_msg = test_tcp_port(host, api_port, timeout=1.2)
    web_port_ok, _ = test_tcp_port(host, 80, timeout=0.8)

    api_auth_ok = False
    api_auth_info = None
    if api_port_ok and cfg.get("user"):
        api_auth_ok, api_auth_info = test_mikrotik_api(cfg, timeout=2.5)

    # Estado global
    all_ready = (
        bool(connected_ethernets)
        and has_target_ip
        and ping_ok
        and api_port_ok
        and (api_auth_ok if cfg.get("user") else True)
    )

    return {
        "cfg": cfg,
        "host": host,
        "api_port": api_port,
        "adapters": adapters,
        "ethernet_adapters": ethernet_adapters,
        "connected_ethernets": connected_ethernets,
        "has_target_ip": has_target_ip,
        "target_adapters": target_adapters,
        "ping_ok": ping_ok,
        "api_port_ok": api_port_ok,
        "api_port_msg": api_port_msg,
        "web_port_ok": web_port_ok,
        "api_auth_ok": api_auth_ok,
        "api_auth_info": api_auth_info,
        "all_ready": all_ready,
    }


def print_diagnosis(diag):
    """Muestra el reporte visual intuitivo en consola."""
    _reconfigure()
    print()
    print("=" * 64)
    print("      DIAGNOSTICO DE RED Y MIKROTIK - ESTACION DE FLASHEO")
    print("=" * 64)

    # 1. Adaptadores Ethernet
    print("\n  [1] ESTADO DE CONEXION FISICA (CABLE ETHERNET):")
    if not diag["ethernet_adapters"]:
        print("      AVISO: No se detectaron adaptadores Ethernet en la laptop.")
    else:
        for a in diag["ethernet_adapters"]:
            status_text = a["status"].upper()
            if a["status"].lower() == "up":
                speed_str = f" ({a['speed']})" if a["speed"] else ""
                print(f"      OK    {a['name']}: CONECTADO [Link Up]{speed_str}")
                print(f"            Dispositivo: {a['desc']}")
            else:
                print(f"      AVISO {a['name']}: DESCONECTADO [Sin cable / Router apagado]")
                print(f"            Dispositivo: {a['desc']}")

    # 2. Direcciones IP de la Laptop
    print("\n  [2] RANGO DE IP DE LA LAPTOP:")
    if diag["has_target_ip"]:
        for a in diag["target_adapters"]:
            for ip_info in a["ips"]:
                if is_in_subnet(ip_info["ip"], "10.100.0.0/16"):
                    print(f"      OK    {a['name']}: IP {ip_info['ip']} / Mascara {ip_info['mask']}")
        print("            -> La laptop esta en el rango correcto (10.100.0.0/16).")
    else:
        print("      ERROR La laptop NO tiene una IP en la red 10.100.0.0/16.")
        for a in diag["ethernet_adapters"]:
            if a["ips"]:
                for ip_info in a["ips"]:
                    print(f"            {a['name']}: IP actual = {ip_info['ip']} ({ip_info['mask']})")
            else:
                print(f"            {a['name']}: Sin IP asignada")
        print("            -> Se recomienda configurar IP fija (ej: 10.100.0.100 / 255.255.0.0).")

    # 3. Comunicación con MikroTik
    host = diag["host"]
    port = diag["api_port"]
    print(f"\n  [3] COMUNICACION CON EL ROUTER MIKROTIK ({host}):")
    if diag["ping_ok"]:
        print(f"      OK    Ping a {host}: Responde correctamente.")
    else:
        print(f"      ERROR Ping a {host}: No responde (inaccesible desde esta IP o cable).")

    if diag["api_port_ok"]:
        print(f"      OK    Puerto API {port}: Abierto y accesible.")
    else:
        print(f"      AVISO Puerto API {port}: {diag['api_port_msg']}")

    if diag["api_port_ok"]:
        if diag["api_auth_ok"]:
            info_dict = diag["api_auth_info"] or {}
            ident = info_dict.get("identity", "MikroTik")
            ports_detected = info_dict.get("active_ports", {})
            print(f"      OK    Login API: Exitoso en router '{ident}'.")
            if ports_detected:
                print(f"            Puertos fisicos con ONU detectados: {len(ports_detected)} {list(ports_detected.keys())}")
            else:
                print("            Puertos con ONU: Ninguno detectado (ONUs apagadas o sin conectar).")
        else:
            err = diag["api_auth_info"] if isinstance(diag["api_auth_info"], str) else "Fallo de credenciales"
            print(f"      ERROR Login API: {err}")

    # 4. Resumen y recomendaciones
    print("\n" + "-" * 64)
    if diag["all_ready"]:
        print("  RESULTADO: ESTACION LISTA PARA FLASHEAR ONUS")
        print("  Todas las conexiones e IPs estan operativas.")
    else:
        print("  ACCIONES RECOMENDADAS:")
        if not diag["connected_ethernets"]:
            print("  * Conectar el cable Ethernet entre la laptop y el MikroTik.")
        if not diag["has_target_ip"]:
            print("  * Asignar IP estatica 10.100.0.100 / 255.255.0.0 a la tarjeta Ethernet.")
            print("    (Puedes usar la opcion 'Auto-configurar IP' para hacerlo en 1 clic)")
        elif not diag["ping_ok"]:
            print("  * Verificar que el MikroTik este encendido y en la IP 10.100.0.1.")
        elif not diag["api_port_ok"]:
            print("  * Habilitar el servicio API en el MikroTik (opcion 4 del menu principal).")
        elif not diag["api_auth_ok"]:
            print("  * Verificar usuario y contrasena del MikroTik en mikrotik_config.json.")
    print("=" * 64)
    print()


# ----------------------------------------------------------------------------
# 4) Implementación / Auto-configuración de IP
# ----------------------------------------------------------------------------
def _run_ps_script(script_text, require_admin=True):
    """Ejecuta un script PowerShell mediante Base64 (-EncodedCommand).
    Si no tiene permisos de administrador, solicita elevación UAC."""
    encoded = base64.b64encode(script_text.encode("utf-16le")).decode("ascii")
    if is_admin() or not require_admin:
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-EncodedCommand", encoded,
        ]
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True, errors="replace", timeout=15
            )
            return res.returncode == 0, (res.stdout + " " + res.stderr).strip()
        except Exception as ex:
            return False, str(ex)

    # Elevación UAC mediante Start-Process
    ps_launcher = (
        f"Start-Process powershell.exe -Verb RunAs -Wait "
        f"-ArgumentList '-NoProfile -ExecutionPolicy Bypass -EncodedCommand {encoded}'"
    )
    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_launcher],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=35,
        )
        return res.returncode == 0, res.stdout.strip()
    except Exception as ex:
        return False, str(ex)


def set_adapter_ip(adapter_name, ip="10.100.0.100", netmask="255.255.0.0", gateway=""):
    """Configura una IP estática en el adaptador indicado."""
    _reconfigure()
    print(f"\n  Configurando {adapter_name} -> IP: {ip}, Mascara: {netmask} ...")
    
    try:
        prefix = ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
    except Exception:
        prefix = 16

    gw_line = f'$gw = "{gateway}"' if gateway else '$gw = $null'
    
    ps_script = f"""
$adapter = "{adapter_name}"
$ip = "{ip}"
$mask = "{netmask}"
$prefix = {prefix}
{gw_line}

# 1. Configurar con netsh usando sintaxis explicita
if ($gw -and $gw.Trim() -ne "") {{
    & netsh interface ipv4 set address name=$adapter source=static address=$ip mask=$mask gateway=$gw
}} else {{
    & netsh interface ipv4 set address name=$adapter source=static address=$ip mask=$mask gateway=none
}}

# 2. Respaldo directo con cmdlets de PowerShell
try {{
    $current = Get-NetIPAddress -InterfaceAlias $adapter -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {{ $_.IPAddress -eq $ip }}
    if (-not $current) {{
        Get-NetIPAddress -InterfaceAlias $adapter -AddressFamily IPv4 -ErrorAction SilentlyContinue | Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
        if ($gw -and $gw.Trim() -ne "") {{
            New-NetIPAddress -InterfaceAlias $adapter -IPAddress $ip -PrefixLength $prefix -DefaultGateway $gw -ErrorAction SilentlyContinue
        }} else {{
            New-NetIPAddress -InterfaceAlias $adapter -IPAddress $ip -PrefixLength $prefix -ErrorAction SilentlyContinue
        }}
    }}
}} catch {{}}
"""
    _run_ps_script(ps_script, require_admin=True)

    # Esperar un instante y verificar
    time.sleep(2)
    adapters = get_network_interfaces()
    target_adapter = next((a for a in adapters if a["name"].lower() == adapter_name.lower()), None)
    if target_adapter and any(ip_info["ip"] == ip for ip_info in target_adapter["ips"]):
        print(f"  OK   IP {ip} asignada exitosamente a '{adapter_name}'.")
        return True, "Configurado con éxito"
    
    time.sleep(1)
    adapters = get_network_interfaces()
    target_adapter = next((a for a in adapters if a["name"].lower() == adapter_name.lower()), None)
    if target_adapter and any(ip_info["ip"] == ip for ip_info in target_adapter["ips"]):
        print(f"  OK   IP {ip} asignada exitosamente a '{adapter_name}'.")
        return True, "Configurado con éxito"

    print(f"  AVISO Verifique si acepto la solicitud de permisos de Administrador (UAC) en pantalla.")
    return False, "No se detecto la nueva IP"


def set_adapter_dhcp(adapter_name):
    """Restaura el adaptador a IP automática (DHCP)."""
    _reconfigure()
    print(f"\n  Restaurando {adapter_name} a DHCP (IP Automatica) ...")
    
    ps_script = f"""
$adapter = "{adapter_name}"
& netsh interface ipv4 set address name=$adapter source=dhcp
& netsh interface ipv4 set dns name=$adapter source=dhcp
try {{
    Set-NetIPInterface -InterfaceAlias $adapter -Dhcp Enabled -ErrorAction SilentlyContinue
}} catch {{}}
"""
    _run_ps_script(ps_script, require_admin=True)

    time.sleep(2)
    print(f"  OK   Adaptador '{adapter_name}' restaurado a DHCP.")
    return True, "Restaurado a DHCP"


def pick_ethernet_adapter(adapters=None):
    """Permite al usuario seleccionar el adaptador Ethernet adecuado si hay varios."""
    if adapters is None:
        adapters = get_network_interfaces()
    
    ethernets = [a for a in adapters if a["is_ethernet"]]
    if not ethernets:
        ethernets = adapters  # fallback a todos

    if len(ethernets) == 1:
        return ethernets[0]["name"]

    # Si hay uno Up, sugerirlo como predeterminado
    default_idx = 1
    for i, a in enumerate(ethernets, 1):
        if a["status"].lower() == "up":
            default_idx = i
            break

    print("\n  Selecciona el adaptador de red a configurar:")
    for i, a in enumerate(ethernets, 1):
        st = "CONECTADO" if a["status"].lower() == "up" else "Desconectado"
        def_tag = " (Sugerido)" if i == default_idx else ""
        print(f"    {i}) {a['name']} [{st}] - {a['desc']}{def_tag}")

    while True:
        try:
            choice = input(f"  Opcion [{default_idx}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not choice:
            return ethernets[default_idx - 1]["name"]
        if choice.isdigit() and 1 <= int(choice) <= len(ethernets):
            return ethernets[int(choice) - 1]["name"]
        print("  Opcion invalida.")


# ----------------------------------------------------------------------------
# 5) Menú interactivo de Diagnóstico y Red
# ----------------------------------------------------------------------------
def interactive_network_menu(cfg=None):
    """Menú interactivo completo para diagnóstico y configuración de red."""
    _reconfigure()
    while True:
        diag = run_diagnosis(cfg)
        print_diagnosis(diag)

        print("  ACCIONES DISPONIBLES:")
        print("    1) Auto-configurar IP de la Laptop para Estacion MikroTik (10.100.0.100/16) [RECOMENDADO]")
        print("    2) Configurar IP para Flasheo Directo sin MikroTik (192.168.1.100/24)")
        print("    3) Restaurar adaptador a IP Automatica (DHCP)")
        print("    4) Personalizar IP estatica manualmente")
        print("    5) Re-ejecutar diagnostico de red")
        print("    6) Asistente de configuracion de Router MikroTik (API + IPs por puerto)")
        print("    0) Volver al menu principal")
        print()

        try:
            opt = input("  Seleccione una opcion [1/2/3/4/5/6/0]: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if opt == "1":
            ad_name = pick_ethernet_adapter(diag["adapters"])
            if ad_name:
                set_adapter_ip(ad_name, ip=DEFAULT_LAPTOP_IP, netmask=DEFAULT_LAPTOP_MASK)
                input("\n  Presione Enter para actualizar el diagnostico ...")
        elif opt == "2":
            ad_name = pick_ethernet_adapter(diag["adapters"])
            if ad_name:
                set_adapter_ip(ad_name, ip=DEFAULT_ONU_DIRECT_IP, netmask=DEFAULT_ONU_DIRECT_MASK)
                input("\n  Presione Enter para actualizar el diagnostico ...")
        elif opt == "3":
            ad_name = pick_ethernet_adapter(diag["adapters"])
            if ad_name:
                set_adapter_dhcp(ad_name)
                input("\n  Presione Enter para actualizar el diagnostico ...")
        elif opt == "4":
            ad_name = pick_ethernet_adapter(diag["adapters"])
            if ad_name:
                custom_ip = input(f"  Direccion IP [{DEFAULT_LAPTOP_IP}]: ").strip() or DEFAULT_LAPTOP_IP
                custom_mask = input(f"  Mascara de subred [{DEFAULT_LAPTOP_MASK}]: ").strip() or DEFAULT_LAPTOP_MASK
                set_adapter_ip(ad_name, ip=custom_ip, netmask=custom_mask)
                input("\n  Presione Enter para actualizar el diagnostico ...")
        elif opt == "5":
            continue
        elif opt == "6":
            import mikrotik as mtk
            from flasheo import setup_mikrotik
            setup_mikrotik()
            input("\n  Presione Enter para continuar ...")
        elif opt == "0":
            break
        else:
            print("  Opcion no valida.")


if __name__ == "__main__":
    interactive_network_menu()
