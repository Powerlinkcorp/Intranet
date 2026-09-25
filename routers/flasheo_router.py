# -*- coding: utf-8 -*-
"""
routers.flasheo_router — Enrutador del Módulo de Flasheo e Integración Servidor-Cliente.
Maneja:
  1. Renderizado de interfaz Intranet (/soporte/flasheo).
  2. Endpoints de sincronización de estaciones remotas (POST /api/flasheo/sync/onus).
  3. Verificación de conectividad (GET /api/flasheo/ping).
  4. Consulta de estaciones activas (GET /api/flasheo/stations).
  5. Trazabilidad y credenciales para Aprovisionamiento (GET /api/flasheo/onu_traceability).
  6. Sub-routers heredados y WebSockets.
"""
import os
import re
import sys
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import or_, desc
from sqlalchemy.orm import Session

from database import get_db
import models
import security
from flasheo.api.v1 import api_v1_router
from flasheo.api.v1.endpoints import ws, onus

templates = Jinja2Templates(directory="templates")

router = APIRouter()

# ============================================================================
# ESQUEMAS PYDANTIC PARA SINCRONIZACIÓN CLIENTE-SERVIDOR
# ============================================================================
class SyncRecordItem(BaseModel):
    mac: str
    pon_sn: Optional[str] = ""
    pon_original: Optional[str] = ""
    modelo_id: Optional[str] = "V2801S-B"
    codigo_lote: Optional[str] = ""
    numero_caja: Optional[str] = ""
    credencial_usuario: Optional[str] = "Powerlink"
    credencial_clave: Optional[str] = "Powerlink2026*"
    firmware_instalado: Optional[str] = ""
    puerto_mikrotik: Optional[str] = ""
    ip: Optional[str] = ""
    resultado: Optional[str] = "EXITO"
    vlan3_ok: Optional[str] = "NO"
    detalles: Optional[str] = ""
    duracion_segundos: Optional[int] = 0
    captura_path: Optional[str] = ""
    operador: Optional[str] = ""
    fecha_hora: Optional[str] = ""

class SyncBatchPayload(BaseModel):
    station_id: str
    station_name: Optional[str] = ""
    hostname: Optional[str] = ""
    ip_address: Optional[str] = ""
    records: List[SyncRecordItem] = []


# ============================================================================
# ENDPOINTS DE SALUD Y CONECTIVIDAD
# ============================================================================
@router.get("/api/flasheo/ping", tags=["Flasheo Sincronización"])
@router.get("/ping", tags=["Flasheo Sincronización"])
async def flasheo_ping():
    """Healthcheck rápido para que las laptops de las estaciones sepan si la Intranet está accesible."""
    return {
        "status": "ok",
        "service": "Intranet Central Powerlink",
        "server_time": datetime.utcnow().isoformat(),
        "version": "3.0.0"
    }


# ============================================================================
# ENDPOINTS DE SINCRONIZACIÓN MULTI-ESTACIÓN
# ============================================================================
@router.post("/api/flasheo/sync/onus", tags=["Flasheo Sincronización"])
async def sync_onus_from_station(payload: SyncBatchPayload, db: Session = Depends(get_db)):
    """
    Recibe un lote de ONUs flasheadas desde cualquier laptop de flasheo.
    Inserta o actualiza registros con identificación de la estación origen (station_id),
    generando los lotes correspondientes y garantizando idempotencia.
    """
    if not payload.station_id:
        raise HTTPException(status_code=400, detail="El campo station_id es obligatorio.")

    now = datetime.utcnow()

    # 1. Registrar o actualizar la estación cliente
    station = db.query(models.FlasheoStation).filter_by(station_id=payload.station_id).first()
    if not station:
        station = models.FlasheoStation(
            station_id=payload.station_id,
            station_name=payload.station_name or payload.station_id,
            hostname=payload.hostname or "",
            ip_address=payload.ip_address or "",
            total_flashed=0,
            last_sync=now,
            is_active=True
        )
        db.add(station)
        db.flush()
    else:
        if payload.station_name:
            station.station_name = payload.station_name
        if payload.hostname:
            station.hostname = payload.hostname
        if payload.ip_address:
            station.ip_address = payload.ip_address
        station.last_sync = now
        station.is_active = True

    synced_count = 0

    for item in payload.records:
        mac_raw = (item.mac or "").strip().upper()
        pon_sn_raw = (item.pon_sn or "").strip().upper()
        if not mac_raw and not pon_sn_raw:
            continue

        clean_mac = re.sub(r"[^0-9A-Z]", "", mac_raw)
        clean_sn = re.sub(r"[^0-9A-Z]", "", pon_sn_raw)

        # 2. Asociar o crear lote si viene indicado
        lote_id = None
        if item.codigo_lote:
            lote = db.query(models.LoteCaja).filter_by(codigo_lote=item.codigo_lote.strip()).first()
            if not lote:
                lote = models.LoteCaja(
                    codigo_lote=item.codigo_lote.strip(),
                    numero_caja=item.numero_caja.strip() if item.numero_caja else "Caja S/N",
                    modelo_id=item.modelo_id or "V2801S-B",
                    firmware_asignado=item.firmware_instalado or "",
                    clave_asignada=item.credencial_clave or "Powerlink2026*",
                    usuario_asignado=item.credencial_usuario or "Powerlink",
                    estado="EN_PROCESO"
                )
                db.add(lote)
                db.flush()
            lote_id = lote.id

        # 3. Buscar si la ONU ya existe por MAC o Serial
        filters = []
        if mac_raw:
            filters.append(models.ONU.mac.ilike(mac_raw))
            if clean_mac:
                filters.append(models.ONU.mac.ilike(f"%{clean_mac}%"))
        if pon_sn_raw:
            filters.append(models.ONU.pon_sn.ilike(pon_sn_raw))
            if clean_sn:
                filters.append(models.ONU.pon_sn.ilike(f"%{clean_sn}%"))

        onu = None
        if filters:
            onu = db.query(models.ONU).filter(or_(*filters)).order_by(models.ONU.id.desc()).first()

        # Parsear fecha
        fecha_parsed = now
        if item.fecha_hora:
            try:
                clean_date = item.fecha_hora.replace("T", " ").split(".")[0]
                fecha_parsed = datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
            except Exception:
                fecha_parsed = now

        if onu:
            # Actualizar datos de flasheo
            onu.station_id = payload.station_id
            onu.sync_status = "SYNCED"
            onu.synced_at = now
            if lote_id:
                onu.lote_id = lote_id
            if item.modelo_id:
                onu.modelo_id = item.modelo_id
            if item.pon_original:
                onu.pon_original = item.pon_original
            if item.credencial_usuario:
                onu.credencial_usuario = item.credencial_usuario
            if item.credencial_clave:
                onu.credencial_clave = item.credencial_clave
            if item.firmware_instalado:
                onu.firmware_instalado = item.firmware_instalado
            if item.resultado:
                onu.resultado = item.resultado
            if item.vlan3_ok:
                onu.vlan3_ok = item.vlan3_ok
            if item.puerto_mikrotik:
                onu.puerto_mikrotik = item.puerto_mikrotik
            if item.ip:
                onu.ip = item.ip
            if item.detalles:
                onu.detalles = item.detalles
            if item.duracion_segundos:
                onu.duracion_segundos = item.duracion_segundos
            onu.fecha_hora = fecha_parsed
        else:
            # Crear nuevo registro en la Intranet
            onu = models.ONU(
                lote_id=lote_id,
                modelo_id=item.modelo_id or "V2801S-B",
                mac=mac_raw,
                pon_original=item.pon_original.strip() if item.pon_original else "",
                pon_sn=pon_sn_raw,
                credencial_usuario=item.credencial_usuario or "Powerlink",
                credencial_clave=item.credencial_clave or "Powerlink2026*",
                firmware_instalado=item.firmware_instalado or "",
                puerto_mikrotik=str(item.puerto_mikrotik or ""),
                ip=item.ip or "",
                resultado=item.resultado or "EXITO",
                vlan3_ok=item.vlan3_ok or "NO",
                detalles=item.detalles or "",
                duracion_segundos=item.duracion_segundos or 0,
                captura_path=item.captura_path or "",
                station_id=payload.station_id,
                sync_status="SYNCED",
                synced_at=now,
                fecha_hora=fecha_parsed
            )
            db.add(onu)

        synced_count += 1

    # Actualizar contador de la estación
    db.flush()
    station.total_flashed = db.query(models.ONU).filter_by(station_id=payload.station_id).count()
    db.commit()

    return {
        "status": "success",
        "message": f"{synced_count} ONUs sincronizadas exitosamente en el servidor central.",
        "synced_count": synced_count,
        "station_id": payload.station_id,
        "server_time": now.isoformat()
    }


@router.get("/api/flasheo/stations", tags=["Flasheo Sincronización"])
async def list_flasheo_stations(db: Session = Depends(get_db)):
    """Retorna la lista de todas las laptops / estaciones de flasheo registradas en la Intranet."""
    stations = db.query(models.FlasheoStation).order_by(models.FlasheoStation.last_sync.desc()).all()
    res = []
    for s in stations:
        d = s.to_dict()
        d["total_flashed"] = db.query(models.ONU).filter_by(station_id=s.station_id).count()
        res.append(d)
    return res


# ============================================================================
# CONSULTA DE ONUS Y TRAZABILIDAD PARA APROVISIONAMIENTO
# ============================================================================
@router.get("/api/flasheo/onus", tags=["Flasheo Intranet"])
async def get_all_flashed_onus(
    station_id: Optional[str] = None,
    resultado: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db)
):
    """Listado centralizado de ONUs flasheadas con filtro multi-estación."""
    q = db.query(models.ONU)
    if station_id and station_id not in ["TODAS", "ALL", ""]:
        q = q.filter(models.ONU.station_id == station_id)
    if resultado and resultado not in ["TODOS", "ALL", ""]:
        q = q.filter(models.ONU.resultado == resultado)
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                models.ONU.mac.ilike(term),
                models.ONU.pon_sn.ilike(term),
                models.ONU.pon_original.ilike(term)
            )
        )
    items = q.order_by(models.ONU.id.desc()).limit(limit).all()
    return [i.to_dict(include_clave=True) for i in items]


def _resolve_traceability(q_val: str, db: Session) -> Dict[str, Any]:
    q = (q_val or "").strip()
    if not q:
        return {
            "encontrado": False,
            "query": q_val,
            "message": "Identificador vacío."
        }
    q_clean = re.sub(r"[^0-9A-Za-z]", "", q).upper()

    onu = db.query(models.ONU).filter(
        or_(
            models.ONU.mac.ilike(f"%{q}%"),
            models.ONU.pon_sn.ilike(f"%{q}%"),
            models.ONU.pon_original.ilike(f"%{q}%"),
            models.ONU.mac.ilike(f"%{q_clean}%"),
            models.ONU.pon_sn.ilike(f"%{q_clean}%")
        )
    ).order_by(models.ONU.id.desc()).first()

    if not onu:
        return {
            "encontrado": False,
            "query": q_val,
            "message": "No se encontraron registros de flasheo para este identificador."
        }

    return {
        "encontrado": True,
        "station_id": onu.station_id or "ESTACION-CENTRAL",
        "mac": onu.mac,
        "pon_sn": onu.pon_sn,
        "pon_original": onu.pon_original,
        "modelo": onu.modelo_id,
        "credenciales": {
            "usuario": onu.credencial_usuario or "Powerlink",
            "clave": onu.credencial_clave or "Powerlink2026*"
        },
        "lote": {
            "codigo_lote": onu.lote.codigo_lote if onu.lote else "Lote S/N",
            "numero_caja": onu.lote.numero_caja if onu.lote else "Caja N/A",
            "estado_lote": onu.lote.estado if onu.lote else "COMPLETO"
        },
        "firmware": onu.firmware_instalado,
        "vlan3_verificada": onu.vlan3_ok,
        "fecha_flasheo": onu.fecha_hora.strftime("%Y-%m-%d %H:%M:%S") if onu.fecha_hora else "",
        "sync_status": onu.sync_status or "SYNCED"
    }


@router.get("/api/flasheo/onus/{identificador}/credentials", tags=["Flasheo Trazabilidad"])
async def get_onu_credentials_by_path(identificador: str, db: Session = Depends(get_db)):
    """Consulta de credenciales por parámetro de ruta (para compatibilidad)."""
    return _resolve_traceability(identificador, db)


@router.get("/api/flasheo/onu_traceability", tags=["Flasheo Trazabilidad"])
async def get_onu_traceability_by_query(query: str = Query(...), db: Session = Depends(get_db)):
    """Consulta de trazabilidad por parámetro query (usado por la UI de Aprovisionamiento)."""
    return _resolve_traceability(query, db)



# ============================================================================
# SUB-ROUTERS Y WEBSOCKETS HEREDADOS
# ============================================================================
router.include_router(api_v1_router)
router.include_router(api_v1_router, prefix="/api/flasheo")
router.include_router(onus.router, prefix="/api/flasheo")
router.include_router(ws.router)


# ============================================================================
# PÁGINA PRINCIPAL EN LA INTRANET
# ============================================================================
@router.get("/soporte/flasheo", response_class=HTMLResponse)
async def flasheo_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if user.role not in ["admin"] and "ver_flasheo" not in (user.permissions or ""):
            return RedirectResponse(url="/")
        return templates.TemplateResponse(request, "flasheo.html", {"request": request, "user": user})
    except HTTPException:
        return RedirectResponse(url="/login")
