# -*- coding: utf-8 -*-
"""
base_onu.py — Clase base abstracta para adaptadores de ONUs.
Permite extender el sistema en el futuro para soportar otras marcas (Huawei, ZTE, Fiberhome, etc.).
"""
from abc import ABC, abstractmethod


class BaseONU(ABC):
    def __init__(self, ip, log_callback=None):
        self.ip = ip.strip()
        self.log_callback = log_callback or (lambda data: None)

    def log(self, message, level="info", step=None, pct=None):
        import time
        t = time.strftime("%H:%M:%S")
        self.log_callback({
            "time": t,
            "message": message,
            "level": level,
            "step": step,
            "pct": pct
        })

    @abstractmethod
    async def probe(self) -> dict:
        """Consulta y retorna información del hardware, potencia óptica, VLAN y Wi-Fi actual."""
        pass

    @abstractmethod
    async def provision(self, vlan_id: str, ssid_2g: str, pass_2g: str, ssid_5g: str = None, pass_5g: str = None) -> dict:
        """Ejecuta el aprovisionamiento completo (Wi-Fi primero, luego WAN con VLAN, luego verificación)."""
        pass
