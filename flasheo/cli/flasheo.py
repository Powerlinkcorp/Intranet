#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
cli.flasheo — Lanzador interactivo por consola para la Estación de Flasheo de ONUs.
Soporta flasheo continuo, individual, masivo, diagnósticos, cambio de modelo y panel web.
"""
import os
import sys
import subprocess
import shutil

# Configuración de rutas modulares
CLI_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CLI_DIR) if os.path.basename(CLI_DIR) == "cli" else CLI_DIR
CORE_DIR = os.path.join(PROJECT_ROOT, "core")
WEB_DIR = os.path.join(PROJECT_ROOT, "web")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
FIRMWARES_DIR = os.path.join(PROJECT_ROOT, "firmwares")

for p in [PROJECT_ROOT, CORE_DIR, WEB_DIR, CLI_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import profiles
import web_station
import network_diag as netdiag

AUTOPILOT = os.path.join(CORE_DIR, "vsol_autopilot.py")
if not os.path.exists(AUTOPILOT):
    AUTOPILOT = os.path.join(PROJECT_ROOT, "vsol_autopilot.py")

CSV = os.path.join(CONFIG_DIR, "onus_list.csv")
if not os.path.exists(CSV):
    CSV = os.path.join(PROJECT_ROOT, "onus_list.csv")

DEFAULT_PARALLEL = 20


def info(msg):
    print(msg, flush=True)


def ok(msg):
    print(f"  OK   {msg}", flush=True)


def warn(msg):
    print(f"  AVISO {msg}", flush=True)


def fail(msg):
    print(f"  ERROR {msg}", flush=True)


def have_module(mod):
    try:
        __import__(mod)
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------------
# 1) Verificacion e instalacion de dependencias
# ----------------------------------------------------------------------------
def ensure_dependencies():
    info("\n" + "=" * 60)
    info("  PASO 1/3 :: Comprobando dependencias de Python")
    info("=" * 60)

    py = sys.executable

    # Comprobar playwright
    if not have_module("playwright"):
        warn("Libreria 'playwright' no instalada. Instalando ...")
        cmd = [py, "-m", "pip", "install", "--upgrade", "playwright"]
        res = subprocess.run(cmd)
        if res.returncode != 0:
            fail("No se pudo instalar playwright. Revisa tu conexion a internet.")
            sys.exit(1)
        ok("playwright instalado.")
    else:
        ok("Libreria 'playwright' detectada.")

    # Comprobar openpyxl
    if not have_module("openpyxl"):
        info("  Instalando openpyxl para exportacion Excel ...")
        subprocess.run([py, "-m", "pip", "install", "openpyxl"], stdout=subprocess.DEVNULL)

    # Comprobar librouteros
    if not have_module("librouteros"):
        info("  Instalando librouteros para integracion con MikroTik ...")
        subprocess.run([py, "-m", "pip", "install", "librouteros"], stdout=subprocess.DEVNULL)

    # Comprobar si Chromium esta descargado
    info("\n" + "=" * 60)
    info("  PASO 2/3 :: Comprobando navegador Chromium (headless)")
    info("=" * 60)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
        ok("Chromium esta instalado y funcional.")
    except Exception as ex:
        warn(f"Chromium no disponible ({ex}). Instalando con Playwright ...")
        info("  (Esto descarga ~150MB, se hace una sola vez)")
        cmd = [py, "-m", "playwright", "install", "chromium"]
        res = subprocess.run(cmd)
        if res.returncode != 0:
            fail("No se pudo instalar Chromium. Ejecuta manualmente: python -m playwright install chromium")
            sys.exit(1)
        ok("Chromium instalado exitosamente.")


# ----------------------------------------------------------------------------
# 2) Verificacion de archivos locales
# ----------------------------------------------------------------------------
def ensure_config():
    info("\n" + "=" * 60)
    info("  PASO 3/3 :: Verificando archivos de configuracion y firmware")
    info("=" * 60)

    active_prof = profiles.get_active_profile()
    fw_path = active_prof.get("firmware_path")

    if not fw_path or not os.path.exists(fw_path):
        fail(f"Firmware NO encontrado: {active_prof.get('firmware')}")
        info(f"   Coloca el archivo en la carpeta: {FIRMWARES_DIR}")
        sys.exit(1)
    else:
        size_mb = os.path.getsize(fw_path) / (1024 * 1024)
        ok(f"Firmware {active_prof.get('id')}: {os.path.basename(fw_path)} ({size_mb:.1f} MB)")

    if not os.path.exists(AUTOPILOT):
        fail(f"Script del autopilot no encontrado en: {AUTOPILOT}")
        sys.exit(1)
    else:
        ok(f"Motor Autopilot: core/vsol_autopilot.py")

    if not os.path.exists(CSV):
        warn(f"No existe {CSV}. Creando plantilla de ejemplo...")
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CSV, "w", encoding="utf-8") as f:
            f.write("puerto,ip,habilitada,comentario\n")
            f.write("1,10.100.1.1,si,ONU puerto 1\n")
            f.write("2,10.100.2.1,si,ONU puerto 2\n")
            f.write("3,10.100.3.1,si,ONU puerto 3\n")
            f.write("4,10.100.4.1,si,ONU puerto 4\n")
        ok("Plantilla creada en config/onus_list.csv.")
    else:
        ok(f"Lista de ONUs: config/onus_list.csv")


# ----------------------------------------------------------------------------
# 3) Diagnostico rapido de red
# ----------------------------------------------------------------------------
def quick_network_check():
    diag = netdiag.run_diagnosis()
    if not diag["all_ready"]:
        warn("Diagnostico de red detecto detalles que requieren atencion:")
        if not diag["connected_ethernets"]:
            warn("  * Cable Ethernet de la laptop desconectado.")
        if not diag["has_target_ip"]:
            warn("  * La laptop no tiene IP en el rango 10.100.0.0/16.")
            print("\n  ¿Deseas auto-configurar la IP estatica de la laptop (10.100.0.100/16)?")
            try:
                ans = input("  Configurar IP ahora [S/n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return
            if ans in ("", "s", "si", "y", "yes"):
                ad_name = netdiag.pick_ethernet_adapter(diag["adapters"])
                if ad_name:
                    netdiag.set_adapter_ip(ad_name, ip=netdiag.DEFAULT_LAPTOP_IP, netmask=netdiag.DEFAULT_LAPTOP_MASK)


def ask_mode():
    active_prof = profiles.get_active_profile()
    fw_name = os.path.basename(active_prof.get("firmware_path", ""))
    fw_size = active_prof.get("firmware_size_mb", 0)

    print()
    print("=" * 64)
    print(f"  ESTACION DE FLASHEO DE ONUs")
    print(f"  Modelo Activo: {active_prof.get('icon', '⚡')} {active_prof.get('name')} [{active_prof.get('hardware_type', 'ONU')}]")
    print(f"  Firmware:      {fw_name} ({fw_size} MB)")
    print("=" * 64)
    print("  Elija el modo de operacion:")
    print("    1) CONTINUO   - Monitorea y flashea automaticamente cada puerto (TUI)")
    print("    2) INDIVIDUAL - Flashea UNA ONU (192.168.1.1 directa o puerto 1..20)")
    print("    3) MASIVO     - Flashea todas las ONUs activas de config/onus_list.csv")
    print("    4) MIKROTIK   - Configura el Router Switch (API + IPs por puerto)")
    print("    5) RED / DIAG - Diagnostico de red laptop-mikrotik y cambio de IP")
    print("    6) WEB PANEL  - Abrir Servidor y Dashboard Web (http://localhost:8080)")
    print("    7) MODELO ONU - Cambiar Modelo de ONU y Firmware activo")
    print("    0) SALIR")
    while True:
        try:
            opt = input("\n  Opcion [1/2/3/4/5/6/7/0]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if opt == "1":
            return "continuo"
        if opt == "2":
            return "individual"
        if opt == "3":
            return "masivo"
        if opt == "4":
            return "mikrotik"
        if opt == "5":
            return "red"
        if opt == "6":
            return "web"
        if opt == "7":
            return "modelo"
        if opt == "0":
            return None
        warn("Opcion invalida. Use 1, 2, 3, 4, 5, 6, 7 o 0.")


def select_model_menu():
    print("\n" + "=" * 64)
    print("  SELECCION DE MODELO DE ONU Y FIRMWARE")
    print("=" * 64)
    models = profiles.get_models_list()
    for i, m in enumerate(models, 1):
        active_tag = "  --> [★ ACTIVO ACTUALMENTE]" if m["is_active"] else ""
        fw_status = f"✔ OK ({m['firmware_size_mb']} MB)" if m["firmware_exists"] else "✖ NO ENCONTRADO EN firmwares/"
        print(f"    {i}) {m.get('icon', '⚡')} {m['name']} [{m.get('hardware_type', 'ONU')}]{active_tag}")
        print(f"       Descripcion: {m.get('description', '')}")
        print(f"       Firmware:    {m['firmware']} [{fw_status}]")
        print(f"       Credenciales: Fabrica {m['default_user']}/{m['default_pass']} -> Final {m['final_user']}/{m['final_pass']}")
        print()
    print("    0) Cancelar / Volver")
    try:
        opt = input(f"  Seleccione modelo [1-{len(models)}/0]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if opt == "0" or not opt:
        return
    if opt.isdigit() and 1 <= int(opt) <= len(models):
        chosen = models[int(opt) - 1]
        ok_set, msg = profiles.set_active_model(chosen["id"])
        if ok_set:
            ok(f"Modelo activo cambiado a: {chosen['name']} ({chosen['id']})")
        else:
            fail(msg)
    else:
        warn("Opcion no valida.")


def ask_ip():
    print()
    print("=" * 60)
    print("  MODO INDIVIDUAL - Flashear una sola ONU")
    print("=" * 60)
    print("  Indica la IP o el numero de puerto de la ONU.")
    print("  Ejemplos:")
    print("    192.168.1.1   (conexion directa por Ethernet sin switch)")
    print("    11            (puerto 11 -> IP 10.100.11.1)")
    print("    10.100.3.1    (IP directa en el switch)")
    print()
    while True:
        try:
            val = input("  IP o puerto [192.168.1.1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not val:
            return "192.168.1.1"
        if val.isdigit():
            p = int(val)
            if 1 <= p <= 20:
                return f"10.100.{p}.1"
            else:
                warn("El puerto debe estar entre 1 y 20.")
                continue
        if "." in val:
            return val
        warn("Entrada no reconocida. Escribe un numero de puerto (1..20) o una IP.")


def setup_mikrotik():
    try:
        import mikrotik as mtk
    except ImportError:
        fail("No se pudo importar el modulo mikrotik.")
        return

    print("\n" + "=" * 60)
    print("  CONFIGURACION DEL ROUTER MIKROTIK")
    print("=" * 60)
    cfg = mtk.load_config() or {}
    host = input(f"  IP del MikroTik [{cfg.get('host', '10.100.0.1')}]: ").strip() or cfg.get("host", "10.100.0.1")
    user = input(f"  Usuario [{cfg.get('user', 'admin')}]: ").strip() or cfg.get("user", "admin")
    pwd = input(f"  Contrasena [{cfg.get('pass', '')}]: ").strip() or cfg.get("pass", "")
    port_str = input(f"  Puerto API [{cfg.get('port', 8728)}]: ").strip() or str(cfg.get("port", 8728))
    ports_max_str = input(f"  Cantidad de puertos [{cfg.get('max_port', 20)}]: ").strip() or str(cfg.get("max_port", 20))

    cfg_new = {
        "host": host,
        "user": user,
        "pass": pwd,
        "port": int(port_str),
        "max_port": int(ports_max_str),
        "iface_regex": "^(?:ether|vlan)(\\d+)$",
    }
    mtk.save_config(cfg_new)
    ok("Configuracion guardada en config/mikrotik_config.json.")

    print("\n  ¿Deseas aplicar la configuracion en el router ahora (crear IPs 10.100.N.1 y habilitar API)?")
    try:
        ans = input("  Aplicar configuracion [S/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if ans in ("", "s", "si", "y", "yes"):
        res = mtk.setup_router(cfg_new)
        if res:
            ok("Router configurado exitosamente.")
        else:
            fail("Hubo errores al configurar el router.")


# ----------------------------------------------------------------------------
# 4) Lanzamiento de modos
# ----------------------------------------------------------------------------
def run_mode(mode, target_ip=None):
    py = sys.executable
    active_prof = profiles.get_active_profile()
    model_id = active_prof.get("id", "V2801S-B")

    if mode == "continuo":
        try:
            from tui_flasheo import run_tui
            has_tui = True
        except Exception:
            has_tui = False

        if has_tui:
            info("\nIniciando Dashboard TUI interactivo en modo CONTINUO ...")
            run_tui(parallel=DEFAULT_PARALLEL, poll=10, final_first=True)
            return

        cmd = [
            py, "-u", AUTOPILOT,
            "--continuo",
            "--final-first",
            "--parallel", str(DEFAULT_PARALLEL),
            "--model", model_id,
        ]
        info(f"\nEjecutando: {' '.join(cmd)}\n")
        subprocess.run(cmd)

    elif mode == "individual":
        cmd = [
            py, "-u", AUTOPILOT,
            "--ip", target_ip,
            "--model", model_id,
        ]
        info(f"\nEjecutando: {' '.join(cmd)}\n")
        subprocess.run(cmd)

    elif mode == "masivo":
        cmd = [
            py, "-u", AUTOPILOT,
            "--mass",
            "--parallel", str(DEFAULT_PARALLEL),
            "--model", model_id,
        ]
        info(f"\nEjecutando: {' '.join(cmd)}\n")
        subprocess.run(cmd)

    elif mode == "mikrotik":
        setup_mikrotik()

    elif mode == "red":
        netdiag.interactive_network_menu()

    elif mode == "web":
        info("\nIniciando servidor web y panel dashboard en http://localhost:8080/ ...")
        web_station.run_web_server(port=8080, open_browser=True)


# ----------------------------------------------------------------------------
# 5) Flujo principal
# ----------------------------------------------------------------------------
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ensure_dependencies()
    ensure_config()
    quick_network_check()

    while True:
        mode = ask_mode()
        if mode is None:
            info("\nOperacion cancelada. Saliendo.")
            break
        elif mode == "individual":
            target = ask_ip()
            if target:
                run_mode("individual", target_ip=target)
        elif mode == "modelo":
            select_model_menu()
        else:
            run_mode(mode)


if __name__ == "__main__":
    main()
