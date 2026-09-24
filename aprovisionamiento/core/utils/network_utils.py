# -*- coding: utf-8 -*-
"""
network_utils.py — Funciones de red, sondeo HTTP y manejo de cabeceras Host.
"""
import asyncio
import urllib.request

DEFAULT_MGMT_IP = "192.168.1.1"


async def check_http_alive(ip: str, timeout: int = 6) -> bool:
    """Verifica si el puerto web de la ONU responde."""
    try:
        def _probe():
            req = urllib.request.Request(
                f"http://{ip}/",
                headers={"Host": DEFAULT_MGMT_IP, "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status in (200, 302, 401, 403)
        return await asyncio.to_thread(_probe)
    except Exception:
        return False
