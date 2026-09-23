# -*- coding: utf-8 -*-
"""
core.schemas — Esquemas Pydantic v2 para validación, serialización y documentación OpenAPI.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ----------------------------------------------------------------------------
# AUTENTICACIÓN Y USUARIOS
# ----------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str = Field(..., description="Nombre de usuario")
    password: str = Field(..., description="Contraseña de acceso")


class LoginResponse(BaseModel):
    success: bool
    token: str
    user: Dict[str, Any]
    message: Optional[str] = None


class UserCreate(BaseModel):
    username: str
    password: str
    rol: str = Field("configurador", description="admin | configurador | visualizador")
    nombre_completo: Optional[str] = ""


class UserResponse(BaseModel):
    id: int
    username: str
    rol: str
    nombre_completo: Optional[str]
    activo: bool
    created_at: Optional[str]


# ----------------------------------------------------------------------------
# LOTES Y CAJAS
# ----------------------------------------------------------------------------
class LoteCreate(BaseModel):
    codigo_lote: str = Field(..., description="Código único del lote (ej. LOTE-2026-05)")
    numero_caja: str = Field(..., description="Identificador físico de caja (ej. Caja #12)")
    modelo_id: str = Field(..., description="ID del modelo de ONU asignado (ej. V2801S-B)")
    firmware_asignado: str = Field(..., description="Nombre de archivo de firmware (.bin)")
    clave_asignada: str = Field("Powerlink2026*", description="Clave que se le programará a las ONUs del lote")
    cantidad_total: int = Field(20, description="Cantidad estimada de ONUs en la caja")
    descripcion: Optional[str] = ""


class LoteResponse(BaseModel):
    id: int
    codigo_lote: str
    numero_caja: str
    modelo_id: str
    modelo_nombre: Optional[str] = ""
    firmware_asignado: Optional[str] = ""
    usuario_asignado: Optional[str] = "Powerlink"
    clave_asignada: Optional[str] = ""
    cantidad_total: int = 20
    cantidad_procesadas: int = 0
    cantidad_exitosas: int = 0
    cantidad_fallidas: int = 0
    estado: str = "EN_PROCESO"
    es_activo: bool = False
    fecha_inicio: Optional[str] = ""
    fecha_cierre: Optional[str] = None


# ----------------------------------------------------------------------------
# ONUs Y CONSULTA EXTERNA
# ----------------------------------------------------------------------------
class ONUExternalCredentials(BaseModel):
    usuario: str
    clave: str


class ONUExternalLote(BaseModel):
    codigo_lote: Optional[str]
    numero_caja: Optional[str]
    estado_lote: Optional[str]


class ONUExternalResponse(BaseModel):
    encontrado: bool
    mac: str
    pon_sn: str
    pon_original: str
    modelo: str
    credenciales: ONUExternalCredentials
    lote: ONUExternalLote
    firmware: str
    vlan3_verificada: str
    fecha_flasheo: str


class ONUResponse(BaseModel):
    id: int
    lote_id: Optional[int]
    codigo_lote: Optional[str]
    numero_caja: Optional[str]
    modelo_id: str
    modelo_nombre: Optional[str]
    mac: str
    pon_original: str
    pon_sn: str
    credenciales: Dict[str, str]
    firmware_instalado: str
    puerto_mikrotik: str
    ip: str
    resultado: str
    vlan3_ok: str
    detalles: str
    duracion_segundos: int
    operador: Optional[str]
    fecha_hora: str


# ----------------------------------------------------------------------------
# CONTROL DE FLASHEO
# ----------------------------------------------------------------------------
class FlasheoContinuoRequest(BaseModel):
    model: Optional[str] = None
    parallel: int = Field(20, description="Grado de paralelismo (máx 20)")


class FlasheoSingleRequest(BaseModel):
    ip: Optional[str] = "192.168.1.1"
    puerto: Optional[int] = None
    model: Optional[str] = None
    direct: Optional[bool] = False
    action: Optional[str] = Field("full", description="full | factory_reset | verify_vlan")

