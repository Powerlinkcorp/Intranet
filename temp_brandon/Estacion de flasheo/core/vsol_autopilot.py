#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSOL ONU Autopilot - V2804AX30-H / HG3232AXT-H (Powerlink branding)
=========================================================================
Automatiza de punta a punta el flasheo de firmware VSOL:

  1)  Espera de arranque de la ONU (el auto-reinicio normal al encender)
  2)  Login #1  (admin / stdONU101)
  3)  Cambio de contrasena  (admin123)  -> asistente
  4)  Enviar configuracion del asistente
  5)  Finalizar
  6)  Subida de firmware  (/boaform/web_form_upload_file.cgi) + monitoreo
  7)  Espera de reinicio post-actualizacion
  8)  Login #2  (admin / admin123)
  9)  Restablecimiento de fabrica  (onu_restore_factory_long.cgi) + cuenta regresiva
 10)  Espera de reinicio post-reset
 11)  Login #3  (Powerlink / Powerlink2026*)
 12)  Verificacion de VLAN 3  (1_TR069_INTERNET_R_VID_3)

Requisitos:
    pip install playwright
    python -m playwright install chromium

Uso (una ONU conectada por Ethernet):
    python vsol_autopilot.py

Uso masivo (varias ONUs via switch CRS326, paralelo):
    python vsol_autopilot.py --mass --parallel 2
    # edita onus_list.csv con IP/Puerto por ONU
    # --parallel N  procesa N ONUs simultaneas (default 2 en masivo; limitado
    #                por RAM del equipo, ~300-400MB por Chromium headless)

Opciones utiles:
    --ip 192.168.1.1     IP de la ONU (por defecto 192.168.1.1)
    --no-emoji           desactiva emojis (consolas antiguas)
    --headless           ejecuta sin ventana de navegador (modo masivo)
    --skip-wizard        omite el cambio de contrasena/asistente (ONU ya iniciada)
    --factory-reset-only solo hace login+factory reset+verificacion (sin firmware)
    --skip-firmware      omite la subida de firmware (ONU que ya lo tiene cargado)
    --no-stabilize       desactiva la espera del auto-reinicio del 1er arranque
    --parallel N         ONUs simultaneas en modo masivo (default 2)

El CAPTCHA del login es 100% generado en el navegador (canvas) y el servidor no
lo valida: este script lo desactiva interceptando la respuesta de
/boaform/wan_select_show.cgi (campo web_captcha="0"). Si el fabricante lo
cambiara a validacion real, el script lo detecta y te pide resolverlo a mano.
"""

import asyncio
import contextvars
import csv
import json
import os
import re
import sys
import time
import threading
from datetime import datetime

from playwright.async_api import async_playwright
import profiles

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CORE_DIR) if os.path.basename(CORE_DIR) == "core" else CORE_DIR
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "core") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "core"))

import profiles
try:
    import inventory_db
except Exception:
    inventory_db = None

BASE_DIR = PROJECT_ROOT
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
FIRMWARES_DIR = os.path.join(PROJECT_ROOT, "firmwares")
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(FIRMWARES_DIR, exist_ok=True)

DEFAULT_IP = "192.168.1.1"
CURRENT_BOX_CODE = None

# Cargar perfil activo por defecto
ACTIVE_PROFILE = profiles.get_active_profile()
FIRMWARE_PATH = ACTIVE_PROFILE.get("firmware_path", profiles.resolve_firmware_path("V2801D-B_all_V6.1.4-260805_powerlink_GPON.bin"))
LOG_CSV = os.path.join(LOGS_DIR, "registro_flasheo.csv")
LOG_XLSX = os.path.join(LOGS_DIR, "registro_flasheo.xlsx")
ONUS_LIST = os.path.join(CONFIG_DIR, "onus_list.csv")
if not os.path.exists(ONUS_LIST):
    ONUS_LIST = os.path.join(PROJECT_ROOT, "onus_list.csv")
SHOT_DIR = os.path.join(PROJECT_ROOT, "capturas")

# Credenciales del proceso
DEFAULT_USER = ACTIVE_PROFILE.get("default_user", "user")
DEFAULT_PASS = ACTIVE_PROFILE.get("default_pass", "user")
NEW_USER = ACTIVE_PROFILE.get("new_user", "admin")
NEW_PASS = ACTIVE_PROFILE.get("new_pass", "admin123")
FINAL_USER = ACTIVE_PROFILE.get("final_user", "Powerlink")
FINAL_PASS = ACTIVE_PROFILE.get("final_pass", "Powerlink2026*")

# Segundos a esperar cuando la ONU entra en cooldown de login
LOCKOUT_WAIT = 75

# Nombre / VLAN objetivo a verificar al final
TARGET_WAN_NAME = ACTIVE_PROFILE.get("target_wan_name", "1_TR069_INTERNET_R_VID_3")
TARGET_VLAN_ID = ACTIVE_PROFILE.get("target_vlan_id", "3")

# Endpoints detectados en el bundle JS de la ONU
EP_LOGIN = "/boaform/web_login_exe.cgi"
EP_CAPTCHA_CFG = "/boaform/web_custom_show.cgi"
EP_UPGRADE_STATUS = "/boaform/get_upgrade_status.cgi"
EP_UPLOAD = "/boaform/web_form_upload_file.cgi"
EP_WAN_SHOW = "/boaform/network_wan_show.cgi"
EP_FACTORY_RESET_LONG = "/boaform/onu_restore_factory_long.cgi"
EP_FACTORY_RESET_KEY = "/boaform/onu_restore_factory_key.cgi"
EP_DEVICE_RESET = "/boaform/device_reset.cgi"
EP_USER_SHOW = "/boaform/web_query_user_show.cgi"
EP_LOGOUT = "/boaform/web_logout_ext.cgi"
EP_DEVICE_BASIC = "/boaform/device_basic_show.cgi"

URL_UPGRADE = "/admin/management/software_upgrade/software_upgrade"
URL_CONFIG_RECOVERY = "/admin/management/device_management/configuration_recovery"
URL_WIZARD = "/wizard/user_config"
URL_FINISH = "/wizard/finish"

# ----------------------------------------------------------------------------
# Utilidades de terminal (emojis, colores, progreso)
# ----------------------------------------------------------------------------
EMOJI = {
    "onu": "\U0001F50C", "login": "\U0001F510", "key": "\U0001F511",
    "wizard": "\U0001F9D9", "upload": "\U0001F4E4", "gear": "\u2699",
    "ok": "\u2705", "fail": "\u274C", "warn": "\u26A0\uFE0F",
    "wait": "\u23F3", "reset": "\u267B\uFE0F", "check": "\U0001F50D",
    "vlan": "\U0001F4E1", "reboot": "\U0001F501", "finish": "\U0001F3C1",
    "info": "\u2139\uFE0F", "cpu": "\U0001F9E0", "flag": "\U0001F6A9",
}

USE_EMOJI = True
USE_COLOR = True


def _reconfigure():
    global USE_EMOJI
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    # Fallback si la consola no soporta emojis
    if os.name == "nt" and "WT_SESSION" not in os.environ and "TERM" not in os.environ:
        USE_EMOJI = False


_reconfigure()


def e(key):
    return EMOJI.get(key, "") if USE_EMOJI else ""


def color(text, code):
    if not USE_COLOR or os.name == "nt" and not os.environ.get("WT_SESSION"):
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


# Etiqueta por ONU (puerto) para salida legible en modo paralelo
CURRENT_TAG = contextvars.ContextVar("current_tag", default="")


def _tag():
    t = CURRENT_TAG.get()
    return color(f"[{t}] ", "1;35") if t else ""


def info(msg):
    print(color(f"[{datetime.now().strftime('%H:%M:%S')}]", "90") + " "
          + _tag() + msg)


def ok(msg):
    print(color(f"[{datetime.now().strftime('%H:%M:%S')}]", "90") + " "
          + _tag() + color("OK  ", "32") + msg)


def fail(msg):
    print(color(f"[{datetime.now().strftime('%H:%M:%S')}]", "90") + " "
          + _tag() + color("FAIL", "31") + " " + msg)


def warn(msg):
    print(color(f"[{datetime.now().strftime('%H:%M:%S')}]", "90") + " "
          + _tag() + color("WARN", "33") + " " + msg)


def phase(num, title):
    bar = color("=" * 40, "36")
    print("\n" + _tag() + bar)
    print(_tag() + color(f"FASE {num}", "1;36") + color(f" :: {title}", "1;37"))
    print(_tag() + bar)


def progress_bar(current, total, width=34, prefix="", suffix=""):
    pct = min(100.0, (current / total) * 100.0 if total else 100.0)
    filled = int(width * pct / 100)
    bar = "█" * filled + "░" * (width - filled)
    if CURRENT_TAG.get():
        # Modo paralelo: cada linea completa (sin \r, para no pisarse entre ONUs)
        print(_tag() + f"{prefix} [{bar}] {pct:5.1f}% {suffix}")
    else:
        sys.stdout.write(f"\r  {prefix} [{bar}] {pct:5.1f}% {suffix}")
        sys.stdout.flush()


def spinner_async(running, prefix=""):
    frames = ["|", "/", "-", "\\"]
    i = 0
    while running.is_set() is False:
        try:
            sys.stdout.write(f"\r  {frames[i % 4]} {prefix}")
            sys.stdout.flush()
            i += 1
            time.sleep(0.15)
        except Exception:
            break


async def wait_http(ip, timeout=120, quiet=False):
    """Espera a que el servidor HTTP de la ONU responda (estable)."""
    import urllib.request
    start = time.time()
    stable = 0
    while time.time() - start < timeout:
        try:
            # La ONU solo sirve la web si el header Host es su IP de gestion
            # (192.168.1.1); con otro Host responde 302 hacia conn-fail.html.
            req = urllib.request.Request(f"http://{ip}/", method="GET",
                                         headers={"Host": DEFAULT_IP,
                                                  "User-Agent": "Mozilla/5.0"})
            # urlopen en hilo para no bloquear el event loop (permite sondeos
            # simultaneos de muchos puertos en modo continuo).
            await asyncio.to_thread(urllib.request.urlopen, req, None, 4)
            stable += 1
            if stable >= 2:
                return True
        except Exception:
            stable = 0
        if not quiet:
            el = int(time.time() - start)
            if CURRENT_TAG.get():
                print(_tag() + f"{e('wait')} Esperando ONU {ip} ... {el}s")
            else:
                sys.stdout.write(f"\r  {e('wait')} Esperando ONU {ip} ... {el}s ")
                sys.stdout.flush()
        await asyncio.sleep(2)
    sys.stdout.write("\n")
    return False


async def wait_stable(ip, settle=45, timeout=420):
    """Espera a que la ONU termine su auto-reinicio del primer arranque.

    Al conectarse a la corriente, estas ONUs encienden, se reinician solas
    una vez y recien despues quedan estables. Si HTTP cae en algun momento
    (reinicio en curso), se reinicia la cuenta de estabilidad y se vuelve a
    esperar hasta que suba de nuevo.
    """
    info(f"{e('reboot')} Esperando estabilizacion (auto-reinicio del 1er arranque) ...")
    t0 = time.time()
    stable_since = None
    while time.time() - t0 < timeout:
        up = await wait_http(ip, timeout=8, quiet=True)
        now = time.time()
        if up:
            if stable_since is None:
                stable_since = now
            elif now - stable_since >= settle:
                info(f"{e('ok')} ONU estable ({settle}s continuos en linea).")
                return True
        else:
            if stable_since is not None:
                warn("Auto-reinicio detectado; esperando a que termine ...")
            stable_since = None
        await asyncio.sleep(3)
    fail("La ONU no se estabilizo a tiempo.")
    return False


# ----------------------------------------------------------------------------
# Utilidades CSV
# ----------------------------------------------------------------------------
MAC_RE = re.compile(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")


def _walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def _extract_device_data(obj):
    """Best-effort: (MAC, serial/PON) desde el JSON de device_basic_show.cgi.
    Devuelve la MAC de lan_info_list (Table_lan1_3_mac_table) y el serial del
    device_base_list (devicenumber); si faltan, busca cualquier MAC/SN valido."""
    mac = ""
    pon = ""
    for k, v in _walk(obj):
        if k == "Table_lan1_3_mac_table" and isinstance(v, str) \
                and v.lower() not in ("none", "", "n/a"):
            mac = v.upper()
            break
    for k, v in _walk(obj):
        if k == "devicenumber" and isinstance(v, str) and v:
            pon = v
            break
    if not mac:
        for k, v in _walk(obj):
            if isinstance(v, str) and MAC_RE.search(v):
                mac = v.upper()
                break
def format_vsol_pon(pon, mac=""):
    """Convierte el PON o número de serie (ej: 4c46d1-4c46d1e3e021) al formato estándar GPON SN:
    VSOL + 00 + últimos 6 dígitos hexadecimales (ej: VSOL00E3E021)."""
    if pon:
        p = str(pon).strip()
        if "-" in p:
            tail = p.split("-")[-1]
            if len(tail) >= 6:
                return "VSOL00" + tail[-6:].upper()
        elif len(p) >= 6:
            return "VSOL00" + p[-6:].upper()
    if mac:
        mc = re.sub(r"[^0-9A-Fa-f]", "", str(mac))
        if len(mc) >= 6:
            return "VSOL00" + mc[-6:].upper()
    return ""


def log_result(puerto, ip, resultado, vlan, detalles, mac="", pon="", duracion_seg=0, captura=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pon_formateado = format_vsol_pon(pon, mac)
    file_exists = os.path.exists(LOG_CSV)
    if not file_exists:
        with open(LOG_CSV, "w", encoding="utf-8") as f:
            f.write("FechaHora,Puerto/ID,IP,MAC,PON/Serial,PON Formateado,Resultado,VLAN3 Verificada,Detalles\n")
    else:
        _migrate_log_csv()
    with open(LOG_CSV, "a", encoding="utf-8") as f:
        safe = str(detalles).replace(",", ";").replace("\n", " ")
        f.write(f"{timestamp},{puerto},{ip},{mac},{pon},{pon_formateado},{resultado},{vlan},{safe}\n")
    _append_xlsx(timestamp, puerto, ip, mac, pon, pon_formateado, resultado, vlan, detalles)

    try:
        from core import database
        model_id = ACTIVE_PROFILE.get("id", "V2801S-B")
        fw_name = os.path.basename(FIRMWARE_PATH) if FIRMWARE_PATH else ""
        database.log_onu_flash(
            mac=mac,
            pon_original=pon,
            pon_sn=pon_formateado,
            modelo_id=model_id,
            resultado=resultado,
            vlan3_ok=vlan,
            firmware=fw_name,
            puerto=str(puerto),
            ip=str(ip),
            detalles=str(detalles),
            duracion_seg=duracion_seg or 0,
            captura_path=captura or "",
        )
    except Exception as ex_db:
        print(f"  [DB] Error registrando en base de datos ORM: {ex_db}")

    if inventory_db:
        try:
            model_id = ACTIVE_PROFILE.get("id", "V2801S-B")
            fw_name = os.path.basename(FIRMWARE_PATH) if FIRMWARE_PATH else ""
            inventory_db.registrar_onu(
                modelo_id=model_id,
                pon=pon,
                mac=mac,
                puerto=puerto,
                ip=ip,
                resultado=resultado,
                vlan_ok=vlan,
                detalles=detalles,
                codigo_caja=CURRENT_BOX_CODE,
                firmware=fw_name,
                duracion_segundos=duracion_seg,
                captura_path=captura,
                fecha_hora=timestamp
            )
        except Exception as ex_db:
            print(f"  [DB] Error registrando en base de datos: {ex_db}")


XLSX_COLS = ["FechaHora", "Puerto/ID", "IP", "MAC", "PON/Serial",
             "PON Formateado", "Resultado", "VLAN3 Verificada", "Detalles"]


def _append_xlsx(timestamp, puerto, ip, mac, pon, pon_formateado, resultado, vlan, detalles):
    """Registro en Excel real (.xlsx): cada campo en su propia columna/celda.
    Crea el archivo si no existe (volcando las filas ya presentes en el CSV) y
    agrega la fila nueva. Nunca lanza."""
    try:
        from openpyxl import load_workbook, Workbook
        path = LOG_XLSX
        if not os.path.exists(path):
            wb = Workbook()
            ws = wb.active
            ws.title = "Registro"
            ws.append(XLSX_COLS)
            try:
                with open(LOG_CSV, "r", encoding="utf-8-sig") as f:
                    for r in csv.DictReader(f):
                        p_orig = r.get("PON/Serial", "")
                        p_form = r.get("PON Formateado") or format_vsol_pon(p_orig, r.get("MAC", ""))
                        ws.append([r.get("FechaHora", ""), r.get("Puerto/ID", ""),
                                   r.get("IP", ""), r.get("MAC", ""),
                                   p_orig, p_form, r.get("Resultado", ""),
                                   r.get("VLAN3 Verificada", ""), r.get("Detalles", "")])
            except Exception:
                pass
        else:
            wb = load_workbook(path)
            ws = wb.active
        try:
            ts = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        except Exception:
            ts = timestamp
        ws.append([ts, puerto, ip, mac, pon, pon_formateado, resultado, vlan, str(detalles)])
        for row in ws.iter_rows(min_col=1, max_col=1):
            for cell in row:
                if isinstance(cell.value, datetime):
                    cell.number_format = "DD/MM/YYYY HH:MM:SS"
        wb.save(path)
    except Exception:
        pass


def _migrate_log_csv():
    """Convierte un CSV con el header antiguo
    al nuevo insertando la columna PON Formateado."""
    try:
        with open(LOG_CSV, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
        if not lines or lines[0].strip().startswith("FechaHora,Puerto/ID,IP,MAC,PON/Serial,PON Formateado"):
            return
        with open(LOG_CSV, "w", encoding="utf-8") as f:
            f.write("FechaHora,Puerto/ID,IP,MAC,PON/Serial,PON Formateado,Resultado,VLAN3 Verificada,Detalles\n")
            for ln in lines[1:]:
                if not ln.strip():
                    continue
                fields = ln.rstrip("\n").split(",")
                if len(fields) >= 8:
                    mac_v = fields[3]
                    pon_v = fields[4]
                    f_pon = format_vsol_pon(pon_v, mac_v)
                    rest = ",".join(fields[5:])
                    f.write(f"{fields[0]},{fields[1]},{fields[2]},{mac_v},{pon_v},{f_pon},{rest}\n")
                elif len(fields) >= 6:
                    f.write(f"{fields[0]},{fields[1]},{fields[2]},,,,{fields[3]},{fields[4]},{','.join(fields[5:])}\n")
                else:
                    f.write(ln)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Estado en vivo (JSON compartido) para la interfaz TUI de seguimiento
# ----------------------------------------------------------------------------
STATUS_FILE = os.path.join(LOGS_DIR, "estado.json")
STATUS_DATA = {"onus": [], "total": 0, "procesadas": 0, "en_curso": 0}
STATUS_LOCK = threading.Lock()


def _write_status():
    try:
        tmp = STATUS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(STATUS_DATA, f, ensure_ascii=False)
        os.replace(tmp, STATUS_FILE)
    except Exception:
        pass


def reset_status(total=0):
    global STATUS_DATA
    STATUS_DATA = {"onus": [], "total": total, "procesadas": 0, "en_curso": 0}
    _write_status()


def _set_status(puerto, **kw):
    global STATUS_DATA
    with STATUS_LOCK:
        for o in STATUS_DATA["onus"]:
            if o.get("puerto") == puerto:
                if kw.get("estado") and kw.get("estado") != o.get("estado"):
                    kw["desde"] = time.time()
                pon_val = kw.get("pon") or o.get("pon")
                mac_val = kw.get("mac") or o.get("mac")
                if pon_val or mac_val:
                    kw.setdefault("pon_formateado", format_vsol_pon(pon_val, mac_val))
                o.update(kw)
                break
        else:
            o = {"puerto": puerto}
            if kw.get("estado"):
                kw["desde"] = time.time()
            pon_val = kw.get("pon")
            mac_val = kw.get("mac")
            if pon_val or mac_val:
                kw["pon_formateado"] = format_vsol_pon(pon_val, mac_val)
            o.update(kw)
            STATUS_DATA["onus"].append(o)
        if kw.get("final"):
            STATUS_DATA["procesadas"] = sum(
                1 for x in STATUS_DATA["onus"] if x.get("final"))
        _write_status()


def load_onus():
    if not os.path.exists(ONUS_LIST):
        return []
    onus = []
    with open(ONUS_LIST, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ip = (row.get("IP") or "").strip()
            if ip and not ip.startswith("#"):
                onus.append({
                    "ip": ip,
                    "user": (row.get("Username") or "").strip() or DEFAULT_USER,
                    "pass": (row.get("Password") or "").strip() or DEFAULT_PASS,
                    "puerto": (row.get("Puerto") or "").strip() or "?",
                    "final_user": (row.get("FinalUser") or "").strip() or FINAL_USER,
                    "final_pass": (row.get("FinalPass") or "").strip() or FINAL_PASS,
                })
    return onus


# ----------------------------------------------------------------------------
# Automatizacion Playwright
# ----------------------------------------------------------------------------
class VSOLAutopilot:
    def __init__(self, ip, browser, context, headless):
        self.ip = ip
        self.browser = browser
        self.context = context
        self.headless = headless
        self.page = None

    # --- helpers de red ---
    async def api_get(self, path):
        resp = await self.page.request.get(f"http://{self.ip}{path}",
                                           headers={"Host": DEFAULT_IP},
                                           timeout=15000)
        if resp.status == 200:
            return await resp.json()
        return None

    async def api_post(self, path, data=None):
        resp = await self.page.request.post(f"http://{self.ip}{path}",
                                            headers={"Host": DEFAULT_IP},
                                            data=data, timeout=15000)
        if resp.status == 200:
            try:
                return await resp.json()
            except Exception:
                return None
        return None

    async def get_device_info(self):
        """Best-effort: (mac, pon) de la ONU via device_basic_show.cgi.
        Requiere sesion activa (se llama tras login). Nunca lanza."""
        try:
            resp = await self.api_get(EP_DEVICE_BASIC)
            if not resp:
                return {"mac": "", "pon": ""}
            mac, pon = _extract_device_data(resp)
            return {"mac": mac, "pon": pon}
        except Exception:
            return {"mac": "", "pon": ""}

    # --- login ---
    async def login(self, user, password, attempt_label=""):
        tag = f" {attempt_label}" if attempt_label else ""
        try:
            await self.page.goto(f"http://{self.ip}/", timeout=30000)
        except Exception:
            await wait_http(self.ip, timeout=60)
            await self.page.goto(f"http://{self.ip}/", timeout=30000)

        # 0. Comprobar si ya está dentro del dashboard o asistente (sesión activa)
        await asyncio.sleep(1)
        cur_url = self.page.url.lower()
        if "/dashboard" in cur_url or "/overview" in cur_url or "/wizard" in cur_url:
            if "/wizard" in cur_url:
                return "firstBoot"
            return "auth"
        if await self.page.locator("button:has-text('Cerrar sesión'), button:has-text('Logout'), button:has-text('Panel de configuración')").count() > 0:
            return "auth"

        # 1. Comprobar si es formulario clásico (VSOL V2801S-B / ZTE / Realtek)
        is_classic_form = False
        try:
            if await self.page.locator("#Frm_Username, input[name='Username']").count() > 0:
                is_classic_form = True
        except Exception:
            is_classic_form = False
        self.is_classic_form = is_classic_form

        if is_classic_form:
            info(f"{e('login')} Formulario clásico detectado (V2801). Iniciando sesión con {user}/{password}{tag} ...")
            user_input = self.page.locator("#Frm_Username, input[name='Username']").first
            pass_input = self.page.locator("#Frm_Password, input[name='Password']").first
            await user_input.fill(user)
            await pass_input.fill(password)

            # Captcha / IdentCode automático si existe
            if await self.page.locator("#Frm_IdentCode").count() > 0:
                try:
                    code = await self.page.evaluate("""() => {
                        if (!window.code || window.code.length !== 4) {
                            if (typeof createCode === 'function') createCode();
                        }
                        return window.code || (document.getElementById('checkCode') ? document.getElementById('checkCode').value : '');
                    }""")
                    if code:
                        await self.page.locator("#Frm_IdentCode").fill(code)
                except Exception:
                    pass

            login_btn = self.page.locator("#LoginId, input[type='submit'][value*='Login'], button[type='submit']").first
            try:
                await login_btn.click()
            except Exception:
                try:
                    await self.page.evaluate("dosubmit()")
                except Exception:
                    pass

            waited = 0
            while waited < 15:
                await asyncio.sleep(1)
                waited += 1
                try:
                    errmsg = await self.page.locator("#errmsg").text_content()
                    if errmsg:
                        if "three times" in errmsg.lower() or "minute later" in errmsg.lower():
                            fail("ONU en cooldown de login (bloqueo temporal 60s). Se reintentara tras una espera ...")
                            return "lockout"
                        elif "wrong" in errmsg.lower() or "error" in errmsg.lower():
                            return None
                except Exception:
                    pass

                # Verificar si ya entró al dashboard o cambió de página
                url = self.page.url
                if "/login" not in url.lower() and await user_input.count() == 0:
                    return "auth"

            # Check final
            if await user_input.count() == 0:
                return "auth"
            return None

        # 2. Formulario moderno Vue SPA (V2804AX30-H)
        form = self.page.locator("form.login-form")
        try:
            await form.locator("input[type='text']").first.wait_for(timeout=10000)
        except Exception:
            # Re-verificar si la página navegó al dashboard durante la espera
            cur_url = self.page.url.lower()
            if "/dashboard" in cur_url or "/overview" in cur_url:
                return "auth"
            if await self.page.locator("button:has-text('Cerrar sesión'), button:has-text('Logout')").count() > 0:
                return "auth"

            # Sesion residual activa (la ONU redirige a dashboard sin login).
            # Fuerza logout y recarga para ver el formulario limpio.
            warn("Sesion activa o formulario no visible; verificando estado ...")
            try:
                await self.page.request.get(
                    f"http://{self.ip}{EP_LOGOUT}",
                    headers={"Host": DEFAULT_IP}, timeout=5000)
            except Exception:
                pass
            try:
                await self.page.goto(f"http://{self.ip}/", timeout=15000)
            except Exception:
                pass
            try:
                await form.locator("input[type='text']").first.wait_for(timeout=8000)
            except Exception:
                pass
            if "/dashboard" in self.page.url.lower() or await form.count() == 0:
                info("Sin formulario de acceso tras logout: se asume sesion activa.")
                return "auth"

        try:
            await form.locator("input[type='text']").first.fill(user)
            await form.locator("input[type='password']").first.fill(password)
        except Exception:
            if "/dashboard" in self.page.url.lower() or await self.page.locator("button:has-text('Cerrar sesión')").count() > 0:
                return "auth"

        # Si el captcha aparece (por si el bypass fallo), lo resolvemos
        try:
            captcha_input = form.locator("input").nth(2) if await form.locator("input").count() > 2 else None
            if captcha_input and not await self._try_autofill_captcha(form):
                if getattr(self, "headless", False):
                    warn("Captcha presente en modo headless; reintentando sin captcha ...")
                else:
                    warn("Captcha presente. Escribelo en la ventana del navegador y pulsa Enter aqui.")
                    try:
                        input("   > Presiona ENTER cuando hayas resuelto el captcha...")
                    except EOFError:
                        warn("No hay terminal interactiva; reintentando sin captcha ...")
        except Exception:
            pass

        btn = form.locator("button, input[type='submit'], .el-button--primary, .login-btn")
        btn_ready = False
        try:
            await btn.first.wait_for(state="visible", timeout=8000)
            btn_ready = True
        except Exception:
            cur_url = self.page.url.lower()
            if "/dashboard" in cur_url or "/overview" in cur_url or await self.page.locator("button:has-text('Cerrar sesión')").count() > 0:
                return "auth"
            btn = self.page.locator("button:has-text('Login'), button:has-text('Iniciar'), .login-btn")
            if await btn.count() > 0:
                btn_ready = True

        if not btn_ready and ("/dashboard" in self.page.url.lower() or await form.count() == 0):
            return "auth"

        # Deteccion robusta del resultado del login
        login_seen = {"v": False}
        login_success = {"v": False}
        login_result = {"v": None}

        async def _on_login(resp):
            if EP_LOGIN in resp.url:
                login_seen["v"] = True
                try:
                    t = await resp.text()
                    login_success["v"] = "success" in t.lower()
                    try:
                        login_result["v"] = json.loads(t)["data"]["result"]
                    except Exception:
                        login_result["v"] = None
                except Exception:
                    pass

        self.page.on("response", _on_login)
        try:
            await btn.first.click()
        except Exception:
            pass
        info(f"{e('login')} Iniciando sesion con {user}/{password}{tag} ...")

        try:
            # Esperar a que salga del login (wizard / dashboard)
            waited = 0
            while waited < 30:
                await asyncio.sleep(1)
                waited += 1
                if login_success["v"]:
                    try:
                        if "wizard" in self.page.url:
                            return "firstBoot"
                    except Exception:
                        pass
                    return "auth"
                try:
                    url = self.page.url
                    if "/login" not in url:
                        if "wizard" in url:
                            return "firstBoot"
                        return "auth"
                except Exception:
                    pass
                # Algunos firmwares dejan la URL en /login aunque la sesion se crea:
                # el SPA quita el formulario del login al entrar al dashboard.
                try:
                    if await form.count() == 0:
                        return "auth"
                except Exception:
                    pass
                # La ONU respondio el login sin exito: credenciales incorrectas.
                if login_seen["v"] and waited >= 10:
                    res = login_result["v"]
                    if res and "three_error_login" in str(res).lower():
                        # Cooldown de login de la ONU (tras demasiados intentos
                        # fallidos bloquea temporalmente hasta credenciales
                        # correctas). La credencial puede ser correcta: NO marcar
                        # como fallo definitivo; avisar para reintentar tras espera.
                        fail("ONU en cooldown de login (three_error_login). "
                             "Se reintentara esta credencial tras una espera ...")
                        return "lockout"
                    fail("Login rechazado por la ONU (credenciales incorrectas).")
                    return None
                # Umbral generoso (la ONU bajo carga puede tardar >8s)
                if waited >= 20:
                    try:
                        err = await self.page.locator(".el-message").all_text_contents()
                        if err:
                            fail(f"Login rechazado: {' | '.join(err)}")
                            return None
                        if await form.count() > 0 and "/login" in self.page.url:
                            fail("Login no completado (sigue en la pantalla de acceso).")
                            return None
                    except Exception:
                        pass
            fail("No se detecto redireccion tras el login")
            return None
        finally:
            self.page.remove_listener("response", _on_login)

    async def wait_cooldown(self):
        """Espera de forma inteligente a que expire el bloqueo temporal de la ONU."""
        try:
            time_el = self.page.locator("#time")
            if await time_el.count() > 0:
                txt = (await time_el.text_content() or "").strip()
                import re
                m = re.search(r"(\d+)", txt)
                secs = int(m.group(1)) if m else 60
                warn(f"ONU en bloqueo temporal: esperando {secs + 3}s para que expire el contador...")
                await asyncio.sleep(secs + 3)
            else:
                warn(f"Esperando {LOCKOUT_WAIT}s para liberar el bloqueo temporal de la ONU...")
                await asyncio.sleep(LOCKOUT_WAIT)
            # Refrescar página para resetear el formulario limpio
            await self.page.goto(f"http://{self.ip}/", timeout=15000)
            await asyncio.sleep(1)
        except Exception:
            await asyncio.sleep(65)

    async def _try_autofill_captcha(self, form):
        """Intenta leer el codigo captcha (generado en el navegador) y rellenarlo."""
        try:
            code = await self.page.evaluate("""
                () => {
                    const canvas = document.getElementById('s-canvas');
                    if (!canvas) return null;
                    let el = canvas;
                    while (el && !el.__vueParentComponent) el = el.parentElement;
                    const comp = el && el.__vueParentComponent;
                    if (!comp || !comp.setupState) return null;
                    const ref = comp.setupState.o;
                    return (ref && typeof ref.value === 'string') ? ref.value : null;
                }
            """)
            if code:
                await form.locator("input").nth(2).fill(code)
                return True
        except Exception:
            pass
        return False

    # --- wizard: cambio de contrasena ---
    async def run_wizard(self, new_password):
        phase(2, "Cambio de contrasena y asistente")
        info(f"{e('wizard')} Navegando al asistente de primer arranque ...")
        try:
            await self.page.goto(f"http://{self.ip}{URL_WIZARD}", timeout=30000)
        except Exception:
            await wait_http(self.ip, timeout=60)
            await self.page.goto(f"http://{self.ip}{URL_WIZARD}", timeout=30000)
        await asyncio.sleep(2)

        pwd_inputs = self.page.locator("input[type='password']")
        await pwd_inputs.first.wait_for(timeout=20000)
        cnt = await pwd_inputs.count()
        if cnt >= 2:
            for i in range(2):
                await pwd_inputs.nth(i).fill(new_password)
            ok(f"{e('key')} Contrasena nueva aplicada en ambos campos: {new_password}")
        else:
            warn("No se encontraron 2 campos de contrasena; verificando si ya estaba configurado...")
            return "skip"

        # Boton Siguiente (action-next)
        nxt = self.page.locator("button.action-next")
        try:
            await nxt.wait_for(timeout=10000)
            await nxt.click()
            info(f"{e('wizard')} Paso 'Siguiente' completado.")
        except Exception:
            pass

        # Boton Enviar (action-submit)
        sub = self.page.locator("button.action-submit")
        try:
            await sub.wait_for(timeout=15000)
            await sub.click()
            ok(f"{e('wizard')} Configuracion del asistente ENVIADA.")
        except Exception as ex:
            warn(f"No aparecio el boton Enviar: {ex}")

        # Pagina de finalizacion
        await asyncio.sleep(3)
        try:
            await self.page.goto(f"http://{self.ip}{URL_FINISH}", timeout=15000)
            await asyncio.sleep(2)
        except Exception:
            pass

        fin = self.page.locator("button:has-text('Finish'), button:has-text('Finalizar')")
        try:
            await fin.first.wait_for(timeout=15000)
            await fin.first.click()
            ok(f"{e('finish')} Asistente finalizado -> dashboard.")
        except Exception:
            warn("No se encontro el boton Finalizar; continuando de todos modos.")

        try:
            await self.page.goto(f"http://{self.ip}/", timeout=15000)
            await asyncio.sleep(3)
        except Exception:
            pass
        return "done"

    # --- navegacion a pagina de actualizacion ---
    async def goto_upgrade(self):
        info(f"{e('gear')} Navegando a Actualizacion de Software ...")
        arch = ACTIVE_PROFILE.get("arch", "realtek_boa")
        upgrade_page = ACTIVE_PROFILE.get("upgrade_page")

        # Arquitectura Cortina / ZTE GHTML (V2801S-B / V2801D-B)
        if arch == "zte_cortina" or getattr(self, "is_classic_form", False) or (upgrade_page and ".gch" in upgrade_page):
            target_url = upgrade_page or "/getpage.gch?pid=1002&nextpage=manager_dev_version_t.gch"
            try:
                await self.page.goto(f"http://{self.ip}{target_url}", timeout=20000)
                await self.page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2)
                if await self.page.locator("#VersionUpload, input[name='VersionUpload']").count() > 0:
                    ok("Página de actualización de firmware Cortina cargada exitosamente.")
                    return True
            except Exception as ex:
                warn(f"Navegación directa a {target_url} falló: {ex}")

            # Fallback por menús en interfaz clásica
            try:
                for sel in ["#mmManager", "text='Administration'", "text='Administración'", "text='Gerenciamento'"]:
                    el = self.page.locator(sel).first
                    if await el.count() > 0:
                        await el.click()
                        await asyncio.sleep(1)
                        break
                for sel in ["#smDevVer", "text='Software Management'", "text='Version Management'", "text='Firmware'"]:
                    el = self.page.locator(sel).first
                    if await el.count() > 0:
                        await el.click()
                        await asyncio.sleep(1)
                        return True
            except Exception:
                pass
            return True

        # Arquitectura Realtek Boa / Vue SPA
        try:
            await self.page.goto(f"http://{self.ip}{URL_UPGRADE}", timeout=15000)
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            return True
        except Exception:
            # Fallback: navegar por menu lateral
            info("Navegacion directa fallo; usando el menu lateral ...")
            try:
                await self.page.goto(f"http://{self.ip}/", timeout=15000)
                await asyncio.sleep(2)
                for lbl in ["Panel de Configuracion", "Gestion",
                            "Actualizacion de software", "Actualización de software"]:
                    el = self.page.locator(f".el-menu >> text='{lbl}'")
                    if await el.count():
                        await el.first.click()
                        await asyncio.sleep(1)
                return True
            except Exception as ex:
                fail(f"No se pudo llegar a la pagina de actualizacion: {ex}")
                return False

    # --- subida de firmware + monitoreo ---
    async def upload_firmware(self, fw_path):
        if not os.path.exists(fw_path):
            raise FileNotFoundError(f"Firmware no encontrado: {fw_path}")
        size_mb = os.path.getsize(fw_path) / (1024 * 1024)
        info(f"{e('upload')} Firmware: {os.path.basename(fw_path)} ({size_mb:.1f} MB)")

        arch = ACTIVE_PROFILE.get("arch", "realtek_boa")
        is_cortina = (arch == "zte_cortina" or 
                      getattr(self, "is_classic_form", False) or 
                      await self.page.locator("#VersionUpload, input[name='VersionUpload']").count() > 0)

        if is_cortina:
            return await self._upload_firmware_cortina(fw_path, size_mb)
        else:
            return await self._upload_firmware_realtek(fw_path, size_mb)

    async def _upload_firmware_cortina(self, fw_path, size_mb):
        info(f"{e('upload')} [Cortina] Subiendo firmware mediante manager_dev_version_t.gch ...")

        file_input = self.page.locator("#VersionUpload, input[name='VersionUpload'], input[type='file']").first
        if await file_input.count() == 0:
            await self.goto_upgrade()
            file_input = self.page.locator("#VersionUpload, input[name='VersionUpload'], input[type='file']").first

        if await file_input.count() == 0:
            fail("[Cortina] No se encontró el campo de archivo (#VersionUpload) en la página de actualización.")
            return False

        # Configurar escucha de diálogos (alert / confirm / msgbox)
        self.page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

        # Asignar archivo al input
        info(f"{e('upload')} [Cortina] Cargando archivo binario en el formulario web...")
        await file_input.set_input_files(fw_path)
        await asyncio.sleep(1)

        # Enviar formulario ejecutando msgCallback()
        info(f"{e('upload')} [Cortina] Ejecutando envío y confirmación de actualización...")
        submitted = False
        try:
            res_eval = await self.page.evaluate("""() => {
                if (typeof msgCallback === 'function') {
                    msgCallback();
                    return 'msgCallback';
                }
                if (document.fUpload && typeof document.fUpload.submit === 'function') {
                    document.fUpload.submit();
                    return 'fUpload.submit';
                }
                return false;
            }""")
            if res_eval:
                submitted = True
                ok(f"{e('upload')} [Cortina] Envío iniciado exitosamente ({res_eval}).")
        except Exception as ex_sub:
            warn(f"[Cortina] Aviso al invocar JS: {ex_sub}")

        if not submitted:
            btn = self.page.locator("input[type='button'][onclick*='myUploadFile'], #upload, input[value*='Upload'], input[value*='Actualizar']").first
            if await btn.count() > 0:
                await btn.click()
                submitted = True
                ok(f"{e('upload')} [Cortina] Envío activado vía botón de subida.")

        # Monitorear escritura en memoria flash y posterior reinicio
        phase(3, "Monitoreo de actualización y reinicio Cortina (V2801)")
        t0 = time.time()
        max_wait = 210  # 3.5 minutos
        reboot_seen = False

        # Progreso inicial mientras el navegador sube los bytes
        for step in range(1, 15):
            await asyncio.sleep(2)
            progress_bar(step, 40, prefix=f"{e('cpu')} Transfiriendo y Grabando Flash", suffix=f"{int(time.time() - t0)}s")

        while time.time() - t0 < max_wait:
            await asyncio.sleep(3)
            elapsed = int(time.time() - t0)
            up = await wait_http(self.ip, timeout=4, quiet=True)

            if not up:
                reboot_seen = True
                progress_bar(25, 40, prefix=f"{e('reboot')} Reiniciando", suffix=f"APLICANDO FIRMWARE ({elapsed}s)")
            elif up and reboot_seen:
                progress_bar(40, 40, prefix=f"{e('ok')} Completado", suffix=f"ONU EN LÍNEA ({elapsed}s)")
                sys.stdout.write("\n")
                ok(f"{e('ok')} Firmware aplicado exitosamente (reinicio completado en {elapsed}s).")
                return True
            else:
                progress_bar(min(38, 15 + int(elapsed / 6)), 40, prefix=f"{e('cpu')} Monitoreando", suffix=f"({elapsed}s)")

        if await wait_http(self.ip, timeout=8, quiet=True):
            ok(f"{e('ok')} ONU responde tras actualización ({int(time.time() - t0)}s).")
            return True
        fail("Tiempo de espera agotado durante el flasheo de la ONU.")
        return False

    async def _upload_firmware_realtek(self, fw_path, size_mb):
        with open(fw_path, "rb") as f:
            fw_bytes = f.read()
        info(f"{e('upload')} Enviando archivo a la ONU ({size_mb:.1f} MB) ...")
        resp = await self.page.request.post(
            f"http://{self.ip}{EP_UPLOAD}",
            headers={"Host": DEFAULT_IP},
            multipart={"file": {"name": os.path.basename(fw_path),
                                "mimeType": "application/octet-stream",
                                "buffer": fw_bytes}},
            timeout=300000,
        )
        try:
            js = await resp.json()
        except Exception:
            js = {}
        result = (js or {}).get("data", {}).get("result") or (js or {}).get("result")
        if result == "file_upload_over":
            ok(f"{e('upload')} Firmware recibido por la ONU (upload completo).")
        elif result == "filesize_error":
            fail("La ONU rechazo el archivo: error de tamano (filesize_error).")
            return False
        elif result == "fileopenfaild":
            fail("La ONU no pudo abrir el archivo (fileopenfaild).")
            return False
        elif result == "upgrade_ing":
            warn("La ONU ya estaba actualizando (upgrade_ing); monitoreando ...")
        else:
            warn(f"Respuesta inesperada del upload (HTTP {resp.status}): {result}")

        # Monitoreo del estado de actualizacion Realtek
        phase(3, "Monitoreo de actualizacion de firmware")
        status_map = {"0": "en espera", "1": "aplicando firmware",
                      "2": "completado (reiniciando)", "3": "fallo"}
        max_polls = 80  # el JS usa 80 * 3s = 240s
        t0 = time.time()
        reboot_seen = False
        err_count = 0
        for i in range(max_polls):
            await asyncio.sleep(3)
            elapsed = time.time() - t0

            # Detectar reinicio de la ONU
            up = await wait_http(self.ip, timeout=8, quiet=True)
            if up and reboot_seen:
                progress_bar(max_polls, max_polls,
                             prefix=f"{e('cpu')} Actualizando",
                             suffix="REINICIO DETECTADO - COMPLETADO")
                sys.stdout.write("\n")
                ok(f"{e('ok')} Firmware aplicado (la ONU reinicio sola, {int(elapsed)}s).")
                return True

            session_lost = False
            try:
                if "/login" in self.page.url or \
                        await self.page.locator("form.login-form").count() > 0:
                    session_lost = True
            except Exception:
                session_lost = False
            if up and session_lost:
                progress_bar(max_polls, max_polls,
                             prefix=f"{e('cpu')} Actualizando",
                             suffix="LOGIN DETECTADO (REINICIO) - COMPLETADO")
                sys.stdout.write("\n")
                ok(f"{e('ok')} Firmware aplicado (equipo ya en login Powerlink, "
                   f"{int(elapsed)}s).")
                return True

            data = None
            try:
                data = await self.api_get(EP_UPGRADE_STATUS)
            except Exception:
                data = None
            st = (data or {}).get("data", {}).get("UpgradeStatus") if data else None
            txt = status_map.get(str(st), f"estado={st}")
            if not up:
                reboot_seen = True
            elif data is None and st is None:
                err_count += 1
                if err_count >= 3:
                    progress_bar(max_polls, max_polls,
                                 prefix=f"{e('cpu')} Actualizando",
                                 suffix="SESION PERDIDA - COMPLETADO")
                    sys.stdout.write("\n")
                    ok(f"{e('ok')} Firmware aplicado (sesion reiniciada, {int(elapsed)}s).")
                    return True
            else:
                err_count = 0
            progress_bar(i + 1, max_polls,
                         prefix=f"{e('cpu')} Actualizando",
                         suffix=f"({txt}) {int(elapsed)}s")
            if str(st) == "2":
                progress_bar(max_polls, max_polls,
                             prefix=f"{e('cpu')} Actualizando",
                             suffix="COMPLETADO")
                sys.stdout.write("\n")
                ok(f"{e('ok')} Firmware aplicado. La ONU se reinicia sola ({int(elapsed)}s).")
                return True
            if str(st) == "3":
                sys.stdout.write("\n")
                fail("La ONU reporto fallo en la actualizacion (UpgradeStatus=3).")
                return False
        sys.stdout.write("\n")
        warn("Tiempo de monitoreo agotado; la ONU podria seguir actualizando.")
        return None

    # --- espera de reinicio ---
    async def wait_online(self, timeout=300):
        info(f"{e('reboot')} Esperando reinicio de la ONU (puede tardar unos minutos) ...")
        t0 = time.time()
        while time.time() - t0 < timeout:
            if await wait_http(self.ip, timeout=8, quiet=True):
                ok(f"{e('ok')} ONU de nuevo en linea ({int(time.time() - t0)}s).")
                return True
            await asyncio.sleep(2)
        fail("La ONU no volvio a estar en linea a tiempo.")
        return False

    # --- restablecimiento de fabrica ---
    async def factory_reset(self, method="factory"):
        phase(4, "Restablecimiento de fabrica")
        arch = ACTIVE_PROFILE.get("arch", "realtek_boa")
        is_cortina = (arch == "zte_cortina" or 
                      getattr(self, "is_classic_form", False) or 
                      ACTIVE_PROFILE.get("config_page") is not None)

        if is_cortina:
            config_page = ACTIVE_PROFILE.get("config_page") or "/getpage.gch?pid=1002&nextpage=manager_dev_conf_t.gch"
            info(f"{e('reset')} [Cortina] Navegando a {config_page} ...")
            try:
                await self.page.goto(f"http://{self.ip}{config_page}", timeout=15000)
                await asyncio.sleep(2)
                self.page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

                btn_restore = self.page.locator("#Submit2, input[onclick*='DevRestoreSubmit']").first
                if await btn_restore.count() > 0:
                    info(f"{e('reset')} [Cortina] Ejecutando restauración de fábrica...")
                    await btn_restore.click()
                else:
                    await self.page.evaluate("if (typeof DevRestoreSubmit === 'function') DevRestoreSubmit();")
            except Exception as ex:
                warn(f"[Cortina] Aviso en restablecimiento web: {ex}")

            info(f"{e('reset')} Esperando reinicio de fábrica de la ONU...")
            await self.wait_online(timeout=180)
            ok(f"{e('ok')} Restablecimiento de fábrica Cortina completado.")
            return True

        info(f"{e('reset')} Navegando a Configuracion de recuperacion ...")
        try:
            await self.page.goto(f"http://{self.ip}{URL_CONFIG_RECOVERY}", timeout=15000)
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
        except Exception:
            pass

        # Localizar boton de factory reset (long) o default reset (key)
        if method == "factory":
            btn = self.page.locator(
                "button:has-text('Factory Reset'), "
                "button:has-text('Restablecimiento de f'), "
                "button:has-text('Restablecimiento de f\u00e1brica')"
            ).first
        else:
            btn = self.page.locator(
                "button:has-text('Default Configuration Reset'), "
                "button:has-text('Configuraci\u00f3n predeterminada')"
            ).first

        try:
            await btn.wait_for(timeout=15000)
            await btn.click()
            info(f"{e('reset')} Confirmando restablecimiento ...")
            await asyncio.sleep(1)
            confirm = self.page.locator(
                "button:has-text('OK'), button:has-text('Yes'), "
                "button:has-text('S\u00ed'), button:has-text('Si')"
            ).last
            try:
                await confirm.click(timeout=5000)
            except Exception:
                pass
        except Exception as ex:
            # Fallback: llamar directamente al endpoint.
            try:
                if method == "factory":
                    await self.api_post(EP_FACTORY_RESET_LONG, {})
                else:
                    await self.api_post(EP_FACTORY_RESET_KEY, {})
            except Exception as ex2:
                if "reset" in str(ex2).lower() or "econnreset" in str(ex2).lower() \
                        or "connection" in str(ex2).lower() or "timed out" in str(ex2).lower() \
                        or "timeout" in str(ex2).lower():
                    info(f"{e('ok')} ONU aplico el reset (desconexion esperada: {type(ex2).__name__}).")
                else:
                    raise
            else:
                ok(f"{e('ok')} POST de restablecimiento aceptado.")

        # Cuenta regresiva de 120s que muestra la propia ONU
        info(f"{e('reset')} Aplicando configuracion de fabrica (esperando reinicio) ...")
        t0 = time.time()
        saw_down = False
        up_streak = 0
        while time.time() - t0 < 150:
            up = await wait_http(self.ip, timeout=6, quiet=True)
            el = int(time.time() - t0)
            if not up:
                saw_down = True
                up_streak = 0
            else:
                up_streak += 1
                if saw_down and up_streak >= 3:
                    break
            progress_bar(min(el, 120), 120,
                         prefix=f"{e('reset')} Reiniciando a fabrica",
                         suffix=f"{el}s")
            await asyncio.sleep(1)
        sys.stdout.write("\n")
        ok(f"{e('ok')} Restablecimiento de fabrica completado "
           f"({int(time.time() - t0)}s).")
        return True

    # --- verificacion de VLAN ---
    async def verify_vlan(self):
        phase(5, "Verificacion de VLAN 3")
        info(f"{e('vlan')} Consultando configuracion WAN ...")
        arch = ACTIVE_PROFILE.get("arch", "realtek_boa")
        is_cortina = (arch == "zte_cortina" or getattr(self, "is_classic_form", False))

        if is_cortina:
            # En arquitectura Cortina / ZTE GHTML, consultar la página de configuración WAN
            wan_pages = [
                "/getpage.gch?pid=1002&nextpage=net_wanset_t.gch",
                "/getpage.gch?pid=1002&nextpage=net_wan_conf_t.gch",
                "/getpage.gch?pid=1002&nextpage=net_wancfg_t.gch",
                "/getpage.gch?pid=1002&nextpage=net_wan_t.gch",
            ]
            content = ""
            for wp in wan_pages:
                try:
                    await self.page.goto(f"http://{self.ip}{wp}", timeout=15000)
                    await asyncio.sleep(2)
                    content = await self.page.content()
                    if "TR069" in content or "VID_3" in content or "1_TR069_INTERNET" in content or "VLAN" in content:
                        break
                except Exception:
                    pass

            # Si no se encontró por URL directa, intentar hacer clic en el menú Network -> WAN
            if not ("TR069" in content or "VID_3" in content):
                try:
                    for sel in ["#mmNet", "text='Network'", "text='Red'", "text='Rede'"]:
                        el = self.page.locator(sel).first
                        if await el.count() > 0:
                            await el.click()
                            await asyncio.sleep(1)
                            break
                    for sel in ["#smWan", "#smWanConf", "text='WAN'", "text='Conexión WAN'", "text='Broadband'"]:
                        el = self.page.locator(sel).first
                        if await el.count() > 0:
                            await el.click()
                            await asyncio.sleep(2)
                            content = await self.page.content()
                            break
                except Exception:
                    pass

            found = (
                (TARGET_WAN_NAME and TARGET_WAN_NAME.lower() in content.lower())
                or "vid_3" in content.lower()
                or "1_tr069_internet_r_vid_3" in content.lower()
                or ("tr069" in content.lower() and "3" in content)
            )
            if found:
                ok(f"{e('vlan')} [Cortina] VLAN objetivo encontrada: {TARGET_WAN_NAME or 'VID 3'}")
                return True
            else:
                fail(f"{e('fail')} [Cortina] No se encontró {TARGET_WAN_NAME} / VLAN {TARGET_VLAN_ID} en la configuración WAN.")
                return False

        data = None
        for _ in range(10):
            try:
                data = await self.api_get(EP_WAN_SHOW)
                if data and data.get("data", {}).get("wan_link_list"):
                    break
            except Exception:
                pass
            await asyncio.sleep(3)

        if not data:
            fail("No se pudo obtener la lista WAN.")
            return False

        links = data.get("data", {}).get("wan_link_list", [])
        names = [l.get("tdaucWanName", "") for l in links]
        vids = [str(l.get("tdvlanid", "")) for l in links]
        info(f"{e('info')} WANs detectadas: {names if names else 'ninguna'}")

        found = any(
            (TARGET_WAN_NAME and TARGET_WAN_NAME.lower() in (n or "").lower())
            or (TARGET_VLAN_ID and str(l.get("tdvlanid", "")) == TARGET_VLAN_ID)
            for n, l in zip(names, links)
        )
        # Tambien acepta nombre que contenga TR069
        if not found:
            found = any("tr069" in (n or "").lower() or "vid_3" in (n or "").lower()
                        for n in names)
        if found:
            ok(f"{e('vlan')} VLAN objetivo encontrada: {TARGET_WAN_NAME}")
        else:
            fail(f"{e('fail')} No se encontro {TARGET_WAN_NAME} / VLAN {TARGET_VLAN_ID}.")
        return found

    async def screenshot(self, name):
        try:
            os.makedirs(SHOT_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(SHOT_DIR, f"{ts}_{name}.png")
            await self.page.screenshot(path=path)
            info(f"{e('info')} Captura guardada: {path}")
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Flujo principal por ONU
# ----------------------------------------------------------------------------
async def process_one(onu, browser, opts):
    ip = onu["ip"]
    puerto = onu["puerto"]
    headless = opts.get("headless", False)
    skip_wizard = opts.get("skip_wizard", False)
    factory_only = opts.get("factory_reset_only", False)
    check_only = opts.get("check", False)

    # Identificacion de la ONU para el registro (MAC del MikroTik como fallback)
    mac = onu.get("mac", "") or ""
    pon = ""

    # Etiqueta de salida por puerto (contextvars: por tarea, no global)
    CURRENT_TAG.set(f"P{puerto}")

    _set_status(puerto, estado="ESPERANDO", icono="\u23f3",
                detalle="Esperando arranque de la ONU")

    print(color("\n" + "=" * 40, "36"))
    print(_tag() + color(f"{e('onu')} ONU en {ip}  (Puerto: {puerto})", "1;37"))
    print(_tag() + color("=" * 40, "36"))

    context = await browser.new_context()
    page = await context.new_page()

    # Interceptor global de red. La ONU solo sirve su web cuando el header
    # "Host" es su IP de gestion (192.168.1.1); con cualquier otro Host responde
    # 302 hacia http://192.168.1.1/web_pages/conn-fail.html. En modo switch (IP
    # virtual 10.100.N.1) el navegador enviaria el Host de la URL, asi que se:
    #   1) fuerza "Host: 192.168.1.1" en cada peticion, y
    #   2) reescribe las URLs absolutas que la ONU genera hacia 192.168.1.1
    #      para que pasen por la IP virtual (la real no es alcanzable del host).
    # Tambien fuerza web_captcha="0" y show_captcha="0" en web_custom_show.cgi
    # (el captcha es 100% cliente, el servidor no lo valida; firmwares nuevos
    # leen show_captcha).
    async def nat_host(route):
        req = route.request
        url = req.url
        if url.startswith(f"http://{DEFAULT_IP}/"):
            url = url.replace(f"http://{DEFAULT_IP}/", f"http://{ip}/")
        headers = dict(req.headers)
        headers["Host"] = DEFAULT_IP
        try:
            resp = await route.fetch(url=url, headers=headers, timeout=120000)
            body = await resp.text()
            if EP_CAPTCHA_CFG in url:
                try:
                    obj = json.loads(body)
                    obj.setdefault("data", {})["web_captcha"] = "0"
                    # Firmwares mas nuevos leen "show_captcha" (no "web_captcha");
                    # hay que inyectarlo, el JSON original no lo trae.
                    obj["data"]["show_captcha"] = "0"
                    body = json.dumps(obj)
                except Exception:
                    body = '{"retcode":"0","data":{"web_captcha":"0","show_captcha":"0"}}'
            await route.fulfill(response=resp, body=body)
        except Exception:
            await route.continue_()

    await context.route("**/*", nat_host)

    # Limpiar cualquier sesion previa activa en la ONU (redirige a dashboard si hay)
    try:
        await page.request.get(f"http://{ip}{EP_LOGOUT}",
                               headers={"Host": DEFAULT_IP}, timeout=10000)
        info(f"{e('warn')} Sesion previa cerrada (si existia).")
    except Exception:
        pass

    ap = VSOLAutopilot(ip, browser, context, headless)
    ap.page = page
    result = "ERROR"
    vlan_ok = "NO"
    details = ""
    skip_firmware = opts.get("skip_firmware", False)

    try:
        # ---- FASE 1: esperar la ONU ----
        phase(1, f"Esperando arranque de la ONU en {ip}")
        # En modo masivo/continuo: probe rapido para saltar puertos sin ONU
        if opts.get("mass") and not await wait_http(
                ip, timeout=opts.get("probe_timeout", 25), quiet=True):
            fail(f"ONU {ip} (puerto {puerto}) no responde: puerto vacio o equipo apagado.")
            _set_status(puerto, estado="SIN_ONU", icono="\u25cb",
                        detalle="Sin respuesta HTTP", final=True, result="SIN_ONU")
            log_result(puerto, ip, "SIN_ONU", "NO",
                       "Sin respuesta HTTP (puerto vacio o ONU apagada)", mac, pon)
            return {"result": "SIN_ONU", "vlan": "NO",
                    "details": "Sin respuesta HTTP (puerto vacio o ONU apagada)"}
        if not await wait_http(ip, timeout=300):
            raise RuntimeError("ONU sin respuesta HTTP a tiempo")
        ok(f"{e('onu')} ONU respondiendo en {ip}")
        _set_status(puerto, estado="ESTABILIZANDO", icono="\u23f3",
                    detalle="Esperando auto-reinicio inicial de fábrica...")

        # Auto-reinicio del primer arranque (opcional, activo por defecto)
        if not opts.get("no_stabilize"):
            if not await wait_stable(ip):
                raise RuntimeError("ONU no se estabilizo (auto-reinicio pendiente)")

        _set_status(puerto, estado="CONECTADO", icono="\U0001f7e2",
                    detalle="ONU estabilizada. Iniciando login...")

        # ---- AUTENTICACION PROGRESIVA (default -> intermedia -> final) ----
        state = None
        cur_user, cur_pass = None, None
        # Construir lista de credenciales a probar segun el perfil del modelo
        candidates = ACTIVE_PROFILE.get("candidate_credentials", [])
        creds_to_try = []
        if opts.get("final_first"):
            creds_to_try.append(("final", onu.get("final_user", FINAL_USER), onu.get("final_pass", FINAL_PASS)))
            for u, p in candidates:
                if (u, p) != (onu.get("final_user", FINAL_USER), onu.get("final_pass", FINAL_PASS)):
                    lbl = "default" if (u, p) == (onu.get("user", DEFAULT_USER), onu.get("pass", DEFAULT_PASS)) else "candidato"
                    creds_to_try.append((lbl, u, p))
            creds_to_try.append(("intermedia", NEW_USER, NEW_PASS))
        else:
            creds_to_try.append(("default", onu.get("user", DEFAULT_USER), onu.get("pass", DEFAULT_PASS)))
            for u, p in candidates:
                if (u, p) != (onu.get("user", DEFAULT_USER), onu.get("pass", DEFAULT_PASS)) and (u, p) != (onu.get("final_user", FINAL_USER), onu.get("final_pass", FINAL_PASS)):
                    creds_to_try.append(("candidato", u, p))
            creds_to_try.append(("intermedia", NEW_USER, NEW_PASS))
            creds_to_try.append(("final", onu.get("final_user", FINAL_USER), onu.get("final_pass", FINAL_PASS)))

        for label, u, p in creds_to_try:
            if label == "default" and skip_wizard:
                continue
            logged = await ap.login(u, p, attempt_label=label)
            if logged == "lockout":
                # La clave actual provocó el bloqueo temporal: esperar a que termine el cooldown
                await ap.wait_cooldown()
                # Pasamos a la siguiente credencial sin reintentar la clave que ya falló
                continue
            if logged:
                # Comprobar si tiene permisos reales de administrador
                if u.lower() == "user":
                    warn(f"Usuario 'user' autenticado, pero carece de permisos para flasheo/reset. Buscando cuenta de administrador...")
                    continue
                state = label
                cur_user, cur_pass = u, p
                break
        if state is None:
            _set_status(puerto, estado="ERROR_AUTH", icono="🔐",
                        detalle="Claves admin no coinciden. Presiona botón RESET en la ONU 10s para restaurar.",
                        final=True, result="ERROR_AUTH")
            raise RuntimeError(
                "No se pudo autenticar como Administrador en la ONU (todas las credenciales fueron rechazadas). "
                "Para restaurar las credenciales de fábrica (admin / stdONU101), por favor mantén presionado "
                "el botón físico de RESET en la ONU durante 10 a 15 segundos con el equipo encendido."
            )

        ok(f"{e('login')} Estado detectado: {state} (usuario {cur_user}).")

        # Datos de identificacion (MAC y serial/PON) para el registro
        dev = await ap.get_device_info()
        mac = dev.get("mac") or mac
        pon = dev.get("pon") or ""

        # ---- Caso: ONU YA en estado final ----
        if state == "final":
            info(f"{e('info')} La ONU ya tiene credenciales finales (Powerlink).")
            _set_status(puerto, estado="VERIFICANDO", icono="\U0001f50d",
                        detalle="ONU final, verificando VLAN3 ...")
            vlan_ok = "SI" if await ap.verify_vlan() else "NO"
            await ap.screenshot("ya_configurada")
            result = "YA_CONFIGURADA" if vlan_ok == "SI" else "EXITO_LOGIN_FINAL"
            details = ("ONU ya estaba en estado final con VLAN3 verificada"
                       if vlan_ok == "SI"
                       else "Login final OK pero VLAN3 no verificada (revisar)")
            _set_status(puerto, estado=result, icono="\u2705",
                        detalle=details, final=True, result=result)
            try:
                await context.close()
            except Exception:
                pass
            log_result(puerto, ip, result, vlan_ok, details, mac, pon)
            print(_tag() + color("=" * 40, "36"))
            print(_tag() + color(f"{e('flag')} RESULTADO [{puerto} {ip}]: {result}  | VLAN3: {vlan_ok}", "1;37"))
            print(_tag() + color("=" * 40, "36"))
            ok(f"{e('finish')} ONU LISTA (puerto {puerto}).")
            return {"result": result, "vlan": vlan_ok, "details": details}

        # ---- Modo comprobacion (no destructivo) ----
        if check_only:
            info(f"{e('info')} Modo --check: solo comprobacion, NO se tocara firmware/wizard/reset.")
            vlan_ok = "SI" if await ap.verify_vlan() else "NO"
            await ap.screenshot("check")
            result = "CHECK_OK" if vlan_ok == "SI" else "CHECK_OK_SIN_VLAN"
            details = f"Acceso OK ({cur_user}); VLAN3={'SI' if vlan_ok=='SI' else 'NO'}"
            try:
                await context.close()
            except Exception:
                pass
            log_result(puerto, ip, result, vlan_ok, details, mac, pon)
            print(_tag() + color("=" * 40, "36"))
            print(_tag() + color(f"{e('flag')} RESULTADO [{puerto} {ip}]: {result}  | VLAN3: {vlan_ok}", "1;37"))
            print(_tag() + color("=" * 40, "36"))
            ok(f"{e('finish')} ONU LISTA (puerto {puerto}).")
        # ---- Comprobación temprana: ONU ya configurada con VLAN 3 ----
        vlan_precheck = await ap.verify_vlan()
        if vlan_precheck:
            info(f"{e('info')} La ONU ya tiene la VLAN 3 configurada ({TARGET_WAN_NAME}). No requiere flasheo.")
            await ap.screenshot("ya_configurada")
            result = "YA_CONFIGURADA"
            details = "ONU ya posee VLAN 3 activa y firmware configurado"
            _set_status(puerto, estado=result, icono="\u2705",
                        detalle=details, final=True, result=result)
            try:
                await context.close()
            except Exception:
                pass
            log_result(puerto, ip, result, "SI", details, mac, pon)
            print(_tag() + color("=" * 40, "36"))
            print(_tag() + color(f"{e('flag')} RESULTADO [{puerto} {ip}]: {result}  | VLAN3: SI", "1;37"))
            print(_tag() + color("=" * 40, "36"))
            ok(f"{e('finish')} ONU LISTA (puerto {puerto}).")
            return {"result": result, "vlan": "SI", "details": details}

        # ---- WIZARD (solo en modelos con wizard y en primer arranque con credenciales default) ----
        has_wizard = ACTIVE_PROFILE.get("has_wizard", False)
        if has_wizard and state == "default" and not skip_wizard:
            _set_status(puerto, estado="WIZARD", icono="\U0001f6e0\ufe0f",
                        detalle="Configurando asistente inicial ...")
            await ap.run_wizard(NEW_PASS)
            cur_user, cur_pass = NEW_USER, NEW_PASS
        else:
            info(f"{e('info')} Omitiendo asistente ({'no aplica para este modelo' if not has_wizard else 'no es primer arranque o --skip-wizard'}).")

        # ---- FIRMWARE (opcional con --skip-firmware) ----
        if factory_only or skip_firmware:
            info(f"{e('info')} Omitiendo subida de firmware "
                 f"({'--factory-reset-only' if factory_only else '--skip-firmware'}).")
        else:
            phase(3, f"Subida de firmware ({ACTIVE_PROFILE.get('name', 'ONU')})")
            _set_status(puerto, estado="FLASHEANDO", icono="\U0001f4e4",
                        detalle=f"Subiendo firmware ({os.path.basename(FIRMWARE_PATH)}) ...")
            try:
                await ap.goto_upgrade()
            except Exception as ex:
                warn(f"Navegacion a interfaz de upgrade no necesaria o fallida ({ex}); procediendo con subida directa...")
            await ap.screenshot("antes_upgrade")
            if await ap.upload_firmware(FIRMWARE_PATH) is False:
                raise RuntimeError("La ONU reporto fallo en la actualizacion")
            await ap.wait_online(timeout=360)
            ok(f"{e('ok')} Firmware actualizado. Reingresando al equipo ...")
            # Tras subir el firmware, el equipo normalmente conserva la contrasena del
            # asistente (admin/admin123); si el flasheo la reseteo, el default del
            # firmware es Powerlink. Probar previas, luego final, luego default.
            logged2 = None
            for lbl2, u2, p2 in (
                    ("post-actualizacion", cur_user or NEW_USER, cur_pass or NEW_PASS),
                    ("final", onu["final_user"], onu["final_pass"]),
                    ("default", onu["user"], onu["pass"]),
            ):
                logged2 = await ap.login(u2, p2, attempt_label=lbl2)
                if logged2:
                    break
            if logged2 is None:
                raise RuntimeError("Login post-actualizacion fallo")

        # ---- RESTABLECIMIENTO DE FABRICA ----
        _set_status(puerto, estado="REINICIANDO", icono="\U0001f504",
                    detalle="Restableciendo de fabrica ...")
        await ap.factory_reset(method=opts.get("reset_method", "factory"))
        await ap.wait_online(timeout=300)

        # ---- LOGIN FINAL (Powerlink) ----
        _set_status(puerto, estado="VERIFICANDO", icono="\U0001f50d",
                    detalle="Login final y verificacion VLAN3 ...")
        info(f"{e('login')} Equipo restaurado. Verificando credenciales finales ...")
        logged3 = await ap.login(onu["final_user"], onu["final_pass"],
                                 attempt_label="final")
        if logged3 is None:
            raise RuntimeError("No se pudo ingresar con credenciales finales (Powerlink)")

        # ---- VERIFICACION DE VLAN ----
        vlan_ok = "SI" if await ap.verify_vlan() else "NO"
        await ap.screenshot("final")

        if vlan_ok == "SI":
            result = "EXITO"
            details = "Firmware cargado, reset completado, VLAN3 verificada"
        else:
            result = "PARCIAL"
            details = "Firmware cargado y reset OK, pero VLAN3 NO encontrada"
        _set_status(puerto, estado=result, icono="\u2705" if vlan_ok == "SI" else "\u26a0\ufe0f",
                    detalle=details, final=True, result=result)

    except FileNotFoundError as ex:
        fail(str(ex))
        details = f"Fallo: {ex}"
        _set_status(puerto, estado="ERROR", icono="\u274c",
                    detalle=details, final=True, result="ERROR")
    except Exception as ex:
        fail(f"Error procesando {ip}: {ex}")
        details = f"Fallo: {str(ex).replace(',', ';')}"
        _set_status(puerto, estado="ERROR", icono="\u274c",
                    detalle=details, final=True, result="ERROR")

    try:
        await ap.screenshot("fin_proceso")
    except Exception:
        pass
    try:
        await context.close()
    except Exception:
        pass

    log_result(puerto, ip, result, vlan_ok, details, mac, pon)
    print(_tag() + color("=" * 40, "36"))
    print(_tag() + color(f"{e('flag')} RESULTADO [{puerto} {ip}]: {result}  | VLAN3: {vlan_ok}", "1;37"))
    print(_tag() + color("=" * 40, "36"))
    if result in ("EXITO", "YA_CONFIGURADA", "CHECK_OK", "CHECK_OK_SIN_VLAN",
                  "EXITO_LOGIN_FINAL", "PARCIAL"):
        ok(f"{e('finish')} ONU LISTA (puerto {puerto}).")
    return {"result": result, "vlan": vlan_ok, "details": details}


async def run_continuo(onus, browser, opts):
    """Modo continuo: cada puerto vigila de forma INDEPENDIENTE y en su propio
    ritmo. Sondea su ONU; si no responde la marca como vacio (esperando ONU
    nueva), y si responde (hay ONU) la configura. El limite de paralelismo solo
    acota cuantas configuraciones se ejecutan a la vez; el sondeo de puertos
    vacios no ocupa ese limite, asi todos los puertos reaccionan por separado.
    No termina por si mismo; se detiene con Ctrl+C."""
    total = len(onus)
    reset_status(total)
    sem = asyncio.Semaphore(opts.get("parallel", 20))
    poll = opts.get("poll", 10)
    probe_t = opts.get("probe_timeout", 8)
    print(color(f"\n{e('info')} Modo CONTINUO: monitoreando {total} puerto(s) "
                f"de forma independiente.", "1;33"))
    print(color(f"{e('info')} Se configurara automaticamente cada ONU nueva que se "
                f"conecte. Ctrl+C para salir.", "1;33"))

    # Deteccion de puertos fisicos via MikroTik (evita flashear puertos
    # enrutados/vacios y permite detectar una ONU NUEVA en el mismo puerto).
    mtk = None
    mtk_cfg = None
    mtk_state = {"ports": None}
    try:
        import mikrotik as mtk
        mtk_cfg = mtk.load_config()
    except Exception:
        mtk = None
    if mtk_cfg:
        p = mtk.get_active_ports(mtk_cfg, quiet=True)
        if p is None:
            print(color(f"{e('warn')} MikroTik sin conexion; modo por defecto "
                        f"(todos los puertos).", "1;33"))
        else:
            mtk_state["ports"] = p
            if p:
                print(color(f"{e('ok')} MikroTik: {len(p)} puerto(s) fisico(s) "
                            f"con ONU: {sorted(p)}", "1;36"))
            else:
                print(color(f"{e('warn')} MikroTik conectado pero sin ONUs "
                            f"fisicas. Esperando que conecten...", "1;33"))

    async def mtk_refresh():
        if not mtk_cfg:
            return
        while True:
            try:
                p = mtk.get_active_ports(mtk_cfg, quiet=True)
                if p is not None:
                    mtk_state["ports"] = p
            except Exception:
                pass
            await asyncio.sleep(30)

    # Estado persistente por puerto para no re-flashear la misma ONU.
    GRACE_RETIRADA = opts.get("grace_retirada", 60)  # s sin ONU para aceptar re-flasheo
    puerto_estado = {}  # {puerto: {"fase": "lista"|"espera", "mac": mac|None, "ausente": t|None}}

    def fase(puerto):
        return puerto_estado.setdefault(
            puerto, {"fase": "espera", "mac": None, "ausente": None, "errores": 0})

    async def port_worker(onu):
        ip = onu["ip"]
        puerto = onu["puerto"]
        while True:
            try:
                st = fase(puerto)
                active = mtk_state.get("ports")
                mac = None
                if active is not None:
                    mac = active.get(int(puerto))
                    if mac is None and int(puerto) not in active:
                        # MikroTik dice que este puerto no tiene ONU fisica:
                        # no gastar recursos, marcar y seguir esperando.
                        st["fase"] = "espera"
                        st["mac"] = None
                        st["ausente"] = time.time()
                        _set_status(puerto, estado="SIN_ONU", icono="\u25cb",
                                    detalle="Sin ONU fisica (puerto vacio/enrutado)")
                        for _ in range(poll):
                            await asyncio.sleep(1)
                        continue

                # ONU ya flasheada: quedarse en LISTA. Solo sale de LISTA si se
                # detecta una ONU distinta (MAC diferente) o, sin MikroTik, si el
                # puerto queda sin ONU el tiempo de gracia (retirada/nueva).
                if st["fase"] == "lista":
                    cambio = False
                    if mac and st["mac"] and mac != st["mac"]:
                        st["fase"] = "espera"
                        st["ausente"] = None
                        cambio = True
                        _set_status(puerto, estado="CONECTADO", icono="\U0001f7e2",
                                    detalle="Nueva ONU detectada (MAC distinta)")
                    elif not await wait_http(ip, timeout=probe_t, quiet=True):
                        # Sin respuesta: vigilar el tiempo de gracia.
                        if st["ausente"] is None:
                            st["ausente"] = time.time()
                        elif time.time() - st["ausente"] > GRACE_RETIRADA:
                            st["fase"] = "espera"
                            st["ausente"] = None
                            cambio = True
                            _set_status(puerto, estado="SIN_ONU", icono="\u25cb",
                                        detalle="ONU retirada. Esperando ONU nueva")
                    else:
                        st["ausente"] = None
                    if not cambio:
                        _set_status(puerto, estado="LISTA", icono="\u2714",
                                    detalle="ONU lista. Puede retirarla y conectar otra")
                        for _ in range(poll):
                            await asyncio.sleep(1)
                        continue

                # Sondeo ligero (sin ocupar el limite de paralelismo): permite
                # que todos los puertos reaccionen a la vez e independientes.
                if not await wait_http(ip, timeout=probe_t, quiet=True):
                    _set_status(puerto, estado="SIN_ONU", icono="\u25cb",
                                detalle="Sin respuesta HTTP (esperando ONU nueva)")
                else:
                    _set_status(puerto, estado="CONECTADO", icono="\U0001f7e2",
                                detalle="ONU detectada, esperando turno de flasheo")
                    async with sem:  # solo el flasheo real usa el limite
                        res = await process_one({**onu, "mac": mac}, browser, opts)
                    if res and res.get("result") in (
                            "EXITO", "YA_CONFIGURADA", "CHECK_OK", "CHECK_OK_SIN_VLAN",
                            "EXITO_LOGIN_FINAL", "PARCIAL"):
                        # Flasheo correcto: marcar LISTA y recordar la MAC.
                        st["fase"] = "lista"
                        st["mac"] = mac
                        st["ausente"] = None
                        st["errores"] = 0
                        _set_status(puerto, estado="LISTA", icono="\u2714",
                                    detalle="ONU lista. Puede retirarla y conectar otra")
                    else:
                        # Fallo: no martillar. Tras 3 errores seguidos, pausa
                        # larga (probable puerto enrutado o ONU problematica).
                        st["errores"] = st.get("errores", 0) + 1
                        if st["errores"] >= 3:
                            _set_status(puerto, estado="PAUSA", icono="\u23f8",
                                        detalle="3 errores seguidos. Reintentara en 5 min")
                            for _ in range(300):
                                await asyncio.sleep(1)
                            st["errores"] = 0
                            continue
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                st["errores"] = st.get("errores", 0) + 1
                _set_status(puerto, estado="ERROR", icono="\u274c",
                            detalle=f"Error: {str(ex)[:60]}")
                if st["errores"] >= 3:
                    _set_status(puerto, estado="PAUSA", icono="\u23f8",
                                detalle="3 errores seguidos. Reintentara en 5 min")
                    for _ in range(300):
                        await asyncio.sleep(1)
                    st["errores"] = 0
                    continue
            for _ in range(poll):
                await asyncio.sleep(1)

    workers = [asyncio.create_task(port_worker(o)) for o in onus]
    refresh_task = asyncio.create_task(mtk_refresh())
    tasks = workers + [refresh_task]
    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        for w in tasks:
            w.cancel()
        ok("Modo continuo detenido por el usuario.")
        raise
    finally:
        ok("Modo continuo finalizado.")


async def main():
    _reconfigure()
    opts = {}
    args = sys.argv[1:]
    mass = "--mass" in args
    opts["mass"] = mass
    opts["headless"] = "--headless" in args
    opts["skip_wizard"] = "--skip-wizard" in args
    opts["factory_reset_only"] = "--factory-reset-only" in args
    opts["skip_firmware"] = "--skip-firmware" in args
    opts["check"] = "--check" in args
    opts["no_stabilize"] = "--no-stabilize" in args
    opts["continuo"] = "--continuo" in args
    opts["final_first"] = "--final-first" in args
    opts["mass"] = mass or opts["continuo"]
    opts["parallel"] = 20 if (mass or opts["continuo"]) else 1
    opts["probe_timeout"] = 8 if opts["continuo"] else 25
    if "--poll" in args:
        try:
            opts["poll"] = max(5, int(args[args.index("--poll") + 1]))
        except Exception:
            pass
    if "--grace-retirada" in args:
        try:
            opts["grace_retirada"] = max(10, int(args[args.index("--grace-retirada") + 1]))
        except Exception:
            pass
    if "--parallel" in args:
        try:
            opts["parallel"] = max(1, int(args[args.index("--parallel") + 1]))
        except (ValueError, IndexError):
            pass
    if "--no-emoji" in args:
        global USE_EMOJI
        USE_EMOJI = False
    if "--no-color" in args:
        global USE_COLOR
        USE_COLOR = False
    global ACTIVE_PROFILE, FIRMWARE_PATH, DEFAULT_USER, DEFAULT_PASS, FINAL_USER, FINAL_PASS, TARGET_WAN_NAME, TARGET_VLAN_ID, CURRENT_BOX_CODE
    ip = DEFAULT_IP
    for i, a in enumerate(args):
        if a == "--ip" and i + 1 < len(args):
            ip = args[i + 1]
        if a == "--reset-method" and i + 1 < len(args):
            opts["reset_method"] = args[i + 1]
        if a in ("--caja", "--box") and i + 1 < len(args):
            CURRENT_BOX_CODE = args[i + 1].strip().upper()
        if a in ("--model", "--profile") and i + 1 < len(args):
            model_req = args[i + 1]
            prof = profiles.get_active_profile(model_req)
            if prof:
                ACTIVE_PROFILE = prof
                FIRMWARE_PATH = ACTIVE_PROFILE.get("firmware_path", FIRMWARE_PATH)
                DEFAULT_USER = ACTIVE_PROFILE.get("default_user", DEFAULT_USER)
                DEFAULT_PASS = ACTIVE_PROFILE.get("default_pass", DEFAULT_PASS)
                FINAL_USER = ACTIVE_PROFILE.get("final_user", FINAL_USER)
                FINAL_PASS = ACTIVE_PROFILE.get("final_pass", FINAL_PASS)
                TARGET_WAN_NAME = ACTIVE_PROFILE.get("target_wan_name", TARGET_WAN_NAME)
                TARGET_VLAN_ID = ACTIVE_PROFILE.get("target_vlan_id", TARGET_VLAN_ID)

    if not CURRENT_BOX_CODE and inventory_db:
        caja_act = inventory_db.obtener_caja_activa()
        if caja_act:
            CURRENT_BOX_CODE = caja_act.get("codigo_caja")

    print(color(f"\n{e('flag')} VSOL Autopilot - {ACTIVE_PROFILE.get('name', 'Estacion de Flasheo')}", "1;36"))
    print(f"  Modelo   : {ACTIVE_PROFILE.get('id')} ({ACTIVE_PROFILE.get('name')})")
    print(f"  Caja/Lote: {CURRENT_BOX_CODE or 'SIN ASIGNAR'}")
    print(f"  Firmware : {os.path.basename(FIRMWARE_PATH)}")
    print(f"  Existe   : {'SI' if os.path.exists(FIRMWARE_PATH) else 'NO'}")
    print(f"  Log CSV  : {LOG_CSV}")
    print(f"  Paralelo : {opts['parallel']} ONU(s) simultaneas"
          + (" (modo masivo)" if mass else ""))
    print()

    if mass or opts["continuo"]:
        onus = load_onus()
        if not onus:
            fail(f"No hay ONUs en {ONUS_LIST}. Activa puertos en onus_list.csv.")
            return
        if opts["continuo"]:
            # Modo continuo: vigila TODOS los puertos del MikroTik (ether1..etherN),
            # aunque no esten activos en el CSV, para configurar cualquier ONU nueva.
            # N = max_port del router (RB750=5, CRS326=20).
            max_port = 20
            try:
                import mikrotik as _mtk
                _cfg = _mtk.load_config()
                if _cfg:
                    max_port = _mtk.get_max_port(_cfg)
            except Exception:
                pass
            csv_onus = {}
            for o in onus:
                if str(o.get("puerto", "")).isdigit():
                    csv_onus[int(o["puerto"])] = o
            onus = []
            for n in range(1, max_port + 1):
                base = csv_onus.get(n)
                onus.append(base or {"ip": f"10.100.{n}.1",
                                     "user": DEFAULT_USER, "pass": DEFAULT_PASS,
                                     "puerto": str(n),
                                     "final_user": FINAL_USER, "final_pass": FINAL_PASS})
        modo = "CONTINUO" if opts["continuo"] else "MASIVO"
        print(color(f"{e('info')} Modo {modo}: {len(onus)} ONU(s) vigiladas.", "1;33"))
    else:
        m = re.match(r"^10\.100\.(\d+)\.1$", ip)
        puerto = m.group(1) if m else "1"
        onus = [{"ip": ip, "user": DEFAULT_USER, "pass": DEFAULT_PASS,
                 "puerto": puerto, "final_user": FINAL_USER, "final_pass": FINAL_PASS}]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=opts["headless"])
        results = []
        try:
            if opts["continuo"]:
                await run_continuo(onus, browser, opts)
                return
            sem = asyncio.Semaphore(opts.get("parallel", 1))
            done = {"n": 0}
            total = len(onus)

            async def worker(onu):
                async with sem:
                    r = await process_one(onu, browser, opts)
                done["n"] += 1
                print(color(f"[progreso] {done['n']}/{total} ONUs procesadas "
                            f"({100 * done['n'] // total}%)", "1;36"))
                return r

            results = await asyncio.gather(*(worker(o) for o in onus))
        finally:
            await browser.close()

    # Resumen final
    print(color("\n" + "=" * 60, "36"))
    print(color("  RESUMEN GENERAL", "1;36"))
    print(color("=" * 60, "36"))
    codes = {"YA_CONFIGURADA": ("32", e("ok")), "EXITO": ("32", e("finish")),
             "EXITO_LOGIN_FINAL": ("33", e("warn")), "SIN_ONU": ("33", e("warn")),
             "ERROR": ("31", e("fail"))}
    for onu, r in zip(onus, results):
        rc, icon = codes.get(r["result"], ("37", ""))
        vc = "32" if r["vlan"] == "SI" else "31"
        vlan_str = color(r["vlan"], vc)
        print("   Puerto " + str(onu.get("puerto", "?")).ljust(4) + " "
              + color(f"{icon} {r['result']}", rc).ljust(22)
              + f"VLAN3: {vlan_str:<3} - {r['details']}")
    print(color("=" * 60, "36"))
    print(color("  LEYENDA", "1;36"))
    print(f"   {e('ok')} YA_CONFIGURADA     : ya tenia firmware final (Powerlink) y VLAN3 OK - no requiere flasheo")
    print(f"   {e('finish')} EXITO              : flasheo completo: firmware subido y VLAN3 verificado")
    print(f"   {e('warn')} EXITO_LOGIN_FINAL : login final OK pero VLAN3 no verificada (revisar)")
    print(f"   {e('warn')} SIN_ONU             : puerto vacio o ONU apagada")
    print(f"   {e('fail')} ERROR               : fallo en algun paso (revisar detalle)")
    ok("Proceso finalizado. Revisa el CSV de registro.")


if __name__ == "__main__":
    asyncio.run(main())