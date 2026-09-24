import os
import sys
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from flasheo.api.v1 import api_v1_router
import security
from database import get_db
import models

# Intranet templates
templates = Jinja2Templates(directory="templates")

router = APIRouter()
# Mouting the flasheo API under /api/flasheo to avoid conflict
router.include_router(api_v1_router, prefix="/api/flasheo")

@router.get("/soporte/flasheo", response_class=HTMLResponse)
async def flasheo_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if user.role not in ["admin"] and "ver_flasheo" not in (user.permissions or ""):
            return RedirectResponse(url="/")
        return templates.TemplateResponse("flasheo.html", {"request": request, "user": user})
    except HTTPException:
        return RedirectResponse(url="/login")
