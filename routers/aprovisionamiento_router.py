import os
import sys
from fastapi import APIRouter, Request, Depends, HTTPException, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Import aprovisionamiento routes
from aprovisionamiento.web.routes import (
    handle_probe, handle_provision, handle_provision_onu_only,
    handle_progress, handle_history, handle_export_excel,
    handle_get_config, handle_save_config, handle_get_credentials,
    handle_save_credentials, handle_system_status, handle_get_vlans_catalog,
    handle_flasheo_traceability, handle_get_unconfigured, handle_get_onu_status,
    handle_get_onu_mac, handle_smartolt_authorize, handle_smartolt_migrate_vlan,
    handle_smartolt_release_onu, handle_get_smartolt_profiles, handle_save_smartolt_config
)

import security
from database import get_db
import models

templates = Jinja2Templates(directory="templates")

router = APIRouter()
api_router = APIRouter(prefix="/api/aprovisionamiento")

def wrap_handler(handler_func, req_data=None):
    res, code = handler_func(req_data) if req_data is not None else handler_func()
    return JSONResponse(content=res, status_code=code)

@api_router.post("/probe")
async def probe(data: dict = Body(...)):
    return wrap_handler(handle_probe, data)

@api_router.post("/provision")
async def provision(data: dict = Body(...)):
    return wrap_handler(handle_provision, data)

@api_router.post("/provision/onu_only")
async def provision_onu_only(data: dict = Body(...)):
    return wrap_handler(handle_provision_onu_only, data)

@api_router.get("/progress")
async def progress(job_id: str = ""):
    res, code = handle_progress(job_id)
    return JSONResponse(content=res, status_code=code)

@api_router.get("/history")
async def history(limit: int = 50):
    res, code = handle_history(limit)
    return JSONResponse(content=res, status_code=code)

@api_router.get("/status")
async def status():
    return wrap_handler(handle_system_status)

@api_router.get("/config")
async def get_config():
    return wrap_handler(handle_get_config)

@api_router.post("/config")
async def save_config(data: dict = Body(...)):
    return wrap_handler(handle_save_config, data)

@api_router.get("/smartolt/unconfigured")
async def smartolt_unconfigured():
    return wrap_handler(handle_get_unconfigured)

@api_router.post("/smartolt/authorize")
async def smartolt_authorize(data: dict = Body(...)):
    return wrap_handler(handle_smartolt_authorize, data)

@api_router.get("/vlans/catalog")
async def vlans_catalog(olt_id: str = None):
    res, code = handle_get_vlans_catalog(olt_id)
    return JSONResponse(content=res, status_code=code)

@api_router.get("/flasheo/onu_traceability")
async def flasheo_traceability(query: str = ""):
    res, code = handle_flasheo_traceability(query)
    return JSONResponse(content=res, status_code=code)

router.include_router(api_router)

@router.get("/soporte/aprovisionamiento", response_class=HTMLResponse)
async def aprovisionamiento_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if user.role not in ["admin"] and "ver_aprovisionamiento" not in (user.permissions or ""):
            return RedirectResponse(url="/")
        return templates.TemplateResponse("aprovisionamiento.html", {"request": request, "user": user})
    except HTTPException:
        return RedirectResponse(url="/login")
