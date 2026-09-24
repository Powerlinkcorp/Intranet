# -*- coding: utf-8 -*-
"""
api.v1.endpoints.onus — Rutas de Consulta de ONUs y Consulta Externa de Credenciales.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response, status
from flasheo.core import database
from flasheo.core.schemas import ONUResponse, ONUExternalResponse

router = APIRouter(prefix="/onus", tags=["ONUs y Consulta Externa"])


@router.get(
    "/{identificador}/credentials",
    response_model=ONUExternalResponse,
    summary="Consultar credencial de una ONU (API Externa)",
    description=(
        "Endpoint diseñado para que otras aplicaciones consulten qué clave y usuario "
        "posee una ONU específica. Acepta Dirección MAC (ej. 4C:46:D1:E3:E0:21 o 4c46d1e3e021) "
        "o GPON Serial Number (ej. VSOL00E3E021 o 4c46d1-4c46d1e3e021)."
    )
)
def get_onu_credentials(identificador: str):
    data = database.lookup_onu_credentials(identificador)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ninguna ONU registrada con el identificador '{identificador}'."
        )
    return data


@router.get("", response_model=List[ONUResponse], summary="Listar historial de ONUs procesadas")
def get_onus(
    limit: int = Query(200, ge=1, le=1000),
    lote_id: Optional[int] = None,
    resultado: Optional[str] = None
):
    return database.list_onus(limit=limit, lote_id=lote_id, resultado=resultado)
