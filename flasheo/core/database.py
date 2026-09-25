# -*- coding: utf-8 -*-
"""
core.database — Capa de Base de Datos y Servicios ORM con SQLAlchemy.
Implementa:
  - Motor SQLite optimizado con WAL (Write-Ahead Logging).
  - Inicialización automática de tablas y semillas de seguridad.
  - Relación Lotes <-> Credenciales <-> ONUs flasheadas.
  - Consulta rápida de credenciales para aplicaciones externas.
  - Control de acceso basado en roles (RBAC).
"""
import hashlib
import json
import os
import re
import secrets
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker, Session, scoped_session

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CORE_DIR) if os.path.basename(CORE_DIR) == "core" else CORE_DIR
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
DB_PATH = os.path.join(CONFIG_DIR, "estacion_flasheo.db")

for d in [CONFIG_DIR, LOGS_DIR]:
    os.makedirs(d, exist_ok=True)

from core.models import Base, Usuario, ModeloONU, LoteCaja, ONU

# Configuración del motor SQLAlchemy con SQLite
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
    echo=False,
)

# Activar WAL mode en SQLite para máxima concurrencia y cero locks
with engine.connect() as conn:
    try:
        conn.exec_driver_sql("PRAGMA journal_mode = WAL")
        conn.exec_driver_sql("PRAGMA synchronous = NORMAL")
    except Exception:
        pass

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def get_db():
    """Generador de sesiones para FastAPI Depends(get_db)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """Retorna una sesión directa para scripts y llamadas en segundo plano."""
    return SessionLocal()


# ============================================================================
# SEGURIDAD Y HASHING
# ============================================================================
def hash_password(password: str) -> str:
    """Genera hash SHA-256 con sal para compatibilidad multiplataforma instantánea."""
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}:{h}"


def verify_password(plain_password: str, hashed_password: str, salt: str = "") -> bool:
    """Verifica si la contraseña plana coincide con el hash almacenado."""
    if not hashed_password:
        return False
    if salt:
        return hashlib.sha256((salt + plain_password).encode("utf-8")).hexdigest() == hashed_password
    if ":" in hashed_password:
        salt_part, h = hashed_password.split(":", 1)
        return hashlib.sha256((salt_part + plain_password).encode("utf-8")).hexdigest() == h
    # Compatibilidad con hashes planos anteriores o passwords temporales
    return hashlib.sha256(plain_password.encode("utf-8")).hexdigest() == hashed_password or plain_password == hashed_password


# ============================================================================
# INICIALIZACIÓN Y SEMILLAS
# ============================================================================
def _auto_migrate():
    """Garantiza que todas las columnas existan en bases de datos SQLite preexistentes."""
    with engine.connect() as conn:
        try:
            # Tabla usuarios
            res_u = conn.exec_driver_sql("PRAGMA table_info(usuarios)").fetchall()
            cols_u = [r[1] for r in res_u]
            if "created_at" not in cols_u:
                conn.exec_driver_sql("ALTER TABLE usuarios ADD COLUMN created_at DATETIME")
            if "salt" not in cols_u:
                conn.exec_driver_sql("ALTER TABLE usuarios ADD COLUMN salt TEXT DEFAULT ''")
            
            # Tabla modelos_onu
            res_m = conn.exec_driver_sql("PRAGMA table_info(modelos_onu)").fetchall()
            cols_m = [r[1] for r in res_m]
            if "firmware_default" not in cols_m:
                conn.exec_driver_sql("ALTER TABLE modelos_onu ADD COLUMN firmware_default TEXT DEFAULT ''")
                if "firmware_filename" in cols_m:
                    conn.exec_driver_sql("UPDATE modelos_onu SET firmware_default = firmware_filename WHERE firmware_default = '' OR firmware_default IS NULL")
            if "candidate_credentials_json" not in cols_m:
                conn.exec_driver_sql("ALTER TABLE modelos_onu ADD COLUMN candidate_credentials_json TEXT DEFAULT '[]'")
                if "candidate_credentials" in cols_m:
                    conn.exec_driver_sql("UPDATE modelos_onu SET candidate_credentials_json = candidate_credentials WHERE candidate_credentials_json = '[]' OR candidate_credentials_json IS NULL")
            if "box_default_qty" not in cols_m:
                conn.exec_driver_sql("ALTER TABLE modelos_onu ADD COLUMN box_default_qty INTEGER DEFAULT 20")

            # Tabla lotes_cajas
            res_l = conn.exec_driver_sql("PRAGMA table_info(lotes_cajas)").fetchall()
            cols_l = [r[1] for r in res_l]
            for col, ctype in [
                ("firmware_asignado", "TEXT DEFAULT ''"),
                ("usuario_asignado", "TEXT DEFAULT 'Powerlink'"),
                ("cantidad_procesadas", "INTEGER DEFAULT 0"),
                ("cantidad_exitosas", "INTEGER DEFAULT 0"),
                ("cantidad_fallidas", "INTEGER DEFAULT 0"),
                ("es_activo", "BOOLEAN DEFAULT 0"),
                ("fecha_inicio", "DATETIME"),
            ]:
                if col not in cols_l:
                    conn.exec_driver_sql(f"ALTER TABLE lotes_cajas ADD COLUMN {col} {ctype}")

                        # Tabla onus_flasheadas
            res_o = conn.exec_driver_sql("PRAGMA table_info(onus_flasheadas)").fetchall()
            cols_o = [r[1] for r in res_o]
            for col, ctype in [
                ("station_id", "TEXT DEFAULT 'ESTACION-GALPON-01'"),
                ("sync_status", "TEXT DEFAULT 'PENDING'"),
                ("synced_at", "DATETIME"),
            ]:
                if col not in cols_o:
                    conn.exec_driver_sql(f"ALTER TABLE onus_flasheadas ADD COLUMN {col} {ctype}")

            conn.commit()
        except Exception as ex:
            print(f"[DB] Auto-migracion nota: {ex}")


def init_db():
    """Crea las tablas y carga datos base si la BD es nueva."""
    _auto_migrate()
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        _seed_usuarios(session)
        _seed_modelos(session)
        _seed_lotes(session)
        session.commit()
    except Exception as ex:
        session.rollback()
        print(f"[DB] Error inicializando base de datos: {ex}")
    finally:
        session.close()


def _seed_usuarios(session: Session):
    if session.query(Usuario).count() == 0:
        usuarios_default = [
            Usuario(
                username="admin",
                password_hash=hash_password("admin2026*"),
                rol="admin",
                nombre_completo="Administrador Principal",
                activo=True,
            ),
            Usuario(
                username="operador",
                password_hash=hash_password("operador123"),
                rol="configurador",
                nombre_completo="Técnico de Flasheo",
                activo=True,
            ),
            Usuario(
                username="lector",
                password_hash=hash_password("lector123"),
                rol="visualizador",
                nombre_completo="Auditor de Calidad",
                activo=True,
            ),
        ]
        session.add_all(usuarios_default)


def _seed_modelos(session: Session):
    profiles_json = os.path.join(CONFIG_DIR, "onu_profiles.json")
    models_data = {}
    if os.path.exists(profiles_json):
        try:
            with open(profiles_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                models_data = data.get("models", {})
        except Exception:
            pass

    # Modelos por defecto
    defaults = {
        "V2801S-B": {
            "marca": "VSOL",
            "modelo": "V2801S-B",
            "nombre_comercial": "VSOL V2801S-B ONU 1GE",
            "descripcion": "ONU 1 Puerto Gigabit Ethernet Bridge / Router",
            "tipo_hardware": "1GE G/EPON",
            "icono": "⚡",
            "badge_color": "#3b82f6",
            "firmware_default": "V2801D-B_all_V6.1.4-260805_powerlink_GPON.bin",
            "has_wizard": False,
            "target_wan_name": "1_TR069_INTERNET_R_VID_3",
            "target_vlan_id": "3",
            "candidate_credentials": [
                ["admin", "admin"],
                ["admin", "Redes2010"],
                ["admin", "stdONU101"],
                ["admin", "admin123"],
                ["user", "user"],
                ["telecomadmin", "admintelecom"],
                ["Powerlink", "Powerlink2026*"],
            ],
            "box_default_qty": 20,
        },
        "V2804AX30-H": {
            "marca": "VSOL",
            "modelo": "V2804AX30-H",
            "nombre_comercial": "VSOL Wi-Fi 6 AX3000 (4GE + 1POTS)",
            "descripcion": "Router ONU Wi-Fi 6 AX3000 Doble Banda",
            "tipo_hardware": "Wi-Fi 6 AX3000",
            "icono": "📡",
            "badge_color": "#8b5cf6",
            "firmware_default": "HG3232AXT-H_all_V1.1.00-20260610_LupoverPowerlinkver.bin",
            "has_wizard": True,
            "target_wan_name": "1_TR069_INTERNET_R_VID_3",
            "target_vlan_id": "3",
            "candidate_credentials": [
                ["admin", "stdONU101"],
                ["admin", "admin123"],
                ["Powerlink", "Powerlink2026*"],
                ["user", "user"],
                ["admin", "admin"],
            ],
            "box_default_qty": 20,
        },
    }

    # Mezclar con json si existe
    for m_id, m_dict in models_data.items():
        if m_id not in defaults:
            defaults[m_id] = {
                "marca": m_dict.get("marca", "VSOL"),
                "modelo": m_dict.get("modelo", m_id),
                "nombre_comercial": m_dict.get("name") or m_dict.get("commercial_name", m_id),
                "descripcion": m_dict.get("descripcion", ""),
                "tipo_hardware": m_dict.get("hardware_type", ""),
                "icono": m_dict.get("icon", "📡"),
                "badge_color": m_dict.get("badge_color", "#3b82f6"),
                "firmware_default": m_dict.get("firmware", ""),
                "has_wizard": bool(m_dict.get("has_wizard", False)),
                "target_wan_name": m_dict.get("target_wan_name", "1_TR069_INTERNET_R_VID_3"),
                "target_vlan_id": m_dict.get("target_vlan_id", "3"),
                "candidate_credentials": m_dict.get("candidate_credentials", []),
                "box_default_qty": m_dict.get("box_default_qty", 20),
            }

    for m_id, item in defaults.items():
        existing = session.query(ModeloONU).filter_by(id=m_id).first()
        cand_json = json.dumps(item.get("candidate_credentials", []))
        if not existing:
            mod = ModeloONU(
                id=m_id,
                marca=item["marca"],
                modelo=item["modelo"],
                nombre_comercial=item["nombre_comercial"],
                descripcion=item["descripcion"],
                tipo_hardware=item["tipo_hardware"],
                icono=item["icono"],
                badge_color=item["badge_color"],
                firmware_default=item["firmware_default"],
                has_wizard=item["has_wizard"],
                target_wan_name=item["target_wan_name"],
                target_vlan_id=item["target_vlan_id"],
                candidate_credentials_json=cand_json,
                box_default_qty=item["box_default_qty"],
                activo=True,
            )
            session.add(mod)


def _seed_lotes(session: Session):
    if session.query(LoteCaja).count() == 0:
        lote_inicial = LoteCaja(
            codigo_lote="LOTE-2026-01",
            numero_caja="Caja #1",
            descripcion="Lote de inicio estándar 20 ONUs",
            modelo_id="V2801S-B",
            firmware_asignado="V2801D-B_all_V6.1.4-260805_powerlink_GPON.bin",
            clave_asignada="Powerlink2026*",
            usuario_asignado="Powerlink",
            cantidad_total=20,
            cantidad_procesadas=0,
            cantidad_exitosas=0,
            estado="EN_PROCESO",
            es_activo=True,
        )
        session.add(lote_inicial)


# ============================================================================
# SERVICIOS DE AUTENTICACIÓN Y USUARIOS
# ============================================================================
def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    session = SessionLocal()
    try:
        user = session.query(Usuario).filter(Usuario.username == username, Usuario.activo == True).first()
        if user and verify_password(password, user.password_hash, getattr(user, "salt", "") or ""):
            return user.to_dict()
        return None
    finally:
        session.close()


def list_users() -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        users = session.query(Usuario).all()
        return [u.to_dict() for u in users]
    finally:
        session.close()


def create_user(username: str, password: str, rol: str = "configurador", nombre_completo: str = ""):
    session = SessionLocal()
    try:
        if session.query(Usuario).filter_by(username=username).first():
            return False, f"El usuario '{username}' ya existe."
        user = Usuario(
            username=username.strip(),
            password_hash=hash_password(password.strip()),
            rol=rol,
            nombre_completo=nombre_completo.strip(),
            activo=True,
        )
        session.add(user)
        session.commit()
        return True, f"Usuario '{username}' creado exitosamente."
    except Exception as ex:
        session.rollback()
        return False, str(ex)
    finally:
        session.close()


# ============================================================================
# SERVICIOS DE LOTES / CAJAS Y CLAVES
# ============================================================================
def get_active_lote(session: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True
    try:
        lote = session.query(LoteCaja).filter_by(es_activo=True).first()
        if not lote:
            lote = session.query(LoteCaja).order_by(LoteCaja.id.desc()).first()
        return lote.to_dict(include_clave=True) if lote else None
    finally:
        if close_session:
            session.close()


def list_lotes(include_clave=False) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        lotes = session.query(LoteCaja).order_by(LoteCaja.id.desc()).all()
        return [l.to_dict(include_clave=include_clave) for l in lotes]
    finally:
        session.close()


def create_lote(numero_caja: str, codigo_lote: str, modelo_id: str, firmware: str, clave_asignada: str, cantidad_total: int = 20, descripcion: str = ""):
    session = SessionLocal()
    try:
        if session.query(LoteCaja).filter_by(codigo_lote=codigo_lote).first():
            return False, f"El lote '{codigo_lote}' ya existe."
        
        # Desactivar anteriores si se marca activo
        session.query(LoteCaja).update({"es_activo": False})
        
        lote = LoteCaja(
            numero_caja=numero_caja.strip(),
            codigo_lote=codigo_lote.strip(),
            modelo_id=modelo_id,
            firmware_asignado=firmware,
            clave_asignada=clave_asignada.strip() or "Powerlink2026*",
            usuario_asignado="Powerlink",
            cantidad_total=cantidad_total,
            descripcion=descripcion.strip(),
            es_activo=True,
            estado="EN_PROCESO",
        )
        session.add(lote)
        session.commit()
        return True, f"Lote '{codigo_lote}' ({numero_caja}) creado y activado."
    except Exception as ex:
        session.rollback()
        return False, str(ex)
    finally:
        session.close()


def set_active_lote(lote_id: int):
    session = SessionLocal()
    try:
        lote = session.query(LoteCaja).filter_by(id=lote_id).first()
        if not lote:
            return False, "Lote no encontrado."
        session.query(LoteCaja).update({"es_activo": False})
        lote.es_activo = True
        session.commit()
        return True, f"Lote '{lote.codigo_lote}' activado para flasheo."
    except Exception as ex:
        session.rollback()
        return False, str(ex)
    finally:
        session.close()


# ============================================================================
# REGISTRO Y CONSULTA DE ONUs (API EXTERNA Y REPORTE)
# ============================================================================
def log_onu_flash(
    mac: str,
    pon_original: str,
    pon_sn: str,
    modelo_id: str,
    resultado: str,
    vlan3_ok: str = "NO",
    firmware: str = "",
    puerto: str = "",
    ip: str = "",
    detalles: str = "",
    duracion_seg: int = 0,
    captura_path: str = "",
    operador_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Registra una ONU flasheada, vinculándola automáticamente al lote activo
    y a la credencial configurada en ese lote.
    """
    session = SessionLocal()
    try:
        active_lote = session.query(LoteCaja).filter_by(es_activo=True).first()
        lote_id = active_lote.id if active_lote else None
        
        clave_asignada = active_lote.clave_asignada if active_lote else "Powerlink2026*"
        usuario_asignado = active_lote.usuario_asignado if active_lote else "Powerlink"
        firmware_usado = firmware or (active_lote.firmware_asignado if active_lote else "")

        # Obtener station_id configurado para esta laptop
        try:
            from core.sync_client import StationSyncClient
            st_cfg = StationSyncClient.load_config()
            station_id = st_cfg.get("station_id", "ESTACION-GALPON-01")
        except Exception:
            station_id = "ESTACION-GALPON-01"

        onu = ONU(
            lote_id=lote_id,
            modelo_id=modelo_id,
            mac=mac.strip().upper(),
            pon_original=pon_original.strip(),
            pon_sn=pon_sn.strip().upper(),
            credencial_usuario=usuario_asignado,
            credencial_clave=clave_asignada,
            firmware_instalado=firmware_usado,
            puerto_mikrotik=str(puerto),
            ip=ip.strip(),
            resultado=resultado,
            vlan3_ok=vlan3_ok,
            detalles=detalles,
            duracion_segundos=duracion_seg,
            captura_path=captura_path,
            operador_id=operador_id,
            station_id=station_id,
            sync_status="PENDING",
            fecha_hora=datetime.now(),
        )
        session.add(onu)

        # Actualizar contadores del lote
        if active_lote:
            active_lote.cantidad_procesadas = (active_lote.cantidad_procesadas or 0) + 1
            if resultado in ("EXITO", "YA_CONFIGURADA", "LISTA"):
                active_lote.cantidad_exitosas = (active_lote.cantidad_exitosas or 0) + 1
            else:
                active_lote.cantidad_fallidas = (active_lote.cantidad_fallidas or 0) + 1
            if active_lote.cantidad_procesadas >= active_lote.cantidad_total:
                active_lote.estado = "COMPLETO"

        session.commit()

        # Disparar sincronización asíncrona hacia el servidor Intranet
        try:
            from core.sync_client import StationSyncClient
            StationSyncClient.sync_pending_async()
        except Exception as ex_sync:
            print(f"[SYNC] Aviso al sincronizar en background: {ex_sync}")

        return onu.to_dict(include_clave=True)
    except Exception as ex:
        session.rollback()
        print(f"[DB] Error registrando ONU: {ex}")
        return {}
    finally:
        session.close()


def lookup_onu_credentials(query: str) -> Optional[Dict[str, Any]]:
    """
    ENDPOINT DE CONSULTA PARA LA OTRA APLICACIÓN:
    Permite consultar por Dirección MAC o por Serial GPON (PON_SN / PON Original)
    y retorna la credencial exacta asignada a la ONU, su Lote y fecha.
    """
    session = SessionLocal()
    try:
        q = query.strip()
        q_clean = re.sub(r"[^0-9A-Za-z]", "", q).upper()

        # Buscar por coincidencias exactas o normalizadas
        onu = session.query(ONU).filter(
            or_(
                ONU.mac.ilike(f"%{q}%"),
                ONU.pon_sn.ilike(f"%{q}%"),
                ONU.pon_original.ilike(f"%{q}%"),
                ONU.mac.ilike(f"%{q_clean}%"),
                ONU.pon_sn.ilike(f"%{q_clean}%")
            )
        ).order_by(ONU.id.desc()).first()

        if onu:
            return {
                "encontrado": True,
                "mac": onu.mac,
                "pon_sn": onu.pon_sn,
                "pon_original": onu.pon_original,
                "modelo": onu.modelo_id,
                "credenciales": {
                    "usuario": onu.credencial_usuario,
                    "clave": onu.credencial_clave,
                },
                "lote": {
                    "codigo_lote": onu.lote.codigo_lote if onu.lote else None,
                    "numero_caja": onu.lote.numero_caja if onu.lote else None,
                    "estado_lote": onu.lote.estado if onu.lote else None,
                },
                "firmware": onu.firmware_instalado,
                "vlan3_verificada": onu.vlan3_ok,
                "fecha_flasheo": onu.fecha_hora.strftime("%Y-%m-%d %H:%M:%S") if onu.fecha_hora else "",
            }
        return None
    finally:
        session.close()


def list_onus(limit: int = 200, lote_id: Optional[int] = None, resultado: Optional[str] = None) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        q = session.query(ONU)
        if lote_id:
            q = q.filter(ONU.lote_id == lote_id)
        if resultado:
            q = q.filter(ONU.resultado == resultado)
        onus = q.order_by(ONU.id.desc()).limit(limit).all()
        return [o.to_dict(include_clave=True) for o in onus]
    finally:
        session.close()


# Inicializar automáticamente al importar
init_db()
