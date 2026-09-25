# -*- coding: utf-8 -*-
"""
core.sync_client — Cliente de Sincronización Resiliente Servidor-Cliente (Intranet <-> Estaciones).
Permite a las laptops del galpón:
  1. Operar 100% offline cuando estén conectadas a ONUs o sin acceso de red.
  2. Guardar cada flasheo inmediatamente en su base de datos local SQLite.
  3. Detectar automáticamente cuando el servidor de la Intranet está disponible.
  4. Resincronizar todos los registros acumulados sin duplicidad (UPSERT central).
  5. Multi-estación: Enviar su identificador único (station_id) y metadatos.
"""
import json
import os
import re
import socket
import sqlite3
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional, Dict, List, Any

# Rutas del módulo
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CORE_DIR) if os.path.basename(CORE_DIR) == "core" else CORE_DIR
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "station_config.json")
DB_PATH = os.path.join(CONFIG_DIR, "estacion_flasheo.db")
if not os.path.exists(DB_PATH) and os.path.exists(os.path.join(PROJECT_ROOT, "intranet_local.db")):
    DB_PATH = os.path.join(PROJECT_ROOT, "intranet_local.db")

_BG_WORKER_THREAD = None
_BG_WORKER_RUNNING = False
_LAST_SYNC_TIME = None
_LAST_STATUS = "idle"


def get_local_ip() -> str:
    """Obtiene la dirección IP LAN preferida del host."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


class StationSyncClient:
    @staticmethod
    def load_config() -> dict:
        """Carga la configuración local de la estación."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        default_cfg = {
            "station_id": f"ESTACION-GALPON-01",
            "station_name": "Estación de Flasheo Laptop 1",
            "server_url": "http://127.0.0.1:8000",
            "auto_sync": True,
            "sync_interval_seconds": 15,
            "batch_size": 100,
            "hostname": socket.gethostname()
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_cfg.update(data)
            except Exception:
                pass
        return default_cfg

    @staticmethod
    def save_config(cfg: dict) -> bool:
        """Guarda la configuración actualizada de la estación."""
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            current = StationSyncClient.load_config()
            current.update(cfg)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=4, ensure_ascii=False)
            return True
        except Exception as ex:
            print(f"[SYNC CLIENT] Error guardando config: {ex}")
            return False

    @staticmethod
    def check_server_online(timeout: float = 2.0) -> bool:
        """Verifica si el servidor central de la Intranet está accesible."""
        cfg = StationSyncClient.load_config()
        base_url = cfg.get("server_url", "http://127.0.0.1:8000").rstrip("/")
        ping_url = f"{base_url}/api/flasheo/ping"

        try:
            req = urllib.request.Request(ping_url, headers={"User-Agent": "PowerlinkFlashStation/3.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass

        # Fallback al ping raíz si el sub-path fallara
        try:
            req_alt = urllib.request.Request(f"{base_url}/ping", headers={"User-Agent": "PowerlinkFlashStation/3.0"})
            with urllib.request.urlopen(req_alt, timeout=timeout) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass

        return False

    @staticmethod
    def get_pending_records(limit: int = 100) -> List[Dict[str, Any]]:
        """Obtiene de la base de datos SQLite local todas las ONUs pendientes de sincronizar."""
        if not os.path.exists(DB_PATH):
            return []

        records = []
        try:
            conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Verificar si la columna sync_status existe
            cur.execute("PRAGMA table_info(onus_flasheadas)")
            cols = [c[1] for c in cur.fetchall()]
            has_sync_status = "sync_status" in cols

            if has_sync_status:
                sql = """
                    SELECT o.*, l.codigo_lote, l.numero_caja
                    FROM onus_flasheadas o
                    LEFT JOIN lotes_cajas l ON o.lote_id = l.id
                    WHERE (o.sync_status IS NULL OR o.sync_status != 'SYNCED')
                    ORDER BY o.id ASC
                    LIMIT ?
                """
                cur.execute(sql, (limit,))
            else:
                # Si aún no tiene columna, todas se consideran pendientes para migrar
                sql = """
                    SELECT o.*, l.codigo_lote, l.numero_caja
                    FROM onus_flasheadas o
                    LEFT JOIN lotes_cajas l ON o.lote_id = l.id
                    ORDER BY o.id ASC
                    LIMIT ?
                """
                cur.execute(sql, (limit,))

            for row in cur.fetchall():
                records.append(dict(row))
            conn.close()
        except Exception as ex:
            print(f"[SYNC CLIENT] Error leyendo pendientes de SQLite: {ex}")

        return records

    @staticmethod
    def mark_records_synced(record_ids: List[int]) -> bool:
        """Marca en la base de datos local SQLite los registros como sincronizados."""
        if not record_ids or not os.path.exists(DB_PATH):
            return True

        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cur = conn.cursor()
            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            # Asegurar que las columnas existen en la BD local
            cur.execute("PRAGMA table_info(onus_flasheadas)")
            cols = [c[1] for c in cur.fetchall()]
            if "sync_status" not in cols:
                cur.execute("ALTER TABLE onus_flasheadas ADD COLUMN sync_status VARCHAR(20) DEFAULT 'PENDING'")
            if "synced_at" not in cols:
                cur.execute("ALTER TABLE onus_flasheadas ADD COLUMN synced_at DATETIME")
            if "station_id" not in cols:
                cur.execute("ALTER TABLE onus_flasheadas ADD COLUMN station_id VARCHAR(50)")

            placeholders = ",".join(["?"] * len(record_ids))
            cur.execute(
                f"UPDATE onus_flasheadas SET sync_status = 'SYNCED', synced_at = ? WHERE id IN ({placeholders})",
                [now_str] + record_ids
            )
            conn.commit()
            conn.close()
            return True
        except Exception as ex:
            print(f"[SYNC CLIENT] Error actualizando estado de sync en local: {ex}")
            return False

    @staticmethod
    def sync_pending_records() -> Dict[str, Any]:
        """
        Ejecuta el ciclo de sincronización de registros pendientes hacia la Intranet:
        1. Consulta pendientes en SQLite local.
        2. Verifica que el servidor de Intranet esté online.
        3. Envía el batch por POST HTTP.
        4. Actualiza los registros locales como SYNCED.
        """
        global _LAST_SYNC_TIME, _LAST_STATUS

        cfg = StationSyncClient.load_config()
        station_id = cfg.get("station_id", "ESTACION-GALPON-01")
        server_url = cfg.get("server_url", "http://127.0.0.1:8000").rstrip("/")
        batch_size = cfg.get("batch_size", 100)

        pending = StationSyncClient.get_pending_records(limit=batch_size)
        if not pending:
            _LAST_STATUS = "idle"
            return {
                "status": "idle",
                "synced_count": 0,
                "pending_count": 0,
                "message": "No hay registros pendientes de sincronizar.",
                "station_id": station_id
            }

        # Verificar conectividad con la Intranet
        if not StationSyncClient.check_server_online():
            _LAST_STATUS = "offline"
            return {
                "status": "offline",
                "synced_count": 0,
                "pending_count": len(pending),
                "message": f"Servidor Intranet no accesible ({server_url}). Registros en cola local (Offline).",
                "station_id": station_id
            }

        # Preparar payload JSON
        records_payload = []
        record_ids = []
        for p in pending:
            record_ids.append(p["id"])
            records_payload.append({
                "mac": p.get("mac") or "",
                "pon_sn": p.get("pon_sn") or "",
                "pon_original": p.get("pon_original") or "",
                "modelo_id": p.get("modelo_id") or "V2801S-B",
                "codigo_lote": p.get("codigo_lote") or "",
                "numero_caja": p.get("numero_caja") or "",
                "credencial_usuario": p.get("credencial_usuario") or "Powerlink",
                "credencial_clave": p.get("credencial_clave") or "Powerlink2026*",
                "firmware_instalado": p.get("firmware_instalado") or "",
                "puerto_mikrotik": str(p.get("puerto_mikrotik") or ""),
                "ip": p.get("ip") or "",
                "resultado": p.get("resultado") or "EXITO",
                "vlan3_ok": p.get("vlan3_ok") or "NO",
                "detalles": p.get("detalles") or "",
                "duracion_segundos": p.get("duracion_segundos") or 0,
                "captura_path": p.get("captura_path") or "",
                "fecha_hora": str(p.get("fecha_hora") or "")
            })

        payload = {
            "station_id": station_id,
            "station_name": cfg.get("station_name", "Estación de Flasheo Laptop"),
            "hostname": socket.gethostname(),
            "ip_address": get_local_ip(),
            "records": records_payload
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            sync_url = f"{server_url}/api/flasheo/sync/onus"
            req = urllib.request.Request(
                sync_url,
                data=req_data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "PowerlinkFlashStation/3.0"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=10.0) as resp:
                if resp.status == 200:
                    resp_body = json.loads(resp.read().decode("utf-8"))
                    # Marcar registros locales como sincronizados
                    StationSyncClient.mark_records_synced(record_ids)
                    _LAST_SYNC_TIME = datetime.utcnow()
                    _LAST_STATUS = "synced"
                    synced_count = resp_body.get("synced_count", len(record_ids))
                    print(f"[SYNC CLIENT] Sincronización exitosa: {synced_count} registros subidos a la Intranet.")
                    return {
                        "status": "success",
                        "synced_count": synced_count,
                        "pending_count": 0,
                        "message": f"Sincronizados {synced_count} registros correctamente con la Intranet.",
                        "station_id": station_id,
                        "server_time": resp_body.get("server_time")
                    }
                else:
                    _LAST_STATUS = "error"
                    return {
                        "status": "error",
                        "synced_count": 0,
                        "pending_count": len(pending),
                        "message": f"Servidor respondió con código {resp.status}."
                    }
        except Exception as ex:
            _LAST_STATUS = "offline"
            print(f"[SYNC CLIENT] Error durante sincronización con Intranet: {ex}")
            return {
                "status": "error",
                "synced_count": 0,
                "pending_count": len(pending),
                "message": f"Fallo al conectar con la Intranet: {ex}",
                "station_id": station_id
            }

    @staticmethod
    def sync_pending_async():
        """Lanza la sincronización en un hilo secundario sin congelar el proceso de flasheo."""
        threading.Thread(target=StationSyncClient.sync_pending_records, daemon=True).start()

    @staticmethod
    def get_status() -> Dict[str, Any]:
        """Retorna el estado de sincronización y métricas de la estación."""
        cfg = StationSyncClient.load_config()
        is_online = StationSyncClient.check_server_online(timeout=1.0)
        
        pending_count = 0
        total_count = 0
        if os.path.exists(DB_PATH):
            try:
                conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2)
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM onus_flasheadas")
                total_count = cur.fetchone()[0]
                cur.execute("PRAGMA table_info(onus_flasheadas)")
                cols = [c[1] for c in cur.fetchall()]
                if "sync_status" in cols:
                    cur.execute("SELECT COUNT(*) FROM onus_flasheadas WHERE sync_status != 'SYNCED' OR sync_status IS NULL")
                    pending_count = cur.fetchone()[0]
                conn.close()
            except Exception:
                pass

        return {
            "station_id": cfg.get("station_id", "ESTACION-GALPON-01"),
            "station_name": cfg.get("station_name", "Estación Laptop"),
            "server_url": cfg.get("server_url", "http://127.0.0.1:8000"),
            "auto_sync": cfg.get("auto_sync", True),
            "is_online": is_online,
            "status": "ONLINE" if is_online else "OFFLINE",
            "pending_count": pending_count,
            "total_flashed": total_count,
            "synced_count": max(0, total_count - pending_count),
            "last_sync": _LAST_SYNC_TIME.strftime("%Y-%m-%d %H:%M:%S") if _LAST_SYNC_TIME else "Nunca"
        }


def _background_sync_loop():
    """Bucle demonio que intenta sincronizar periódicamente cuando la Intranet está disponible."""
    global _BG_WORKER_RUNNING
    _BG_WORKER_RUNNING = True
    print("[SYNC CLIENT] Demonio de sincronización en segundo plano iniciado.")
    while _BG_WORKER_RUNNING:
        try:
            cfg = StationSyncClient.load_config()
            interval = cfg.get("sync_interval_seconds", 15)
            if cfg.get("auto_sync", True):
                StationSyncClient.sync_pending_records()
            time.sleep(interval)
        except Exception as ex:
            time.sleep(10)


def start_background_sync():
    """Inicia el demonio de sincronización automática en segundo plano."""
    global _BG_WORKER_THREAD
    if _BG_WORKER_THREAD is None or not _BG_WORKER_THREAD.is_alive():
        _BG_WORKER_THREAD = threading.Thread(target=_background_sync_loop, daemon=True)
        _BG_WORKER_THREAD.start()


# Alias conveniente
sincronizar_con_intranet = StationSyncClient.sync_pending_records
