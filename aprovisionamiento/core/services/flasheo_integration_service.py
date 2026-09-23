# -*- coding: utf-8 -*-
"""
flasheo_integration_service.py — Servicio de Integración con la Estación de Flasheo.
Permite a Aprovisionamiento Automático consultar la credencial exacta, lote y caja
de una ONU mediante arquitectura híbrida de alta disponibilidad:
  1. API REST de la Estación de Flasheo (http://localhost:8080/api/v1/onus/{query}/credentials)
  2. Fallback de lectura directa a la base de datos SQLite WAL (estacion_flasheo.db)
"""
import json
import os
import re
import sqlite3
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

FLASHEO_API_URL = "http://localhost:8000/api/flasheo/onus/{query}/credentials"
FLASHEO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FLASHEO_DB_PATH = os.path.join(FLASHEO_ROOT, "intranet_local.db")


class FlasheoIntegrationService:
    @staticmethod
    def lookup(query: str) -> Optional[Dict[str, Any]]:
        """
        Busca las credenciales y datos de lote de una ONU por MAC o Serial GPON.
        Primero intenta la API REST; si el servidor está apagado, lee SQLite directamente.
        """
        if not query or not str(query).strip():
            return None

        q = str(query).strip()

        # 1. Intentar API REST (HTTP)
        data = FlasheoIntegrationService._lookup_via_api(q)
        if data:
            return data

        # 2. Fallback directo a SQLite
        return FlasheoIntegrationService._lookup_via_sqlite(q)

    @staticmethod
    def _lookup_via_api(query: str) -> Optional[Dict[str, Any]]:
        try:
            url = FLASHEO_API_URL.format(query=urllib.parse.quote(query))
            req = urllib.request.Request(url, headers={"User-Agent": "AprovisionamientoAuto/2.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    if payload.get("encontrado"):
                        payload["origen_datos"] = "API_REST_8080"
                        return payload
        except Exception:
            pass
        return None

    @staticmethod
    def _lookup_via_sqlite(query: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(FLASHEO_DB_PATH):
            return None

        q_clean = re.sub(r"[^0-9A-Za-z]", "", query).upper()
        try:
            conn = sqlite3.connect(f"file:{FLASHEO_DB_PATH}?mode=ro", uri=True, timeout=3)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            sql = """
                SELECT o.*, l.codigo_lote, l.numero_caja, l.estado as estado_lote
                FROM onus_flasheadas o
                LEFT JOIN lotes_cajas l ON o.lote_id = l.id
                WHERE UPPER(o.mac) = ? OR UPPER(o.pon_sn) = ? OR UPPER(o.pon_original) = ?
                   OR UPPER(REPLACE(o.mac, ':', '')) = ? OR UPPER(REPLACE(o.pon_sn, '-', '')) = ?
                ORDER BY o.id DESC
                LIMIT 1
            """
            cur.execute(sql, (query.upper(), query.upper(), query.upper(), q_clean, q_clean))
            row = cur.fetchone()
            conn.close()

            if row:
                return {
                    "encontrado": True,
                    "origen_datos": "SQLITE_DIRECT",
                    "mac": row["mac"],
                    "pon_sn": row["pon_sn"],
                    "pon_original": row["pon_original"],
                    "modelo": row["modelo_id"],
                    "credenciales": {
                        "usuario": row["credencial_usuario"] or "Powerlink",
                        "clave": row["credencial_clave"] or "Powerlink2026*",
                    },
                    "lote": {
                        "codigo_lote": row["codigo_lote"],
                        "numero_caja": row["numero_caja"],
                        "estado_lote": row["estado_lote"],
                    },
                    "firmware": row["firmware_instalado"],
                    "vlan3_verificada": row["vlan3_ok"],
                    "fecha_flasheo": str(row["fecha_hora"]) if row["fecha_hora"] else "",
                }
        except Exception as ex:
            print(f"[FlasheoIntegration] Error leyendo SQLite: {ex}")

        return None
