from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, Body, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
import uuid
import json
import io
import csv
import logging

import security
from database import get_db
import models

import permissions_manager

templates = Jinja2Templates(directory="templates")
templates.env.globals["has_perm"] = permissions_manager.user_has_perm
templates.env.globals["has_any_perm"] = permissions_manager.user_has_any_perm
templates.env.globals["get_perm_registry"] = permissions_manager.load_registry
templates.env.globals["build_powertrack_perms"] = permissions_manager.build_powertrack_permissions_dict
templates.env.globals["get_user_perms_list"] = permissions_manager.get_user_effective_perms_list
router = APIRouter(tags=["operaciones"])
logger = logging.getLogger("operaciones")

# ============================================
# SCHEMAS PYDANTIC — Validación estricta (R3)
# ============================================

class EventCreate(BaseModel):
    """Schema para crear un nuevo evento de red."""
    id: Optional[str] = None
    date: str
    causa: Literal["Falla de proveedor", "Falla eléctrica", "Falla interna", "Actividad"]
    lugar: str = Field(..., min_length=1, max_length=150)
    personal: str = Field(..., min_length=1, max_length=150)
    motivo: str = Field(..., min_length=1, max_length=200)
    proveedor: Optional[str] = ""
    horaReporte: Optional[str] = ""
    horaSolucion: Optional[str] = ""
    duracionMinutos: Optional[int] = 0
    reporte: str = Field(..., min_length=1)
    estado: Literal["abierto", "en_seguimiento", "solventado"] = "abierto"
    customFields: Optional[Any] = "{}"
    accionTomada: Optional[str] = ""
    causaRaiz: Optional[str] = ""
    clientesAfectados: Optional[str] = ""

class EventUpdate(BaseModel):
    """Schema para actualizar campos de un evento existente."""
    causa: Optional[str] = None
    lugar: Optional[str] = None
    personal: Optional[str] = None
    motivo: Optional[str] = None
    proveedor: Optional[str] = None
    horaReporte: Optional[str] = None
    horaSolucion: Optional[str] = None
    duracionMinutos: Optional[int] = None
    reporte: Optional[str] = None
    estado: Optional[str] = None
    customFields: Optional[Any] = None
    accionTomada: Optional[str] = None
    causaRaiz: Optional[str] = None
    clientesAfectados: Optional[str] = None

class EventClose(BaseModel):
    """Schema para cerrar/solventar un evento."""
    horaSolucion: str
    duracionMinutos: int = 0
    accionTomada: str = Field(..., min_length=1)
    causaRaiz: Optional[str] = ""
    reporte: Optional[str] = None

class TicketUpdateCreate(BaseModel):
    """Schema para agregar una novedad/actualización a un ticket."""
    id: Optional[str] = None
    hora: str
    autor: str = Field(..., min_length=1)
    mensaje: str = Field(..., min_length=1)
    timestamp: Optional[str] = None
    new_status: Optional[str] = None

class BulkEventsPayload(BaseModel):
    """Schema para la carga masiva legacy (compatibilidad retroactiva)."""
    events: List[Dict[str, Any]]


# ============================================
# HELPER: Serializar evento a dict para JSON
# ============================================

def _serialize_event(ev: models.NetworkEvent) -> dict:
    """Convierte un ORM NetworkEvent a diccionario compatible con el frontend React."""
    updates = []
    for u in (ev.updates or []):
        updates.append({
            "id": u.id,
            "timestamp": u.timestamp.isoformat() if u.timestamp else "",
            "hora": u.hora,
            "autor": u.autor,
            "mensaje": u.mensaje
        })
    
    return {
        "id": ev.id,
        "date": ev.date.isoformat() if ev.date else "",
        "causa": ev.causa,
        "proveedor": ev.proveedor or "",
        "lugar": ev.lugar,
        "personal": ev.personal,
        "motivo": ev.motivo,
        "horaReporte": ev.hora_reporte or "",
        "horaSolucion": ev.hora_solucion or "",
        "duracionMinutos": ev.duracion_minutos or 0,
        "reporte": ev.reporte,
        "estado": ev.estado or "abierto",
        "customFields": ev.custom_fields or "{}",
        "accionTomada": ev.accion_tomada or "",
        "causaRaiz": ev.causa_raiz or "",
        "clientesAfectados": ev.clientes_afectados or "",
        "createdAt": ev.created_at.isoformat() if ev.created_at else "",
        "closedAt": ev.closed_at.isoformat() if ev.closed_at else "",
        "createdBy": ev.created_by or "",
        "closedBy": ev.closed_by or "",
        "updates": updates
    }


def _parse_date(date_raw) -> datetime:
    """Parsea una fecha ISO de forma segura con fallback a utcnow."""
    if date_raw:
        try:
            return datetime.fromisoformat(str(date_raw))
        except Exception:
            pass
    return datetime.utcnow()


# ============================================
# VISTA HTML (con autenticación)
# ============================================

@router.get("/admin/operaciones", response_class=HTMLResponse)
async def operaciones_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if not permissions_manager.user_has_any_perm(user, [
            "mod_operaciones", "sub_op_welcome", "sub_op_daily", "sub_op_events",
            "sub_op_guards", "sub_op_projects", "sub_op_activities", "sub_op_ozmap", "sub_op_ozmap_db"
        ]):
            return RedirectResponse(url="/")
        return templates.TemplateResponse(request, "operaciones.html", {"user": user})
    except (HTTPException, Exception):
        return RedirectResponse(url="/login")


# ============================================
# GET — Listar todos los eventos (público para Power BI)
# ============================================

@router.get("/api/operaciones/events")
def get_events(format: str = Query(None), db: Session = Depends(get_db)):
    events = db.query(models.NetworkEvent).order_by(models.NetworkEvent.date.desc()).all()
    result = [_serialize_event(ev) for ev in events]

    # Exportación CSV enriquecida para Power BI (R11)
    if format in ("powerbi", "csv"):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Fecha", "Anio", "Mes", "DiaSemana", "Causa", "Proveedor", "Lugar",
            "Personal", "Motivo", "HoraReporte", "HoraSolucion", "DuracionMinutos",
            "Estado", "AccionTomada", "CausaRaiz", "ClientesAfectados",
            "NumeroActualizaciones", "CreadoPor", "CerradoPor"
        ])
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        for r in result:
            try:
                dt = datetime.fromisoformat(r["date"]) if r["date"] else None
                anio = dt.year if dt else ""
                mes = dt.month if dt else ""
                dia_sem = dias_semana[dt.weekday()] if dt else ""
            except Exception:
                anio, mes, dia_sem = "", "", ""
            writer.writerow([
                r["id"], r["date"], anio, mes, dia_sem, r["causa"], r["proveedor"],
                r["lugar"], r["personal"], r["motivo"], r["horaReporte"], r["horaSolucion"],
                r["duracionMinutos"], r["estado"], r["accionTomada"], r["causaRaiz"],
                r["clientesAfectados"], len(r.get("updates", [])),
                r.get("createdBy", ""), r.get("closedBy", "")
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=eventos_powerbi.csv"}
        )

    return result


# ============================================
# POST — Crear un evento individual (R1, R2, R3)
# ============================================

@router.post("/api/operaciones/events/create", status_code=201)
def create_single_event(data: EventCreate, db: Session = Depends(get_db)):
    ev_id = data.id or f"evt-{int(datetime.utcnow().timestamp() * 1000)}"
    
    # Verificar que no exista duplicado
    existing = db.query(models.NetworkEvent).filter(models.NetworkEvent.id == ev_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"El evento con ID '{ev_id}' ya existe.")
    
    date_val = _parse_date(data.date)
    
    new_event = models.NetworkEvent(
        id=ev_id,
        date=date_val,
        causa=data.causa,
        proveedor=data.proveedor or "",
        lugar=data.lugar,
        personal=data.personal,
        motivo=data.motivo,
        hora_reporte=data.horaReporte or "",
        hora_solucion=data.horaSolucion or "",
        duracion_minutos=data.duracionMinutos or 0,
        reporte=data.reporte,
        estado=data.estado,
        custom_fields=str(data.customFields) if data.customFields else "{}",
        accion_tomada=data.accionTomada or "",
        causa_raiz=data.causaRaiz or "",
        clientes_afectados=data.clientesAfectados or "",
        closed_at=datetime.utcnow() if data.estado == "solventado" else None,
    )
    
    try:
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creando evento {ev_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al guardar en base de datos: {str(e)[:200]}")
    
    return {"status": "created", "id": new_event.id, "event": _serialize_event(new_event)}


# ============================================
# PUT — Actualizar un evento existente (R1)
# ============================================

@router.put("/api/operaciones/events/{event_id}")
def update_event(event_id: str, data: EventUpdate, db: Session = Depends(get_db)):
    event = db.query(models.NetworkEvent).filter(models.NetworkEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Evento '{event_id}' no encontrado.")
    
    # Actualizar solo los campos enviados (no-None)
    update_fields = data.model_dump(exclude_none=True)
    field_map = {
        "causa": "causa", "lugar": "lugar", "personal": "personal",
        "motivo": "motivo", "proveedor": "proveedor",
        "horaReporte": "hora_reporte", "horaSolucion": "hora_solucion",
        "duracionMinutos": "duracion_minutos", "reporte": "reporte",
        "estado": "estado", "accionTomada": "accion_tomada",
        "causaRaiz": "causa_raiz", "clientesAfectados": "clientes_afectados"
    }
    
    for frontend_key, db_col in field_map.items():
        if frontend_key in update_fields:
            setattr(event, db_col, update_fields[frontend_key])
    
    if "customFields" in update_fields:
        event.custom_fields = str(update_fields["customFields"])
    
    try:
        db.commit()
        db.refresh(event)
    except Exception as e:
        db.rollback()
        logger.error(f"Error actualizando evento {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar: {str(e)[:200]}")
    
    return {"status": "updated", "event": _serialize_event(event)}


# ============================================
# PATCH — Cerrar / Solventar un evento (R1)
# ============================================

@router.patch("/api/operaciones/events/{event_id}/close")
def close_event(event_id: str, data: EventClose, db: Session = Depends(get_db)):
    event = db.query(models.NetworkEvent).filter(models.NetworkEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Evento '{event_id}' no encontrado.")
    
    event.estado = "solventado"
    event.hora_solucion = data.horaSolucion
    event.duracion_minutos = data.duracionMinutos
    event.accion_tomada = data.accionTomada
    event.causa_raiz = data.causaRaiz or ""
    event.closed_at = datetime.utcnow()
    if data.reporte:
        event.reporte = data.reporte
    
    try:
        db.commit()
        db.refresh(event)
    except Exception as e:
        db.rollback()
        logger.error(f"Error cerrando evento {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al cerrar evento: {str(e)[:200]}")
    
    return {"status": "closed", "event": _serialize_event(event)}


# ============================================
# DELETE — Eliminar un evento (R1)
# ============================================

@router.delete("/api/operaciones/events/{event_id}")
def delete_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(models.NetworkEvent).filter(models.NetworkEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Evento '{event_id}' no encontrado.")
    
    try:
        db.delete(event)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error eliminando evento {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar: {str(e)[:200]}")
    
    return {"status": "deleted", "id": event_id}


# ============================================
# POST — Agregar novedad / update a un ticket (R1, R9)
# ============================================

@router.post("/api/operaciones/events/{event_id}/update")
def add_event_update(event_id: str, data: TicketUpdateCreate, db: Session = Depends(get_db)):
    event = db.query(models.NetworkEvent).filter(models.NetworkEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Evento '{event_id}' no encontrado.")
    
    update_id = data.id or str(uuid.uuid4())
    ts = data.timestamp or datetime.utcnow().isoformat()
    
    new_update = models.NetworkEventUpdate(
        id=update_id,
        event_id=event_id,
        timestamp=datetime.fromisoformat(ts),
        hora=data.hora,
        autor=data.autor,
        mensaje=data.mensaje
    )
    
    # Actualizar estado del evento si se solicita
    if data.new_status:
        event.estado = data.new_status
    elif event.estado == "abierto":
        event.estado = "en_seguimiento"
    
    try:
        db.add(new_update)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error agregando update a {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al agregar actualización: {str(e)[:200]}")
    
    return {"status": "success", "update_id": update_id}


# ============================================
# POST LEGACY — Compatibilidad con bulk save del frontend actual
# ============================================

@router.post("/api/operaciones/events")
def bulk_save_events(data: Any = Body(...), db: Session = Depends(get_db)):
    """
    Endpoint legacy de compatibilidad retroactiva.
    Acepta un array completo de eventos (como lo envía el frontend actual)
    y hace upsert de cada uno. Se mantiene para no romper el frontend
    mientras se migra gradualmente a los endpoints individuales.
    """
    events_list = data if isinstance(data, list) else [data]
    saved_ids = []
    
    for event_data in events_list:
        ev_id = str(event_data.get("id") or uuid.uuid4())
        existing = db.query(models.NetworkEvent).filter(models.NetworkEvent.id == ev_id).first()
        
        date_val = _parse_date(event_data.get("date"))

        if existing:
            existing.date = date_val
            existing.causa = event_data.get("causa", existing.causa)
            existing.proveedor = event_data.get("proveedor", existing.proveedor)
            existing.lugar = event_data.get("lugar", existing.lugar)
            existing.personal = event_data.get("personal", existing.personal)
            existing.motivo = event_data.get("motivo", existing.motivo)
            existing.hora_reporte = event_data.get("horaReporte", existing.hora_reporte)
            existing.hora_solucion = event_data.get("horaSolucion", existing.hora_solucion)
            existing.duracion_minutos = event_data.get("duracionMinutos", existing.duracion_minutos)
            existing.reporte = event_data.get("reporte", existing.reporte)
            existing.estado = event_data.get("estado", existing.estado)
            existing.custom_fields = str(event_data.get("customFields", existing.custom_fields))
            existing.accion_tomada = event_data.get("accionTomada", existing.accion_tomada)
            existing.causa_raiz = event_data.get("causaRaiz", existing.causa_raiz)
            existing.clientes_afectados = event_data.get("clientesAfectados", existing.clientes_afectados)
            saved_ids.append(existing.id)
        else:
            new_event = models.NetworkEvent(
                id=ev_id,
                date=date_val,
                causa=event_data.get("causa", ""),
                proveedor=event_data.get("proveedor", ""),
                lugar=event_data.get("lugar", ""),
                personal=event_data.get("personal", ""),
                motivo=event_data.get("motivo", ""),
                hora_reporte=event_data.get("horaReporte", ""),
                hora_solucion=event_data.get("horaSolucion", ""),
                duracion_minutos=event_data.get("duracionMinutos", 0),
                reporte=event_data.get("reporte", ""),
                estado=event_data.get("estado", "abierto"),
                custom_fields=str(event_data.get("customFields", "{}")),
                accion_tomada=event_data.get("accionTomada", ""),
                causa_raiz=event_data.get("causaRaiz", ""),
                clientes_afectados=event_data.get("clientesAfectados", "")
            )
            db.add(new_event)
            saved_ids.append(new_event.id)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error en bulk save: {e}")
        raise HTTPException(status_code=500, detail=f"Error al guardar eventos: {str(e)[:200]}")
    
    return {"status": "success", "count": len(saved_ids), "ids": saved_ids}


# ============================================
# OZMAP BITÁCORA
# ============================================

@router.get("/api/operaciones/ozmap/bitacora")
def get_bitacora(db: Session = Depends(get_db)):
    records = db.query(models.OzmapBitacora).all()
    result = []
    for r in records:
        result.append({
            "id": r.id, "fecha": r.fecha, "hora": r.hora,
            "id_servicio": r.id_servicio, "id_usuario": r.id_usuario,
            "cliente": r.cliente, "cedula": r.cedula,
            "serial_onu": r.serial_onu, "precinto": r.precinto,
            "caja_nap": r.caja_nap, "caja_original": r.caja_original,
            "tipo_accion": r.tipo_accion, "codigo_ozmap": r.codigo_ozmap,
            "georreferenciado": r.georreferenciado, "estado": r.estado,
            "timestamp": r.timestamp
        })
    return result

@router.post("/api/operaciones/ozmap/bitacora")
def save_bitacora(records: List[Dict[Any, Any]], db: Session = Depends(get_db)):
    for r in records:
        existing = db.query(models.OzmapBitacora).filter(models.OzmapBitacora.id == r.get("id")).first()
        if not existing:
            new_record = models.OzmapBitacora(
                id=r.get("id"), fecha=r.get("fecha"), hora=r.get("hora"),
                id_servicio=r.get("id_servicio"), id_usuario=r.get("id_usuario"),
                cliente=r.get("cliente"), cedula=r.get("cedula"),
                serial_onu=r.get("serial_onu"), precinto=r.get("precinto"),
                caja_nap=r.get("caja_nap"), caja_original=r.get("caja_original"),
                tipo_accion=r.get("tipo_accion"), codigo_ozmap=r.get("codigo_ozmap"),
                georreferenciado=r.get("georreferenciado", True),
                estado=r.get("estado"), timestamp=r.get("timestamp")
            )
            db.add(new_record)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error guardando bitácora: {str(e)[:200]}")
    return {"status": "success", "records_processed": len(records)}


# ============================================
# PROXY IIS — Descarga de archivos Excel
# ============================================

@router.get("/descargas_powerlink/{filename}")
async def proxy_descargas_powerlink(filename: str):
    """Proxy hacia el servidor IIS 10.0.1.243 para descargar las bases de datos Rubpi sin 404 ni CORS"""
    import requests
    target_url = f"http://10.0.1.243/descargas_powerlink/{filename}"
    try:
        resp = requests.get(target_url, timeout=30)
        if resp.status_code == 200:
            return Response(
                content=resp.content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                }
            )
        else:
            raise HTTPException(status_code=resp.status_code, detail=f"Servidor IIS devolvió error: {resp.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar con el servidor IIS 10.0.1.243: {e}")
