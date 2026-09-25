import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="user") # "admin" (RRHH) or "user"
    permissions = Column(String, default="") # e.g. "cargar_datos_usuarios,ver_integracion"
    avatar_url = Column(String, default="/static/img/default-avatar.png")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    link_url = Column(String, default="#")
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False) # "Solicitudes", "Aplicaciones", "Plantillas", "Manual Empleado"
    file_path = Column(String, nullable=False)
    file_type = Column(String, default="pdf")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    apellido = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    cedula = Column(String, unique=True, index=True, nullable=True)
    position = Column(String, nullable=True)
    department = Column(String, default="General")
    photo_url = Column(String, nullable=True)
    birthday_date = Column(String, nullable=True) # e.g. "18 de Julio"

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

class KpiMetric(Base):
    __tablename__ = "kpi_metrics"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    value = Column(String, nullable=False)
    trend = Column(String, default="up") # "up", "down", "neutral"
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class PopupNotification(Base):
    __tablename__ = "popup_notifications"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Integer, nullable=False)
    month = Column(Integer, default=7)
    year = Column(Integer, default=2026)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, nullable=False)
    user_name = Column(String, nullable=False)
    channel = Column(String, default="#General")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ChatReadState(Base):
    __tablename__ = "chat_read_states"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, index=True, nullable=False)
    channel = Column(String, index=True, nullable=False)
    last_read_timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class PhoneExtension(Base):
    __tablename__ = 'phone_extensions'

    id = Column(Integer, primary_key=True, index=True)
    department = Column(String, index=True)
    name = Column(String)
    extension = Column(String)
    is_group = Column(Boolean, default=False)

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(String, index=True, nullable=False, unique=True)
    cedula = Column(String, index=True, nullable=True)
    name = Column(String, nullable=False)
    client_type = Column(String, default="Residencial") # Residencial, Corporativo
    current_plan = Column(String, nullable=True)
    status = Column(String, nullable=True)
    installation_date = Column(String, nullable=True)
    last_status_change_date = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    histories = relationship("ClientHistory", back_populates="client")

class ClientHistory(Base):
    __tablename__ = "client_history"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    record_date = Column(DateTime, nullable=False, index=True) # The date of the excel file or sweep
    event_type = Column(String, nullable=False) # e.g. STATUS_CHANGE, PLAN_CHANGE
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    client = relationship("Client", back_populates="histories")

# ==========================================
# MODELOS DE FLASHEO Y APROVISIONAMIENTO
# ==========================================

class FlasheoUsuario(Base):
    __tablename__ = "flasheo_usuarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    salt = Column(String(64), default="")
    rol = Column(String(20), nullable=False, default="configurador")  # admin, configurador, visualizador
    nombre_completo = Column(String(100), default="")
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relaciones
    onus_procesadas = relationship("ONU", back_populates="operador")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "rol": self.rol,
            "nombre_completo": self.nombre_completo,
            "activo": self.activo,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class ModeloONU(Base):
    __tablename__ = "modelos_onu"

    id = Column(String(50), primary_key=True)  # ej. 'V2801S-B', 'V2804AX30-H'
    marca = Column(String(50), default="VSOL")
    modelo = Column(String(50), nullable=False)
    nombre_comercial = Column(String(120), default="")
    descripcion = Column(Text, default="")
    tipo_hardware = Column(String(60), default="")
    icono = Column(String(10), default="??")
    badge_color = Column(String(20), default="#3b82f6")
    firmware_default = Column(String(150), default="")
    has_wizard = Column(Boolean, default=False)
    upload_endpoint = Column(String(150), default="/boaform/web_form_upload_file.cgi")
    target_wan_name = Column(String(100), default="1_TR069_INTERNET_R_VID_3")
    target_vlan_id = Column(String(20), default="3")
    candidate_credentials_json = Column(Text, default="[]")
    box_default_qty = Column(Integer, default=20)
    activo = Column(Boolean, default=True)

    # Relaciones
    lotes = relationship("LoteCaja", back_populates="modelo")
    onus = relationship("ONU", back_populates="modelo")

    def to_dict(self):
        import json
        try:
            candidates = json.loads(self.candidate_credentials_json or "[]")
        except Exception:
            candidates = []
        return {
            "id": self.id,
            "marca": self.marca,
            "modelo": self.modelo,
            "nombre_comercial": self.nombre_comercial or self.modelo,
            "descripcion": self.descripcion,
            "tipo_hardware": self.tipo_hardware,
            "icono": self.icono,
            "badge_color": self.badge_color,
            "firmware_default": self.firmware_default,
            "has_wizard": self.has_wizard,
            "upload_endpoint": self.upload_endpoint,
            "target_wan_name": self.target_wan_name,
            "target_vlan_id": self.target_vlan_id,
            "candidate_credentials": candidates,
            "box_default_qty": self.box_default_qty,
            "activo": self.activo,
        }

class LoteCaja(Base):
    __tablename__ = "lotes_cajas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_lote = Column(String(60), unique=True, nullable=False, index=True)
    numero_caja = Column(String(60), nullable=False)
    descripcion = Column(String(200), default="")
    modelo_id = Column(String(50), ForeignKey("modelos_onu.id"), nullable=False)
    firmware_asignado = Column(String(150), default="")
    clave_asignada = Column(String(100), default="Powerlink2026*")
    usuario_asignado = Column(String(50), default="Powerlink")
    cantidad_total = Column(Integer, default=20)
    cantidad_procesadas = Column(Integer, default=0)
    cantidad_exitosas = Column(Integer, default=0)
    cantidad_fallidas = Column(Integer, default=0)
    estado = Column(String(30), default="EN_PROCESO")  # EN_PROCESO, COMPLETO, CERRADO
    es_activo = Column(Boolean, default=False)
    fecha_inicio = Column(DateTime, default=datetime.datetime.utcnow)
    fecha_cierre = Column(DateTime, nullable=True)

    # Relaciones
    modelo = relationship("ModeloONU", back_populates="lotes")
    onus = relationship("ONU", back_populates="lote")

    def to_dict(self, include_clave=False):
        return {
            "id": self.id,
            "codigo_lote": self.codigo_lote,
            "numero_caja": self.numero_caja,
            "descripcion": self.descripcion,
            "modelo_id": self.modelo_id,
            "modelo_nombre": self.modelo.nombre_comercial if self.modelo else self.modelo_id,
            "firmware_asignado": self.firmware_asignado,
            "usuario_asignado": self.usuario_asignado,
            "clave_asignada": self.clave_asignada if include_clave else "********",
            "cantidad_total": self.cantidad_total,
            "cantidad_procesadas": self.cantidad_procesadas,
            "cantidad_exitosas": self.cantidad_exitosas,
            "cantidad_fallidas": self.cantidad_fallidas,
            "estado": self.estado,
            "es_activo": self.es_activo,
            "fecha_inicio": self.fecha_inicio.strftime("%Y-%m-%d %H:%M:%S") if self.fecha_inicio else "",
            "fecha_cierre": self.fecha_cierre.strftime("%Y-%m-%d %H:%M:%S") if self.fecha_cierre else None,
        }

class ONU(Base):
    __tablename__ = "onus_flasheadas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lote_id = Column(Integer, ForeignKey("lotes_cajas.id", ondelete="SET NULL"), nullable=True)
    modelo_id = Column(String(50), ForeignKey("modelos_onu.id"), nullable=False)
    mac = Column(String(30), index=True, default="")
    pon_original = Column(String(50), index=True, default="")
    pon_sn = Column(String(30), index=True, default="")  # ej. VSOL00E3E021
    credencial_usuario = Column(String(50), default="Powerlink")
    credencial_clave = Column(String(100), default="Powerlink2026*")
    firmware_instalado = Column(String(150), default="")
    puerto_mikrotik = Column(String(10), default="")
    ip = Column(String(30), default="")
    resultado = Column(String(30), default="EXITO")  # EXITO, YA_CONFIGURADA, ERROR, SIN_ONU
    vlan3_ok = Column(String(10), default="NO")
    detalles = Column(Text, default="")
    duracion_segundos = Column(Integer, default=0)
    captura_path = Column(String(255), default="")
    operador_id = Column(Integer, ForeignKey("flasheo_usuarios.id"), nullable=True)
    station_id = Column(String(50), default="ESTACION-DEFAULT", index=True)
    sync_status = Column(String(20), default="SYNCED", index=True)
    synced_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=True)
    fecha_hora = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    # Relaciones
    lote = relationship("LoteCaja", back_populates="onus")
    modelo = relationship("ModeloONU", back_populates="onus")
    operador = relationship("FlasheoUsuario", back_populates="onus_procesadas")

    def to_dict(self, include_clave=True):
        return {
            "id": self.id,
            "station_id": self.station_id or "ESTACION-DEFAULT",
            "sync_status": self.sync_status or "SYNCED",
            "synced_at": self.synced_at.strftime("%Y-%m-%d %H:%M:%S") if self.synced_at else "",
            "lote_id": self.lote_id,
            "codigo_lote": self.lote.codigo_lote if self.lote else None,
            "numero_caja": self.lote.numero_caja if self.lote else None,
            "modelo_id": self.modelo_id,
            "modelo_nombre": self.modelo.nombre_comercial if self.modelo else self.modelo_id,
            "mac": self.mac,
            "pon_original": self.pon_original,
            "pon_sn": self.pon_sn,
            "credenciales": {
                "usuario": self.credencial_usuario,
                "clave": self.credencial_clave if include_clave else "********",
            },
            "firmware_instalado": self.firmware_instalado,
            "puerto_mikrotik": self.puerto_mikrotik,
            "ip": self.ip,
            "resultado": self.resultado,
            "vlan3_ok": self.vlan3_ok,
            "detalles": self.detalles,
            "duracion_segundos": self.duracion_segundos,
            "operador": self.operador.username if self.operador else None,
            "fecha_hora": self.fecha_hora.strftime("%Y-%m-%d %H:%M:%S") if self.fecha_hora else "",
        }


class FlasheoStation(Base):
    __tablename__ = "flasheo_stations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), unique=True, nullable=False, index=True)
    station_name = Column(String(100), default="")
    ip_address = Column(String(50), default="")
    hostname = Column(String(100), default="")
    total_flashed = Column(Integer, default=0)
    last_sync = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "station_id": self.station_id,
            "station_name": self.station_name or self.station_id,
            "ip_address": self.ip_address,
            "hostname": self.hostname,
            "total_flashed": self.total_flashed,
            "last_sync": self.last_sync.strftime("%Y-%m-%d %H:%M:%S") if self.last_sync else "",
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
        }

