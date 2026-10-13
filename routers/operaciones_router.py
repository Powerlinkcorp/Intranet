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

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, Body, Response
from fastapi.responses import HTMLResponse, RedirectResponse
import io, csv

@router.get("/api/operaciones/events")
def get_events(format: str = Query(None), db: Session = Depends(get_db)):
    events = db.query(models.NetworkEvent).order_by(models.NetworkEvent.date.desc()).all()
    # Serialize to match the React frontend
    result = []
    for ev in events:
        updates = [{"id": u.id, "timestamp": u.timestamp.isoformat(), "hora": u.hora, "autor": u.autor, "mensaje": u.mensaje} for u in ev.updates]
        result.append({
            "id": ev.id,
            "date": ev.date.isoformat() if ev.date else "",
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

    if format == "powerbi" or format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Fecha", "Causa", "Proveedor", "Lugar", "Personal", "Motivo", "HoraReporte", "HoraSolucion", "DuracionMinutos", "Estado"])
        for r in result:
            writer.writerow([r["id"], r["date"], r["causa"], r["proveedor"], r["lugar"], r["personal"], r["motivo"], r["horaReporte"], r["horaSolucion"], r["duracionMinutos"], r["estado"]])
        return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=eventos_powerbi.csv"})

    return result

@router.post("/api/operaciones/events")
def create_event(data: Any = Body(...), db: Session = Depends(get_db)):
    events_list = data if isinstance(data, list) else [data]
    saved_ids = []
    for event_data in events_list:
        ev_id = str(event_data.get("id") or uuid.uuid4())
        existing = db.query(models.NetworkEvent).filter(models.NetworkEvent.id == ev_id).first()
        
        date_raw = event_data.get("date")
        if date_raw:
            try:
                date_val = datetime.fromisoformat(str(date_raw))
            except Exception:
                date_val = datetime.utcnow()
        else:
            date_val = datetime.utcnow()

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
                custom_fields=str(event_data.get("customFields", "{}"))
            )
            db.add(new_event)
            saved_ids.append(new_event.id)
            
    db.commit()
    return {"status": "success", "count": len(saved_ids), "ids": saved_ids}

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

