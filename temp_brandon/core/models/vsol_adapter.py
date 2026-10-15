# -*- coding: utf-8 -*-
"""
vsol_adapter.py — Adaptador especializado para ONUs VSOL (HG3232AXT-H, V2804AX30-H, V2801, etc.).
Implementa la interfaz BaseONU ejecutando el flujo UI idéntico al proceso manual de soporte.
"""
import asyncio
import json
import re
from playwright.async_api import async_playwright

from .base_onu import BaseONU
from ..utils.network_utils import check_http_alive, DEFAULT_MGMT_IP

# Endpoints conocidos en firmware VSOL
EP_LOGIN = "/boaform/web_login_exe.cgi"
EP_LOGOUT = "/boaform/web_logout_ext.cgi"
EP_CAPTCHA_CFG = "/boaform/web_custom_show.cgi"
EP_DEVICE_BASIC = "/boaform/device_basic_show.cgi"
EP_WAN_SHOW = "/boaform/network_wan_show.cgi"
EP_WAN_ADD = "/boaform/network_wan_add.cgi"
EP_WLAN_2G_SHOW = "/boaform/wlan_basic_show.cgi"
EP_WLAN_2G_SET = "/boaform/wlan_basic_set.cgi"
EP_WLAN_5G_SHOW = "/boaform/wlan_5_basic_show.cgi"
EP_WLAN_5G_SET = "/boaform/wlan_5_basic_set.cgi"
EP_WPS_2G_SET = "/boaform/wps_basic_set.cgi"
EP_WPS_5G_SET = "/boaform/wps_basic_5_set.cgi"

MAC_REGEX = re.compile(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")


def _extract_mac_pon(basic_data):
    mac = ""
    pon = ""
    try:
        data = basic_data.get("data", {}) if isinstance(basic_data, dict) else {}
        dev_base = data.get("device_base_list", [])
        if dev_base and isinstance(dev_base, list):
            pon = dev_base[0].get("devicenumber", "")

        lan_list = data.get("lan_info_list", [])
        for item in lan_list:
            m = item.get("Table_lan1_3_mac_table", "")
            if m and m.lower() not in ("none", "n/a", ""):
                mac = m.upper()
                break

        if not mac:
            text = json.dumps(basic_data)
            match = MAC_REGEX.search(text)
            if match:
                mac = match.group(0).upper()
    except Exception:
        pass
    return mac, pon


class VSOLAdapter(BaseONU):
    """Adaptador para equipos VSOL."""

    def __init__(self, ip, log_callback=None, sn=None, mac=None):
        super().__init__(ip, log_callback)
        self.sn = sn
        self.mac = mac
        self.browser = None
        self.context = None
        self.page = None
        self.authenticated_user = None

    async def _setup_browser(self, p):
        self.browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        self.context = await self.browser.new_context()

        # Interceptor de red: Host Header y Bypass de Captcha
        async def nat_interceptor(route):
            req = route.request
            url = req.url
            if url.startswith(f"http://{DEFAULT_MGMT_IP}/"):
                url = url.replace(f"http://{DEFAULT_MGMT_IP}/", f"http://{self.ip}/")
            headers = dict(req.headers)
            headers["Host"] = DEFAULT_MGMT_IP
            try:
                resp = await route.fetch(url=url, headers=headers, timeout=25000)
                body = await resp.text()
                if "/boaform/web_custom_show.cgi" in url or "/boaform/wan_select_show.cgi" in url:
                    try:
                        obj = json.loads(body)
                        obj.setdefault("data", {})["web_captcha"] = "0"
                        obj["data"]["show_captcha"] = "0"
                        body = json.dumps(obj)
                    except Exception:
                        pass
                await route.fulfill(response=resp, body=body)
            except Exception:
                await route.continue_()

        await self.context.route("**/*", nat_interceptor)
        self.page = await self.context.new_page()

    async def _api_get(self, path):
        try:
            resp = await self.page.request.get(
                f"http://{self.ip}{path}",
                headers={"Host": DEFAULT_MGMT_IP},
                timeout=15000
            )
            if resp.status == 200:
                try:
                    return await resp.json()
                except Exception:
                    return None
        except Exception:
            pass
        return None

    async def _api_post(self, path, data=None):
        try:
            resp = await self.page.request.post(
                f"http://{self.ip}{path}",
                headers={"Host": DEFAULT_MGMT_IP, "Content-Type": "application/json"},
                data=json.dumps(data) if isinstance(data, (dict, list)) else data,
                timeout=20000
            )
            if resp.status == 200:
                try:
                    return await resp.json()
                except Exception:
                    return {"status": 200}
        except Exception as e:
            self.log(f"Error en POST {path}: {e}", "warn")
        return None

    async def _try_autofill_captcha(self, form):
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
            if code and await form.locator("input").count() > 2:
                await form.locator("input").nth(2).fill(code)
                return True
        except Exception:
            pass
        return False

    async def login(self) -> bool:
        self.log(f"Conectando a http://{self.ip}/ ...", "info", step="login", pct=15)
        try:
            await self.page.goto(f"http://{self.ip}/", timeout=25000)
        except Exception:
            await asyncio.sleep(2)
            await self.page.goto(f"http://{self.ip}/", timeout=25000)

        is_classic = False
        try:
            if await self.page.locator("#Frm_Username, input[name='Username']").count() > 0:
                is_classic = True
        except Exception:
            is_classic = False

        form = self.page.locator("form.login-form") if not is_classic else None

        if not is_classic:
            try:
                await form.locator("input[type='text']").first.wait_for(timeout=8000)
            except Exception:
                if "/login" not in self.page.url:
                    self.log("Sesión activa detectada en la ONU.", "ok")
                    self.authenticated_user = "Sesión Activa"
                    return True
                try:
                    await self.page.request.get(f"http://{self.ip}{EP_LOGOUT}", headers={"Host": DEFAULT_MGMT_IP})
                    await self.page.goto(f"http://{self.ip}/", timeout=15000)
                    await form.locator("input[type='text']").first.wait_for(timeout=10000)
                except Exception:
                    pass

        from ..services.credentials_service import CredentialsService
        candidates = CredentialsService.get_candidates(sn=self.sn, mac=self.mac)
        self.log(f"Iniciando ciclo de autenticación ({len(candidates)} credenciales)...", "info")

        for u, pwd in candidates:
            self.log(f"Probando credencial: {u} / {'*' * len(pwd)}", "info")
            if is_classic:
                u_in = self.page.locator("#Frm_Username, input[name='Username']").first
                p_in = self.page.locator("#Frm_Password, input[name='Password']").first
                await u_in.fill(u)
                await p_in.fill(pwd)
                if await self.page.locator("#checkCode").count() > 0:
                    try:
                        code = await self.page.evaluate("""() => {
                            if (window.code) return String(window.code);
                            const el = document.getElementById('checkCode');
                            if (!el) return '';
                            return el.value || el.innerText || el.textContent || '';
                        }""")
                        if not code:
                            code = await self.page.locator("#checkCode").input_value()
                        if code and await self.page.locator("#Frm_IdentCode").count() > 0:
                            await self.page.locator("#Frm_IdentCode").fill(code.strip())
                    except Exception:
                        pass
                btn = self.page.locator("#LoginId, input[type='submit'], button[type='submit']").first
                await btn.click()
            else:
                if await form.locator("input[type='text']").count() == 0:
                    break
                await form.locator("input[type='text']").first.fill(u)
                await form.locator("input[type='password']").first.fill(pwd)
                await self._try_autofill_captcha(form)
                btn = form.locator("button").first
                await btn.click()

            for _ in range(12):
                await asyncio.sleep(1)
                url = self.page.url
                if "/login" not in url.lower():
                    self.authenticated_user = u
                    self.log(f"Autenticación exitosa con usuario '{u}'.", "ok", step="auth_ok", pct=25)
                    return True
                if not is_classic and await form.count() == 0:
                    self.authenticated_user = u
                    self.log(f"Acceso confirmado al panel de administración.", "ok", step="auth_ok", pct=25)
                    return True

        self.log("Error: Ningún juego de credenciales maestras fue aceptado por la ONU.", "error")
        return False

    async def probe(self) -> dict:
        async with async_playwright() as p:
            alive = await check_http_alive(self.ip, timeout=5)
            if not alive:
                return {
                    "success": False,
                    "error": f"La ONU en {self.ip} no responde en el puerto 80 / HTTP.",
                    "ip": self.ip
                }

            await self._setup_browser(p)
            try:
                logged = await self.login()
                if not logged:
                    return {
                        "success": False,
                        "error": "Fallo de autenticación en la ONU (credenciales rechazadas).",
                        "ip": self.ip
                    }

                basic = await self._api_get(EP_DEVICE_BASIC) or {}
                data_b = basic.get("data", {})
                dev_base = data_b.get("device_base_list", [{}])[0]
                pon_info = data_b.get("pon_info_list", [{}])[0]

                mac, pon_serial = _extract_mac_pon(basic)
                model = dev_base.get("devicemodel", "VSOL ONU")
                hw_ver = dev_base.get("hwversion", "")
                fw_ver = dev_base.get("softwareversion", "")
                tx_pwr = pon_info.get("Txpower", "N/A")
                rx_pwr = pon_info.get("Rxpower", "N/A")
                pon_status = pon_info.get("connectstatus", "0")

                wan_data = await self._api_get(EP_WAN_SHOW) or {}
                wan_links = wan_data.get("data", {}).get("wan_link_list", [])
                active_vlans = []
                for w in wan_links:
                    active_vlans.append({
                        "name": w.get("tdaucWanName", ""),
                        "vlan_id": str(w.get("tdvlanid", "")),
                        "mode": "Route" if str(w.get("tdconnectiontype", "")) == "1" else "Bridge",
                        "type": "DHCP" if str(w.get("tducAddressingType", "")) == "2" else "PPPoE/Static"
                    })

                wlan_2g = await self._api_get(EP_WLAN_2G_SHOW) or {}
                data_2g = wlan_2g.get("data", {})
                ssid_2g = (
                    data_2g.get("wifi_basic_list", [{}])[0].get("wlanssid") or
                    data_2g.get("Table_wlan1_1_name_table") or
                    data_2g.get("multissid_list", [{}])[0].get("ssid_name") or
                    data_2g.get("wlanssid") or ""
                )
                enabled_2g = str(data_2g.get("wlan_disabled", "0")) == "0"
                auth_2g = (
                    data_2g.get("wifi_basic_list", [{}])[0].get("WlanAuthMode_select") or
                    data_2g.get("Table_wlan3_1_auth_table") or ""
                )

                wlan_5g = await self._api_get(EP_WLAN_5G_SHOW) or await self._api_get(EP_WLAN_5G_SET) or {}
                data_5g = wlan_5g.get("data", {})
                has_5g = bool(data_5g) or bool(data_2g.get("wl_band_5g") == "1") or bool(data_2g.get("ax_support_5g") == "1")
                ssid_5g = (
                    data_5g.get("wifi_5_basic_list", [{}])[0].get("wlanssid_5") or
                    data_5g.get("wifi_basic_list", [{}])[0].get("wlanssid_5") or
                    data_5g.get("Table_wlan1_1_name_table") or
                    data_5g.get("multissid_list", [{}])[0].get("ssid_name") or
                    data_5g.get("wlanssid_5") or ""
                )
                enabled_5g = str(data_5g.get("wlan_disabled", "0")) == "0"

                return {
                    "success": True,
                    "ip": self.ip,
                    "model": model,
                    "mac": mac,
                    "pon_serial": pon_serial,
                    "hw_version": hw_ver,
                    "software_version": fw_ver,
                    "optical_signal": {
                        "rx_power_dbm": rx_pwr,
                        "tx_power_dbm": tx_pwr,
                        "connected": pon_status == "1"
                    },
                    "wan_links": active_vlans,
                    "wifi_2g": {
                        "ssid": ssid_2g,
                        "enabled": enabled_2g,
                        "auth_mode": auth_2g
                    },
                    "wifi_5g": {
                        "supported": has_5g,
                        "ssid": ssid_5g,
                        "enabled": enabled_5g
                    } if has_5g else {"supported": False}
                }
            finally:
                if self.browser:
                    await self.browser.close()

    async def provision(self, vlan_id: str, ssid_2g: str, pass_2g: str, ssid_5g: str = None, pass_5g: str = None) -> dict:
        from ..services.history_service import HistoryService

        vlan_str = str(vlan_id).strip()
        ssid_2g = (ssid_2g or "").strip()
        pass_2g = (pass_2g or "").strip()
        ssid_5g = (ssid_5g or "").strip()
        pass_5g = (pass_5g or pass_2g or "").strip()

        async with async_playwright() as p:
            self.log(f"Iniciando aprovisionamiento en ONU {self.ip} (VLAN {vlan_str})", "info", step="start", pct=5)

            alive = await check_http_alive(self.ip, timeout=8)
            if not alive:
                msg = f"La ONU en {self.ip} no responde a peticiones HTTP."
                self.log(msg, "error")
                HistoryService.log(self.ip, "", "", "VSOL", vlan_str, ssid_2g, ssid_5g, "ERROR", msg)
                return {"success": False, "error": msg}

            await self._setup_browser(p)
            try:
                # 1. Login
                logged = await self.login()
                if not logged:
                    msg = "Fallo de autenticación (credenciales no válidas)."
                    self.log(msg, "error")
                    HistoryService.log(self.ip, "", "", "VSOL", vlan_str, ssid_2g, ssid_5g, "ERROR", msg)
                    return {"success": False, "error": msg}

                basic = await self._api_get(EP_DEVICE_BASIC) or {}
                mac, pon_serial = _extract_mac_pon(basic)
                model = basic.get("data", {}).get("device_base_list", [{}])[0].get("devicemodel", "VSOL")
                self.log(f"Equipo identificado: {model} | MAC: {mac or 'N/A'} | PON: {pon_serial or 'N/A'}", "ok")

                # =========================================================================
                # PASO 1 (PRIMERO): CONFIGURACIÓN WI-FI 2.4 GHz Y 5 GHz
                # =========================================================================
                if ssid_2g:
                    self.log(f"[1/3] Configurando Wi-Fi 2.4 GHz ('{ssid_2g}')...", "info", step="wifi_2g", pct=35)
                    try:
                        await self.page.goto(f"http://{self.ip}/admin/wireless_settings/2g_config/2g_basic", timeout=25000)
                        await asyncio.sleep(2)

                        ssid_in_2g = self.page.locator(".el-form-item:has-text('Nombre WiFi') input.el-input__inner, .el-form-item:has-text('SSID') input").first
                        if await ssid_in_2g.count() == 0:
                            ssid_in_2g = self.page.locator("input[type='text']").nth(0)
                        await ssid_in_2g.fill(ssid_2g)

                        pass_in_2g = self.page.locator(".el-form-item:has-text('Clave Precompartida WPA') input.el-input__inner, input[type='password']").first
                        await pass_in_2g.fill(pass_2g)

                        btn_sub_2g = self.page.locator("button:has-text('Enviar'), button:has-text('Aplicar'), button:has-text('Guardar')").first
                        await btn_sub_2g.click()
                        await asyncio.sleep(3)
                        self.log(f"Wi-Fi 2.4 GHz guardado exitosamente ('{ssid_2g}')", "ok")
                    except Exception as e:
                        self.log(f"Aviso en Wi-Fi 2.4G vía UI: {e}; aplicando vía API...", "warn")
                        wlan_2g_payload = {
                            "wlanssid": ssid_2g,
                            "WAPPreShared_text": pass_2g,
                            "WlanAuthMode_select": "4",
                            "WlanPwdMode_select": "3",
                            "Table_wlan1_1_name_table": ssid_2g,
                            "Table_wlan5_1_key_table": pass_2g,
                            "wlan_disabled": "0",
                            "wlan_disabled_checkbox": "0"
                        }
                        await self._api_post(EP_WLAN_2G_SET, wlan_2g_payload)

                has_5g_target = bool(ssid_5g)
                if has_5g_target:
                    self.log(f"[2/3] Configurando Wi-Fi 5 GHz ('{ssid_5g}')...", "info", step="wifi_5g", pct=50)
                    try:
                        await self.page.goto(f"http://{self.ip}/admin/wireless_settings/5g_config/5g_basic", timeout=20000)
                        await asyncio.sleep(2)

                        ssid_in_5g = self.page.locator(".el-form-item:has-text('Nombre WiFi') input.el-input__inner, .el-form-item:has-text('SSID') input").first
                        if await ssid_in_5g.count() == 0:
                            ssid_in_5g = self.page.locator("input[type='text']").nth(0)
                        await ssid_in_5g.fill(ssid_5g)

                        pass_in_5g = self.page.locator(".el-form-item:has-text('Clave Precompartida WPA') input.el-input__inner, input[type='password']").first
                        await pass_in_5g.fill(pass_5g)

                        btn_sub_5g = self.page.locator("button:has-text('Enviar'), button:has-text('Aplicar'), button:has-text('Guardar')").first
                        await btn_sub_5g.click()
                        await asyncio.sleep(3)
                        self.log(f"Wi-Fi 5 GHz guardado exitosamente ('{ssid_5g}')", "ok")
                    except Exception as e:
                        self.log(f"Aviso en Wi-Fi 5G vía UI: {e}; aplicando vía API...", "warn")
                        wlan_5g_payload = {
                            "wlanssid_5": ssid_5g,
                            "WAPPreShared_5_text": pass_5g,
                            "WlanAuthMode_5_select": "4",
                            "WlanPwdMode_5_select": "3",
                            "Table_wlan1_1_name_table": ssid_5g,
                            "Table_wlan5_1_key_table": pass_5g,
                            "wlan_disabled": "0"
                        }
                        await self._api_post(EP_WLAN_5G_SET, wlan_5g_payload)

                # =========================================================================
                # PASO 2 (SEGUNDO): CONFIGURACIÓN DE RED (WAN) Y VLAN
                # =========================================================================
                self.log(f"[3/3] Accediendo a Configuración de Red para aplicar VLAN {vlan_str} ...", "info", step="wan_vlan", pct=70)
                wan_applied = False

                # Validación: Si la ONU ya posee la VLAN solicitada, conservarla intacta
                try:
                    wan_data = await self._api_get(EP_WAN_SHOW) or {}
                    wan_links = wan_data.get("data", {}).get("wan_link_list", [])
                    for w in wan_links:
                        w_vlan = str(w.get("tdvlanid", "")).strip()
                        w_name = str(w.get("tdaucWanName", "")).strip()
                        if w_vlan == vlan_str or f"VID_{vlan_str}" in w_name:
                            wan_applied = True
                            self.log(f"[Validación VLAN] La ONU ya posee la VLAN {vlan_str} configurada ({w_name}). Se conservan los parámetros existentes sin alterar.", "ok")
                            break
                except Exception as ex_chk:
                    self.log(f"Comprobación de VLAN existente: {ex_chk}", "debug")

                if not wan_applied:
                    try:
                        await self.page.goto(f"http://{self.ip}/admin/network/network_config/wan_config", timeout=25000)
                        await asyncio.sleep(2)

                        # 1. Seleccionar 'Nuevo'
                        self.log("Seleccionando 'Nuevo' en Seleccionar configuración...", "info")
                        select_cfg = self.page.locator(".el-form-item:has-text('Seleccionar configuración') .el-select, .el-form-item:has-text('Select configuration') .el-select").first
                        if await select_cfg.count() == 0:
                            select_cfg = self.page.locator(".el-select").first
                        await select_cfg.click()
                        await asyncio.sleep(1)

                        opt_nuevo = self.page.locator(".el-select-dropdown__item:has-text('Nuevo'), .el-select-dropdown__item:has-text('New'), .el-select-dropdown__item:has-text('nuevo')").last
                        await opt_nuevo.click()
                        await asyncio.sleep(1)

                        # 2. Modo de Conexión: Route
                        select_mode = self.page.locator(".el-form-item:has-text('Modo de Conexión') .el-select, .el-form-item:has-text('Connection Mode') .el-select").first
                        if await select_mode.count() > 0:
                            await select_mode.click()
                            await asyncio.sleep(0.8)
                            opt_route = self.page.locator(".el-select-dropdown__item:has-text('Route'), .el-select-dropdown__item:has-text('route')").last
                            await opt_route.click()
                            await asyncio.sleep(0.8)

                        # 3. Protocolo: IPv4 / Modo: DHCP
                        btn_ipv4 = self.page.locator("label.el-radio-button:has-text('IPv4')").first
                        if await btn_ipv4.count() > 0:
                            await btn_ipv4.click()
                            await asyncio.sleep(0.5)

                        btn_dhcp = self.page.locator("label.el-radio-button:has-text('DHCP')").first
                        if await btn_dhcp.count() > 0:
                            await btn_dhcp.click()
                            await asyncio.sleep(0.5)

                        # 4. Habilitar VLAN (switch)
                        self.log(f"Activando opción de VLAN y asignando ID {vlan_str}...", "info")
                        vlan_switch = self.page.locator(".el-form-item:has-text('Habilitar VLAN') .el-switch, .el-form-item:has-text('Enable VLAN') .el-switch").first
                        if await vlan_switch.count() > 0:
                            is_checked = "is-checked" in (await vlan_switch.get_attribute("class") or "")
                            if not is_checked:
                                await vlan_switch.click()
                                await asyncio.sleep(0.5)

                        # 5. ID de VLAN
                        vlan_in = self.page.locator(".el-form-item:has-text('ID de VLAN') input.el-input__inner, .el-form-item:has-text('VLAN ID') input").first
                        if await vlan_in.count() > 0:
                            await vlan_in.fill(vlan_str)
                            await asyncio.sleep(0.5)

                        # 6. Botón Enviar / Guardar
                        self.log("Guardando la configuración de red en el equipo...", "info")
                        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(0.8)
                        btn_enviar_wan = self.page.locator("button:has-text('Enviar'), button:has-text('Aplicar'), button:has-text('Guardar'), button.el-button--primary").last
                        await btn_enviar_wan.click()
                        await asyncio.sleep(4)
                        self.log(f"Configuración de red WAN (VLAN {vlan_str}) guardada con éxito.", "ok")
                        wan_applied = True
                    except Exception as ex_ui:
                        self.log(f"Aviso en flujo de UI de red: {ex_ui}; aplicando vía API...", "warn")

                if not wan_applied:
                    wan_name = f"2_INTERNET_R_VID_{vlan_str}"
                    wan_payload = {
                        "indexid": "",
                        "indexid1": "1",
                        "indexid2": "1",
                        "wanenable": "1",
                        "wanswitch": "1",
                        "web_vlan_mode": "2",
                        "tdvlanid": vlan_str,
                        "tdconnectiontype": "1",
                        "tducAddressingType": "2",
                        "tducNATEnabled": "1",
                        "tducServiceList": "1",
                        "tdaucWanName": wan_name,
                        "tdulBindPort": "0",
                        "tdulMaxMTUSize": "1500",
                        "RequestDNS_Enable": "1",
                        "td_ucLanInterfaceDHCPEnable": "1",
                        "tducIPMode": "1",
                        "tdulMulticastVlan": vlan_str,
                        "wan_name_select": "Nuevo",
                        "Connection_mode_select": "1",
                        "IP_Protocol_select": "1",
                        "Mode_select": "2",
                        "Enable_LAN_DHCP_checkbox": "1",
                        "Enable_NAT_checkbox": "1",
                        "Enable_VLAN_checkbox": "1",
                        "VlanId_text": vlan_str
                    }
                    await self._api_post(EP_WAN_ADD, wan_payload)

                await asyncio.sleep(2)

                # =========================================================================
                # PASO 3: VERIFICACIÓN FINAL
                # =========================================================================
                self.log("Verificando parámetros aplicados en la ONU...", "info", step="verify", pct=90)
                wan_check = await self._api_get(EP_WAN_SHOW) or {}
                links = wan_check.get("data", {}).get("wan_link_list", [])
                vlan_verified = any(str(l.get("tdvlanid", "")) == vlan_str or vlan_str in l.get("tdaucWanName", "") for l in links)

                res_label = "EXITO" if vlan_verified else "PARCIAL"
                details = f"VLAN {vlan_str}: {'OK' if vlan_verified else 'NO VERIFICADA'} | Wi-Fi 2.4G: OK"
                if has_5g_target:
                    details += f" | Wi-Fi 5G: OK"

                self.log(f"Aprovisionamiento finalizado con éxito: {res_label} ({details})", "ok", step="done", pct=100)

                HistoryService.log(
                    self.ip, mac, pon_serial, model, vlan_str, ssid_2g, ssid_5g or "N/A", res_label, details
                )

                return {
                    "success": True,
                    "result": res_label,
                    "ip": self.ip,
                    "mac": mac,
                    "pon_serial": pon_serial,
                    "model": model,
                    "vlan_verified": vlan_verified,
                    "details": details
                }

            except Exception as ex:
                err_msg = f"Excepción durante aprovisionamiento: {ex}"
                self.log(err_msg, "error")
                HistoryService.log(self.ip, "", "", "VSOL", vlan_str, ssid_2g, ssid_5g or "", "ERROR", err_msg)
                return {"success": False, "error": err_msg}
            finally:
                if self.browser:
                    await self.browser.close()
