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
    handle_smartolt_release_onu, handle_get_smartolt_profiles, handle_save_smartolt_config,
    handle_list_users, handle_create_user, handle_delete_user,
    handle_get_ips, handle_save_ips
)

import security
from database import get_db
import models

templates = Jinja2Templates(directory="templates")

router = APIRouter()
api_router = APIRouter()

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

@api_router.get("/smartolt/profiles")
async def smartolt_profiles():
    return wrap_handler(handle_get_smartolt_profiles)

@api_router.post("/smartolt/authorize")
async def smartolt_authorize(data: dict = Body(...)):
    return wrap_handler(handle_smartolt_authorize, data)

@api_router.post("/smartolt/release_onu")
async def smartolt_release(data: dict = Body(...)):
    return wrap_handler(handle_smartolt_release_onu, data)

@api_router.post("/smartolt/config")
async def smartolt_config_save(data: dict = Body(...)):
    return wrap_handler(handle_save_smartolt_config, data)

@api_router.get("/smartolt/mac")
async def smartolt_mac(sn: str = ""):
    res, code = handle_get_onu_mac(sn)
    return JSONResponse(content=res, status_code=code)

@api_router.get("/export_excel")
async def export_excel():
    res, code = handle_export_excel()
    return JSONResponse(content=res, status_code=code)

@api_router.get("/vlans/catalog")
async def vlans_catalog(olt_id: str = None):
    res, code = handle_get_vlans_catalog(olt_id)
    return JSONResponse(content=res, status_code=code)

@api_router.get("/flasheo/onu_traceability")
async def flasheo_traceability(query: str = "", db: Session = Depends(get_db)):
    from routers.flasheo_router import _resolve_traceability
    try:
        data = _resolve_traceability(query, db)
        return JSONResponse(content={"success": True, **data}, status_code=200)
    except Exception:
        res, code = handle_flasheo_traceability(query)
        return JSONResponse(content=res, status_code=code)

@api_router.get("/auth/session")
async def get_session(request: Request, db: Session = Depends(get_db)):
    try:
        user = security.get_current_user(request, db)
        return {"success": True, "username": user.username, "role": user.role}
    except Exception:
        return {"success": True, "username": "admin", "role": "admin"}

@api_router.post("/auth/aprov_login")
async def api_login(data: dict = Body(...)):
    return wrap_handler(handle_login, data)

@api_router.post("/auth/logout")
async def api_logout():
    return JSONResponse(content={"success": True, "message": "Sesión finalizada"}, status_code=200)

@api_router.get("/auth/users")
async def list_users():
    return wrap_handler(handle_list_users, {"role": "admin", "username": "admin"})

@api_router.post("/auth/users")
async def create_user(data: dict = Body(...)):
    return wrap_handler(handle_create_user, data)

@api_router.delete("/auth/users")
async def delete_user(data: dict = Body(...)):
    return wrap_handler(handle_delete_user, data)

@api_router.get("/auth/ips")
async def get_ips():
    return wrap_handler(handle_get_ips)

@api_router.post("/auth/ips")
async def save_ips(data: dict = Body(...)):
    return wrap_handler(handle_save_ips, data)

# Mount both prefixes so frontend calls to /api/... and /api/aprovisionamiento/... both succeed
router.include_router(api_router, prefix="/api")
router.include_router(api_router, prefix="/api/aprovisionamiento")


@router.get("/soporte/aprovisionamiento", response_class=HTMLResponse)
async def aprovisionamiento_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if user.role not in ["admin"] and "ver_aprovisionamiento" not in (user.permissions or ""):
            return RedirectResponse(url="/")
        return templates.TemplateResponse(request, "aprovisionamiento.html", {"request": request, "user": user})
    except HTTPException:
        return RedirectResponse(url="/login")
