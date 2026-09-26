# -*- coding: utf-8 -*-
"""
api.v1.endpoints.lotes — Gestión de Cajas, Lotes y Asignación de Claves.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from core import database
from core.schemas import LoteCreate, LoteResponse
from api.v1.endpoints.auth import get_current_user, require_operator, require_admin

router = APIRouter(prefix="/lotes", tags=["Lotes y Cajas"])


@router.get("", response_model=List[LoteResponse], summary="Listar todos los lotes")
def get_lotes(current_user: dict = Depends(get_current_user)):
    # Los administradores ven la clave completa, los configuradores/visualizadores ven asteriscos
    is_admin = (current_user.get("rol") == "admin")
    return database.list_lotes(include_clave=is_admin)


@router.get("/active", response_model=LoteResponse, summary="Obtener lote activo actual")
def get_active_lote(current_user: dict = Depends(get_current_user)):
    lote = database.get_active_lote()
    if not lote:
        raise HTTPException(status_code=404, detail="No hay lote activo configurado.")
    if current_user.get("rol") != "admin":
        lote["clave_asignada"] = "••••••••"
    return lote


@router.post("", summary="Crear un nuevo lote con firmware y clave asignada")
def create_lote(req: LoteCreate, operator: dict = Depends(require_operator)):
    ok, msg = database.create_lote(
        numero_caja=req.numero_caja,
        codigo_lote=req.codigo_lote,
        modelo_id=req.modelo_id,
        firmware=req.firmware_asignado,
        clave_asignada=req.clave_asignada,
        cantidad_total=req.cantidad_total,
        descripcion=req.descripcion or "",
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.post("/{lote_id}/activate", summary="Activar un lote para la sesión de flasheo")
def activate_lote(lote_id: int, operator: dict = Depends(require_operator)):
    ok, msg = database.set_active_lote(lote_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}
