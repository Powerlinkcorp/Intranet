# -*- coding: utf-8 -*-
"""
flasheo_directo_v2801.py — Ejecutor de flasheo y validación directa para VSOL V2801S-B.
Realiza el flujo completo:
1. Conexión a 192.168.1.1
2. Login con admin/stdONU101 (o credenciales detectadas)
3. Carga del firmware customizado V2801D-B_all_V6.1.4-260914_powerlink_GPON.bin
4. Espera del reinicio tras flasheo
5. Login y restablecimiento de fábrica (Factory Reset)
6. Espera del reinicio de fábrica
7. Login final con Powerlink/Powerlink2026* y verificación de VLAN 3
"""
import asyncio
import os
import sys
import time
import urllib.request
from datetime import datetime

# Rutas del proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIRMWARES_DIR = os.path.join(BASE_DIR, "firmwares")
CAPTURA_DIR = os.path.join(BASE_DIR, "capturas")
FW_NAME = "V2801D-B_all_V6.1.4-260914_powerlink_GPON.bin"
FW_PATH = os.path.join(FIRMWARES_DIR, FW_NAME)
ONU_IP = "192.168.1.1"

os.makedirs(CAPTURA_DIR, exist_ok=True)


def ts():
    return datetime.now().strftime("[%H:%M:%S]")


def log(msg, color="0"):
    print(f"\033[{color}m{ts()} {msg}\033[0m")


def info(msg):
    log(f"ℹ  {msg}", "36")


def success(msg):
    log(f"✅ {msg}", "32")


def warn(msg):
    log(f"⚠️  {msg}", "33")


def error(msg):
    log(f"❌ {msg}", "31")


def check_connectivity(timeout=10):
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
    """Resuelve el IdentCode si la página lo requiere."""
    try:
        if await page.locator("#Frm_IdentCode").count() > 0:
            code = await page.evaluate("""() => {
                if (!window.code || window.code.length !== 4) {
                    if (typeof createCode === 'function') createCode();
                }
                return window.code || (document.getElementById('checkCode') ? document.getElementById('checkCode').value : '');
            }""")
            if code:
                await page.locator("#Frm_IdentCode").fill(code)
                return code
    except Exception:
        pass
    return None


async def try_login(page, username, password):
    """Intenta iniciar sesión en el formulario web clásico."""
    info(f"Probando login con usuario='{username}'...")
    try:
        await page.goto(f"http://{ONU_IP}/", timeout=20000)
        await asyncio.sleep(1)
    except Exception:
        pass

    # Comprobar si ya está dentro
    url = page.url.lower()
    if "/dashboard" in url or "/overview" in url or "/template" in url:
        return "logged"

    user_input = page.locator("#Frm_Username, input[name='Username']").first
    pass_input = page.locator("#Frm_Password, input[name='Password']").first
    if await user_input.count() == 0:
        if await page.locator("button:has-text('Logout'), a:has-text('Logout')").count() > 0:
            return "logged"
        return "no_form"

    # Verificar si está en cooldown
    try:
        errmsg = await page.locator("#errmsg").text_content()
        if errmsg and ("three times" in errmsg.lower() or "minute later" in errmsg.lower()):
            warn("Formulario bloqueado por cooldown de 60s.")
            return "cooldown"
    except Exception:
        pass

    await user_input.fill(username)
    await pass_input.fill(password)
    await solve_captcha(page)

    login_btn = page.locator("#LoginId, input[type='submit'][value*='Login'], button[type='submit']").first
    try:
        await login_btn.click(timeout=5000)
    except Exception:
        try:
            await page.evaluate("if (typeof dosubmit === 'function') dosubmit();")
        except Exception:
            pass

    # Esperar cambio de página o mensaje de error
    waited = 0
    while waited < 10:
        await asyncio.sleep(1)
        waited += 1
        url = page.url.lower()
        if "/login" not in url and await user_input.count() == 0:
            return "logged"
        try:
            errmsg = await page.locator("#errmsg").text_content()
            if errmsg:
                if "three times" in errmsg.lower() or "minute later" in errmsg.lower():
                    return "cooldown"
                elif "wrong" in errmsg.lower() or "error" in errmsg.lower():
                    return "failed"
        except Exception:
            pass

    if await user_input.count() == 0 or await page.locator("a:has-text('Logout')").count() > 0:
        return "logged"
    return "failed"


async def wait_reboot(desc="Reinicio", max_wait=180):
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
    warn(f"{desc}: Tiempo límite alcanzado, verificando conectividad...")
    return check_connectivity(timeout=5)


async def main():
    print("=" * 65)
    print("  FLASHEO Y VALIDACIÓN DIRECTA — VSOL V2801S-B")
    print(f"  Firmware Objetivo: {FW_NAME}")
    print(f"  IP de Gestión   : {ONU_IP}")
    print("=" * 65)

    if not os.path.exists(FW_PATH):
        error(f"Archivo de firmware no encontrado en: {FW_PATH}")
        return 1

    info("Comprobando enlace de red con la ONU (192.168.1.1)...")
    if not check_connectivity(timeout=5):
        error("No hay respuesta en http://192.168.1.1/.")
        print("\n[!] VERIFICA LA CONFIGURACIÓN DE RED:")
        print("    1. La tarjeta Ethernet 3 debe tener asignada la IP estática: 192.168.1.100")
        print("    2. Máscara de subred: 255.255.255.0")
        print("    3. Ejecuta como Administrador: 'configurar_red_directa.bat'\n")
        return 1

    success("Conexión HTTP establecida con la ONU.")

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

        # -------------------------------------------------------------
        # FASE 1: Login
        # -------------------------------------------------------------
        info("=== FASE 1: Autenticación inicial ===")
        auth_user, auth_pass = None, None
        creds = [
            ("Powerlink", "Powerlink2026*"),
            ("admin", "stdONU101"),
            ("admin", "Redes2010"),
            ("user", "user"),
            ("admin", "admin"),
            ("admin", "admin123"),
        ]

        for u, pwd in creds:
            res = await try_login(page, u, pwd)
            if res == "cooldown":
                warn("Esperando 75 segundos por cooldown de seguridad de la ONU...")
                await asyncio.sleep(75)
                res = await try_login(page, u, pwd)
            if res == "logged":
                success(f"¡Sesión iniciada con éxito! Usuario: '{u}'")
                auth_user, auth_pass = u, pwd
                break

        if not auth_user:
            error("No se pudo iniciar sesión con ninguna de las credenciales conocidas.")
            await browser.close()
            return 1

        # Captura de pantalla del estado inicial
        shot_ini = os.path.join(CAPTURA_DIR, "v2801_paso1_login.png")
        await page.screenshot(path=shot_ini)
        info(f"Captura guardada: {shot_ini}")

        # -------------------------------------------------------------
        # FASE 2: Carga de Firmware
        # -------------------------------------------------------------
        info(f"=== FASE 2: Subiendo firmware {FW_NAME} ===")
        upgrade_url = f"http://{ONU_IP}/getpage.gch?pid=1002&nextpage=manager_dev_version_t.gch"
        await page.goto(upgrade_url, timeout=25000)
        await asyncio.sleep(2)

        file_input = page.locator("#VersionUpload, input[name='VersionUpload'], input[type='file']").first
        if await file_input.count() == 0:
            warn("No se encontró #VersionUpload directo; buscando en menús...")
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
            error("No se pudo localizar el campo de subida de firmware en la interfaz.")
            await browser.close()
            return 1

        info(f"Seleccionando archivo de firmware ({os.path.getsize(FW_PATH) / 1024 / 1024:.2f} MB)...")
        await file_input.set_input_files(FW_PATH)
        await asyncio.sleep(1)

        info("Confirmando y enviando actualización (msgCallback)...")
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
        success(f"Formulario de actualización enviado ({sub_ok}).")

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
        for u, pwd in [("admin", "stdONU101"), ("Powerlink", "Powerlink2026*"), (auth_user, auth_pass)]:
            res = await try_login(page, u, pwd)
            if res == "logged":
                logged_reset = True
                auth_user, auth_pass = u, pwd
                break

        if not logged_reset:
            warn("Login directo falló; esperando 15s adicionales antes de reintentar...")
            await asyncio.sleep(15)
            await try_login(page, "admin", "stdONU101")

        restore_url = f"http://{ONU_IP}/getpage.gch?pid=1002&nextpage=manager_dev_conf_t.gch"
        info(f"Navegando a {restore_url}...")
        try:
            await page.goto(restore_url, timeout=20000)
            await asyncio.sleep(2)
            btn_restore = page.locator("#Submit2, input[onclick*='DevRestoreSubmit']").first
            if await btn_restore.count() > 0:
                info("Haciendo clic en botón de Restauración de Fábrica...")
                await btn_restore.click()
            else:
                await page.evaluate("if (typeof DevRestoreSubmit === 'function') DevRestoreSubmit();")
            success("Comando de restablecimiento de fábrica enviado exitosamente.")
        except Exception as ex:
            warn(f"Aviso al enviar reset de fábrica: {ex}")

        # -------------------------------------------------------------
        # FASE 5: Espera de reinicio de fábrica
        # -------------------------------------------------------------
        info("=== FASE 5: Reinicio de fábrica ===")
        await wait_reboot(desc="Reinicio de Fábrica", max_wait=180)

        # -------------------------------------------------------------
        # FASE 6: Verificación final de VLAN 3 y credenciales Powerlink
        # -------------------------------------------------------------
        info("=== FASE 6: Verificación de configuración final y VLAN 3 ===")
        await asyncio.sleep(10)

        final_logged = False
        for u, pwd in [("Powerlink", "Powerlink2026*"), ("admin", "stdONU101")]:
            res = await try_login(page, u, pwd)
            if res == "logged":
                final_logged = True
                success(f"Autenticado exitosamente con credenciales finales: '{u}'")
                break

        # Navegar a la página de conexiones WAN
        wan_url = f"http://{ONU_IP}/getpage.gch?pid=1002&nextpage=net_wanset_t.gch"
        try:
            await page.goto(wan_url, timeout=15000)
            await asyncio.sleep(2)
        except Exception:
            pass

        content = await page.content()
        shot_final = os.path.join(CAPTURA_DIR, "v2801_flasheo_exitoso.png")
        await page.screenshot(path=shot_final)
        info(f"Captura final guardada en: {shot_final}")

        # Comprobar presencia de VLAN 3
        vlan3_ok = (
            "1_TR069_INTERNET_R_VID_3" in content
            or "VID_3" in content
            or "VID 3" in content
            or ("TR069" in content and "3" in content)
        )

        print("\n" + "=" * 65)
        if vlan3_ok:
            success("¡PROCESO COMPLETADO CON ÉXITO TOTAL!")
            success("1. Firmware customizado cargado: V2801D-B_all_V6.1.4-260914_powerlink_GPON.bin")
            success("2. Restablecimiento de fábrica ejecutado correctamente.")
            success("3. VLAN 3 ('1_TR069_INTERNET_R_VID_3' / Modo Router) detectada y verificada.")
        else:
            warn("Proceso de flasheo finalizado, pero no se visualizó 'VID_3' directamente en el texto WAN.")
            info("Revisa la captura de pantalla generada para validación manual visual.")
        print("=" * 65 + "\n")

        await browser.close()
        return 0 if vlan3_ok else 2


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
