from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime
import uuid

import security
from database import get_db
import models

templates = Jinja2Templates(directory="templates")

router = APIRouter(tags=["operaciones"])

@router.get("/admin/operaciones", response_class=HTMLResponse)
async def operaciones_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        return templates.TemplateResponse(request, "operaciones.html", {"user": user})
    except HTTPException:
        return RedirectResponse(url="/login")

@router.get("/api/operaciones/events")
def get_events(db: Session = Depends(get_db)):
    events = db.query(models.NetworkEvent).order_by(models.NetworkEvent.date.desc()).all()
    # Serialize to match the React frontend
    result = []
    for ev in events:
        updates = [{"id": u.id, "timestamp": u.timestamp.isoformat(), "hora": u.hora, "autor": u.autor, "mensaje": u.mensaje} for u in ev.updates]
        result.append({
            "id": ev.id,
            "date": ev.date.isoformat(),
            "causa": ev.causa,
            "proveedor": ev.proveedor,
            "lugar": ev.lugar,
            "personal": ev.personal,
            "motivo": ev.motivo,
            "horaReporte": ev.hora_reporte,
            "horaSolucion": ev.hora_solucion,
            "duracionMinutos": ev.duracion_minutos,
            "reporte": ev.reporte,
            "estado": ev.estado,
            "customFields": ev.custom_fields,
            "updates": updates
        })
    return result

@router.post("/api/operaciones/events")
def create_event(event_data: Dict[Any, Any], db: Session = Depends(get_db)):
    new_event = models.NetworkEvent(
        id=event_data.get("id", str(uuid.uuid4())),
        date=datetime.fromisoformat(event_data.get("date", datetime.utcnow().isoformat())),
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
        custom_fields=event_data.get("customFields", "{}")
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return {"status": "success", "id": new_event.id}

@router.post("/api/operaciones/events/{event_id}/update")
def add_event_update(event_id: str, update_data: Dict[Any, Any], db: Session = Depends(get_db)):
    event = db.query(models.NetworkEvent).filter(models.NetworkEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    new_update = models.NetworkEventUpdate(
        id=update_data.get("id", str(uuid.uuid4())),
        event_id=event_id,
        timestamp=datetime.fromisoformat(update_data.get("timestamp", datetime.utcnow().isoformat())),
        hora=update_data.get("hora", ""),
        autor=update_data.get("autor", ""),
        mensaje=update_data.get("mensaje", "")
    )
    
    # Update event status if provided
    new_status = update_data.get("new_status")
    if new_status:
        event.estado = new_status
        if update_data.get("horaSolucion"):
            event.hora_solucion = update_data.get("horaSolucion")
        if update_data.get("duracionMinutos"):
            event.duracion_minutos = update_data.get("duracionMinutos")
            
    db.add(new_update)
    db.commit()
    return {"status": "success"}

@router.get("/api/operaciones/ozmap/bitacora")
def get_bitacora(db: Session = Depends(get_db)):
    records = db.query(models.OzmapBitacora).all()
    result = []
    for r in records:
        result.append({
            "id": r.id,
            "fecha": r.fecha,
            "hora": r.hora,
            "id_servicio": r.id_servicio,
            "id_usuario": r.id_usuario,
            "cliente": r.cliente,
            "cedula": r.cedula,
            "serial_onu": r.serial_onu,
            "precinto": r.precinto,
            "caja_nap": r.caja_nap,
            "caja_original": r.caja_original,
            "tipo_accion": r.tipo_accion,
            "codigo_ozmap": r.codigo_ozmap,
            "georreferenciado": r.georreferenciado,
            "estado": r.estado,
            "timestamp": r.timestamp
        })
    return result

@router.post("/api/operaciones/ozmap/bitacora")
def save_bitacora(records: List[Dict[Any, Any]], db: Session = Depends(get_db)):
    for r in records:
        existing = db.query(models.OzmapBitacora).filter(models.OzmapBitacora.id == r.get("id")).first()
        if not existing:
            new_record = models.OzmapBitacora(
                id=r.get("id"),
                fecha=r.get("fecha"),
                hora=r.get("hora"),
                id_servicio=r.get("id_servicio"),
                id_usuario=r.get("id_usuario"),
                cliente=r.get("cliente"),
                cedula=r.get("cedula"),
                serial_onu=r.get("serial_onu"),
                precinto=r.get("precinto"),
                caja_nap=r.get("caja_nap"),
                caja_original=r.get("caja_original"),
                tipo_accion=r.get("tipo_accion"),
                codigo_ozmap=r.get("codigo_ozmap"),
                georreferenciado=r.get("georreferenciado", True),
                estado=r.get("estado"),
                timestamp=r.get("timestamp")
            )
            db.add(new_record)
    db.commit()
    return {"status": "success", "records_processed": len(records)}
