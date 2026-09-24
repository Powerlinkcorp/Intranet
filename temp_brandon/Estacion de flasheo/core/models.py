# -*- coding: utf-8 -*-
"""
core.models — Modelos Declarativos de SQLAlchemy para la Estación de Flasheo.
Gestiona:
  - Usuario (RBAC: admin, configurador, visualizador)
  - ModeloONU (V2801S-B, V2804AX30-H, etc.)
  - LoteCaja (Lotes/Cajas con firmware y credencial asignada)
  - ONU (Registro histórico y relación individual con su clave y lote)
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    salt = Column(String(64), default="")
    rol = Column(String(20), nullable=False, default="configurador")  # admin, configurador, visualizador
    nombre_completo = Column(String(100), default="")
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

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
    icono = Column(String(10), default="📡")
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
    fecha_inicio = Column(DateTime, default=datetime.utcnow)
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
            "clave_asignada": self.clave_asignada if include_clave else "••••••••",
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
    operador_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_hora = Column(DateTime, default=datetime.utcnow, index=True)

    # Relaciones
    lote = relationship("LoteCaja", back_populates="onus")
    modelo = relationship("ModeloONU", back_populates="onus")
    operador = relationship("Usuario", back_populates="onus_procesadas")

    def to_dict(self, include_clave=True):
        """Retorna diccionario serializable para la UI y la API externa."""
        return {
            "id": self.id,
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
                "clave": self.credencial_clave if include_clave else "••••••••",
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
