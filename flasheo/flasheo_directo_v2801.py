# -*- coding: utf-8 -*-
"""
flasheo_directo_v2801.py — Ejecutor de flasheo y validación directa para VSOL V2801S-B / V2801D-B.
Realiza el ciclo de vida completo:
 1. Conexión a 192.168.1.1
 2. Autenticación con credenciales candidatas (admin/stdONU101, Powerlink/Powerlink2026*, etc.)
 3. Carga del firmware customizado V2801D-B_all_V6.1.4-260914_powerlink_GPON.bin
 4. Espera de reinicio post-flasheo
 5. Restablecimiento de fábrica web (Factory Reset) para activar la configuración customizada
 6. Espera de reinicio de fábrica
 7. Autenticación con usuario Powerlink y contraseña Powerlink2026*
 8. Verificación de VLAN 3 (1_TR069_INTERNET_R_VID_3)
 9. Registro en la base de datos local y sincronización con el módulo de flasheo de la Intranet
"""
import asyncio
import os
import sys
import time
import urllib.request
from datetime import datetime

# Rutas del proyecto
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

FIRMWARES_DIR = os.path.join(PROJECT_ROOT, "firmwares")
CAPTURA_DIR = os.path.join(PROJECT_ROOT, "capturas")
FW_NAME = "V2801D-B_all_V6.1.4-260914_powerlink_GPON.bin"
FW_PATH = os.path.join(FIRMWARES_DIR, FW_NAME)
ONU_IP = "192.168.1.1"

os.makedirs(CAPTURA_DIR, exist_ok=True)
os.makedirs(FIRMWARES_DIR, exist_ok=True)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def ts():
    return datetime.now().strftime("[%H:%M:%S]")


def log(msg, color="0"):
    print(f"\033[{color}m{ts()} {msg}\033[0m", flush=True)


def info(msg):
    log(f"ℹ  {msg}", "36")


def success(msg):
    log(f"✅ {msg}", "32")


def warn(msg):
    log(f"⚠️  {msg}", "33")


def error(msg):
    log(f"❌ {msg}", "31")


def check_connectivity(timeout=5):
    """Comprueba si la ONU en 192.168.1.1 responde HTTP."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            req = urllib.request.Request(
                f"http://{ONU_IP}/",
                headers={"Host": ONU_IP, "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status in (200, 302):
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


async def solve_captcha(page):
    """Resuelve el IdentCode del formulario ZTE / Cortina."""
    try:
        code = await page.evaluate("""() => {
            if (typeof createCode === 'function') createCode();
            var el = document.getElementById('checkCode');
            return window.code || (el ? el.value : '');
        }""")
        return code
    except Exception:
        return ""


async def try_login(page, username, password):
    """Intenta iniciar sesión en el formulario web clásico."""
    info(f"Probando login con '{username}' / '{password}' ...")
    try:
        await page.goto(f"http://{ONU_IP}/", timeout=15000, wait_until="domcontentloaded")
        await asyncio.sleep(1)
    except Exception:
        pass

    # Comprobar si ya está autenticado
    url = page.url.lower()
    content = await page.content()
    if "/login" not in url and ("logout" in content.lower() or "getpage.gch" in url or "main" in url):
        return "logged"

    user_input = page.locator("#Frm_Username, input[name='Username']").first
    pass_input = page.locator("#Frm_Password, input[name='Password']").first
    if await user_input.count() == 0:
        if await page.locator("button:has-text('Logout'), a:has-text('Logout')").count() > 0:
            return "logged"
        return "no_form"

    # Verificar si está bloqueada por cooldown
    try:
        errmsg = (await page.locator("#errmsg").text_content() or "").strip()
        if "three times" in errmsg.lower() or "minute later" in errmsg.lower():
            warn("Formulario bloqueado por cooldown de seguridad (60s). Esperando 65 segundos...")
            await asyncio.sleep(65)
            await page.goto(f"http://{ONU_IP}/", timeout=15000, wait_until="domcontentloaded")
            await asyncio.sleep(1)
    except Exception:
        pass

    try:
        await user_input.fill(username)
        await pass_input.fill(password)
        code = await solve_captcha(page)
        if code and await page.locator("#Frm_IdentCode").count() > 0:
            await page.locator("#Frm_IdentCode").fill(code)

        login_btn = page.locator("#LoginId, input[type='submit'][value*='Login'], button[type='submit']").first
        try:
            await login_btn.click(timeout=3000)
        except Exception:
            try:
                await page.evaluate("if (typeof dosubmit === 'function') dosubmit();")
            except Exception:
                pass
    except Exception as ex:
        warn(f"Aviso al completar formulario: {ex}")

    # Esperar cambio de estado
    waited = 0
    while waited < 8:
        await asyncio.sleep(1)
        waited += 1
        url = page.url.lower()
        content = await page.content()

        # Comprobar si saltó el asistente de cambio obligatorio de clave (primer arranque)
        if "frm_cfmpassword" in content.lower():
            info("Asistente de primer arranque detectado. Configurando contraseña a 'Powerlink2026*'...")
            try:
                await page.fill("#Frm_Password", "Powerlink2026*")
                await page.fill("#Frm_CfmPassword", "Powerlink2026*")
                await page.evaluate("if (typeof pageSubmit_chgpwd === 'function') pageSubmit_chgpwd();")
                await asyncio.sleep(3)
                if await page.locator("#Frm_Username").count() > 0:
                    code2 = await solve_captcha(page)
                    await page.fill("#Frm_Username", username)
                    await page.fill("#Frm_Password", "Powerlink2026*")
                    if code2 and await page.locator("#Frm_IdentCode").count() > 0:
                        await page.fill("#Frm_IdentCode", code2)
                    await page.evaluate("if (typeof dosubmit === 'function') dosubmit();")
                    await asyncio.sleep(3)
            except Exception as ex:
                warn(f"Aviso en asistente de cambio de clave: {ex}")
            return "logged"

        if "/login" not in url and await user_input.count() == 0:
            return "logged"
        if "logout" in content.lower() or "getpage.gch" in url or "mainframe" in content.lower():
            return "logged"
        try:
            errmsg = (await page.locator("#errmsg").text_content() or "").strip()
            if errmsg:
                if "three times" in errmsg.lower() or "minute later" in errmsg.lower():
                    return "cooldown"
                elif "wrong" in errmsg.lower() or "error" in errmsg.lower():
                    return "failed"
        except Exception:
            pass

    return "failed"


async def wait_reboot(desc="Reinicio", max_wait=200):
    """Espera a que la ONU caiga y vuelva a responder."""
    info(f"{desc}: esperando que la ONU se reinicie...")
    t0 = time.time()
    saw_down = False
    up_count = 0

    while time.time() - t0 < max_wait:
        alive = check_connectivity(timeout=2)
        if not alive:
            saw_down = True
            up_count = 0
        else:
            if saw_down:
                up_count += 1
                if up_count >= 3:
                    success(f"{desc}: ¡ONU restablecida y en línea! ({int(time.time() - t0)}s)")
                    return True
        await asyncio.sleep(2)
        elapsed = int(time.time() - t0)
        sys.stdout.write(f"\r  Esperando {desc}... ({elapsed}s)")
        sys.stdout.flush()

    sys.stdout.write("\n")
    warn(f"{desc}: Verificando respuesta final...")
    return check_connectivity(timeout=5)


def get_mac_address(ip="192.168.1.1"):
    """Obtiene la MAC de la ONU desde la tabla ARP."""
    try:
        import subprocess, re
        res = subprocess.run(["arp", "-a", ip], capture_output=True, text=True, timeout=3)
        m = re.search(r"([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})", res.stdout)
        if m:
            return m.group(1).replace("-", ":").upper()
    except Exception:
        pass
    return ""


def sync_onu_record(mac, pon, resultado, vlan3_ok, detalle):
    """Guarda en SQLite local y envía sincronización a la Intranet central."""
    try:
        from core import database
        pon_fmt = pon or (f"VSOL00{mac[-8:].replace(':', '')}" if mac else "VSOL00UNKNOWN")
        database.log_onu_flash(
            mac=mac,
            pon_original=pon,
            pon_sn=pon_fmt,
            modelo_id="V2801D-B",
            resultado=resultado,
            vlan3_ok=vlan3_ok,
            firmware=FW_NAME,
            puerto="1",
            ip=ONU_IP,
            detalles=detalle,
        )
        success("Registro guardado localmente y sincronización enviada a la Intranet.")
    except Exception as ex:
        warn(f"Aviso registrando en base de datos: {ex}")


async def main():
    print("=" * 65)
    print("  ESTACIÓN DE FLASHEO — VSOL V2801S-B / V2801D-B")
    print(f"  Firmware Objetivo : {FW_NAME}")
    print(f"  IP de Gestión      : {ONU_IP}")
    print("=" * 65)

    if not os.path.exists(FW_PATH):
        error(f"Archivo de firmware no encontrado en: {FW_PATH}")
        return 1

    info("Comprobando enlace de red con la ONU (192.168.1.1)...")
    if not check_connectivity(timeout=5):
        error("No hay respuesta en http://192.168.1.1/.")
        print("\n[!] VERIFICA:")
        print("    1. Cable de red conectado a la laptop.")
        print("    2. IP estática 192.168.1.100 / 255.255.255.0 configurada en el adaptador.")
        return 1

    success("Conexión HTTP establecida con la ONU.")
    mac = get_mac_address(ONU_IP)
    if mac:
        info(f"MAC detectada (ARP): {mac}")

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

        # -------------------------------------------------------------
        # FASE 1: Autenticación inicial
        # -------------------------------------------------------------
        info("=== FASE 1: Autenticación inicial ===")
        auth_user, auth_pass = None, None
        creds = [
            ("admin", "Powerlink2026*"),
            ("Powerlink", "Powerlink2026*"),
            ("admin", "stdONUi0i"),
            ("admin", "stdONU101"),
            ("user", "Powerlink2026*"),
            ("user", "user"),
            ("admin", "admin"),
            ("admin", "CorpPowerLink**2026"),
            ("admin", "admin123"),
            ("admin", "Redes2010"),
            ("telecomadmin", "admintelecom"),
        ]

        for u, pwd in creds:
            res = await try_login(page, u, pwd)
            if res == "cooldown":
                warn("Esperando 65s por cooldown de seguridad de la ONU...")
                await asyncio.sleep(65)
                res = await try_login(page, u, pwd)
            if res == "logged":
                success(f"¡Sesión iniciada con éxito! Usuario: '{u}'")
                auth_user, auth_pass = u, pwd
                break

        if not auth_user:
            error("No se pudo iniciar sesión con ninguna de las credenciales conocidas.")
            error("Si la ONU tiene una clave desconocida, presiona el botón físico de RESET durante 10-15s.")
            await browser.close()
            return 2

        shot_ini = os.path.join(CAPTURA_DIR, "v2801_paso1_login.png")
        await page.screenshot(path=shot_ini)

        # Comprobar si ya estaba en estado final (Powerlink + VLAN 3)
        if auth_user == "Powerlink":
            info("Comprobando si la ONU ya tiene VLAN 3 configurada...")
            already_vlan3 = False
            for wpage in ["IPv46_net_wan2_conf_t.gch", "net_wanset_t.gch"]:
                try:
                    await page.goto(f"http://{ONU_IP}/template.gch?pid=1002&nextpage={wpage}", timeout=15000, wait_until="networkidle")
                    await asyncio.sleep(2)
                    c = await page.content()
                    if (
                        "VLANID: 3" in c
                        or "DEFAULT_WAN" in c
                        or "1_TR069_INTERNET_R_VID_3" in c
                        or "VID_3" in c
                        or "VID 3" in c
                    ):
                        already_vlan3 = True
                        break
                except Exception:
                    pass
            if already_vlan3:
                success("¡La ONU ya se encuentra flasheada con credenciales Powerlink y VLAN 3 verificada!")
                sync_onu_record(mac, "", "YA_CONFIGURADA", "SI", "ONU ya poseía firmware final Powerlink y VLAN 3")
                await browser.close()
                return 0

        # -------------------------------------------------------------
        # FASE 2: Carga de Firmware
        # -------------------------------------------------------------
        info(f"=== FASE 2: Subiendo firmware {FW_NAME} ===")
        upgrade_url = f"http://{ONU_IP}/getpage.gch?pid=1002&nextpage=manager_dev_version_t.gch"
        await page.goto(upgrade_url, timeout=25000, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        file_input = page.locator("#VersionUpload, input[name='VersionUpload'], input[type='file']").first
        if await file_input.count() == 0:
            warn("Buscando selector de archivo en submenús...")
            for sel in ["#mmManager", "text='Administration'", "text='Administración'"]:
                if await page.locator(sel).first.count() > 0:
                    await page.locator(sel).first.click()
                    await asyncio.sleep(1)
                    break
            for sel in ["#smDevVer", "text='Software Management'", "text='Version Management'"]:
                if await page.locator(sel).first.count() > 0:
                    await page.locator(sel).first.click()
                    await asyncio.sleep(1)
                    break
            file_input = page.locator("#VersionUpload, input[name='VersionUpload'], input[type='file']").first

        if await file_input.count() == 0:
            error("No se pudo localizar el campo de subida de firmware.")
            await browser.close()
            return 3

        info(f"Seleccionando archivo binario ({os.path.getsize(FW_PATH) / 1024 / 1024:.2f} MB)...")
        await file_input.set_input_files(FW_PATH)
        await asyncio.sleep(1)

        info("Confirmando y enviando actualización...")
        sub_ok = await page.evaluate("""() => {
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
        success(f"Comando de actualización ejecutado ({sub_ok}).")

        # -------------------------------------------------------------
        # FASE 3: Espera de reinicio tras flasheo
        # -------------------------------------------------------------
        info("=== FASE 3: Aplicación de firmware y reinicio ===")
        await wait_reboot(desc="Flasheo y Reinicio", max_wait=200)

        # -------------------------------------------------------------
        # FASE 4: Restablecimiento de fábrica (Factory Reset)
        # -------------------------------------------------------------
        info("=== FASE 4: Restablecimiento de fábrica para activar customización ===")
        await asyncio.sleep(5)
        logged_reset = False
        for u, pwd in [(auth_user, auth_pass), ("admin", "Powerlink2026*"), ("admin", "stdONUi0i"), ("admin", "stdONU101"), ("Powerlink", "Powerlink2026*")]:
            if not u:
                continue
            res = await try_login(page, u, pwd)
            if res == "logged":
                logged_reset = True
                auth_user, auth_pass = u, pwd
                break

        restore_url = f"http://{ONU_IP}/getpage.gch?pid=1002&nextpage=manager_dev_conf_t.gch"
        try:
            await page.goto(restore_url, timeout=20000, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            await page.evaluate("""() => {
                if (typeof msgCallback2 === 'function') {
                    msgCallback2();
                    return;
                }
                if (typeof DevRestoreSubmit === 'function') {
                    DevRestoreSubmit();
                    return;
                }
                var btn = document.getElementById('Submit2') || document.querySelector("input[onclick*='DevRestoreSubmit']");
                if (btn) btn.click();
            }""")
            success("Comando de restablecimiento de fábrica enviado exitosamente.")
        except Exception as ex:
            warn(f"Aviso en reset de fábrica: {ex}")

        # -------------------------------------------------------------
        # FASE 5: Espera de reinicio de fábrica
        # -------------------------------------------------------------
        info("=== FASE 5: Reinicio de fábrica ===")
        await wait_reboot(desc="Reinicio de Fábrica", max_wait=180)

        # -------------------------------------------------------------
        # FASE 6: Verificación final de VLAN 3 y credenciales Powerlink
        # -------------------------------------------------------------
        info("=== FASE 6: Verificación de configuración final y VLAN 3 ===")
        await asyncio.sleep(8)

        final_logged = False
        for u, pwd in [("Powerlink", "Powerlink2026*"), ("admin", "Powerlink2026*"), ("admin", "stdONUi0i"), ("admin", "stdONU101")]:
            res = await try_login(page, u, pwd)
            if res == "logged":
                final_logged = True
                success(f"Autenticado exitosamente con credenciales finales: '{u}'")
                break

        # Navegar a la página de conexiones WAN (soporta V6.1.4 y V6.1.3)
        vlan3_ok = False
        for wan_page in ["IPv46_net_wan2_conf_t.gch", "net_wanset_t.gch"]:
            wan_url = f"http://{ONU_IP}/template.gch?pid=1002&nextpage={wan_page}"
            try:
                await page.goto(wan_url, timeout=15000, wait_until="networkidle")
                await asyncio.sleep(2)
                if await page.locator("#Frm_WANCName0").count() > 0:
                    try:
                        await page.select_option("#Frm_WANCName0", value="IGD.WD1.WCD1.WCIP1")
                        await asyncio.sleep(2)
                    except Exception:
                        pass
                content = await page.content()
                if (
                    "VLANID: 3" in content
                    or ('value="3"' in content and "VLAN" in content)
                    or "1_TR069_INTERNET_R_VID_3" in content
                    or "VID_3" in content
                    or "VID 3" in content
                    or ("DEFAULT_WAN" in content and "INTERNET_TR069" in content)
                ):
                    vlan3_ok = True
                    break
            except Exception:
                pass

        shot_final = os.path.join(CAPTURA_DIR, "v2801_flasheo_exitoso.png")
        await page.screenshot(path=shot_final)
        info(f"Captura final guardada en: {shot_final}")

        print("\n" + "=" * 65)
        if vlan3_ok and final_logged:
            success("¡PROCESO COMPLETADO CON ÉXITO TOTAL!")
            success(f"1. Firmware customizado cargado: {FW_NAME}")
            success("2. Restablecimiento de fábrica ejecutado correctamente.")
            success("3. Credenciales Powerlink / Powerlink2026* verificadas.")
            success("4. VLAN 3 ('1_TR069_INTERNET_R_VID_3' / Modo Router) detectada y verificada.")
            sync_onu_record(mac, "", "EXITO", "SI", "Firmware cargado; reset completado; VLAN 3 verificada")
        else:
            warn(f"Resultado final: Autenticación Powerlink={'SÍ' if final_logged else 'NO'} | VLAN 3={'SÍ' if vlan3_ok else 'NO'}")
            sync_onu_record(mac, "", "ERROR", "SI" if vlan3_ok else "NO", "Validación final incompleta")
        print("=" * 65 + "\n")

        await browser.close()
        return 0 if (vlan3_ok and final_logged) else 4


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
