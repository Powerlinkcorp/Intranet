import os
import shutil
import io
import re
import asyncio
import pandas as pd
from typing import List, Optional
import uuid
try:
    from PIL import Image
except ImportError:
    Image = None
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, Depends, HTTPException, status, Request, Form, File, UploadFile, Response, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from database import engine, get_db, Base
import models
import security
import email_util

load_dotenv()

# Ensure required directories exist
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "static/uploads")
DOCS_DIR = "static/docs"
IMG_DIR = "static/img"

for d in [UPLOAD_DIR, DOCS_DIR, IMG_DIR]:
    os.makedirs(d, exist_ok=True)

# Create sample doc files if missing
sample_docs = ["manual_empleado_2026.pdf", "planilla_vacaciones.pdf", "app_helpdesk.pdf", "plantilla_informe.docx"]
for doc_name in sample_docs:
    doc_path = os.path.join(DOCS_DIR, doc_name)
    if not os.path.exists(doc_path):
        with open(doc_path, "wb") as f:
            f.write(f"Contenido demo para {doc_name} en la Intranet Corporativa.".encode("utf-8"))

app = FastAPI(
    title="Intranet Platform API",
    description="Sistema de Intranet Corporativa con PostgreSQL y Autenticación JWT Robusta",
    version="1.0.0"
)

# Security Headers & CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # Content Security Policy (CSP) contra spyware y exfiltracion de datos
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
        "img-src 'self' data: blob: https://ngfihmioixtfnrmlrlam.supabase.co https://ui-avatars.com; "
        "connect-src 'self' ws: wss: https://powerlinkcorp.telecomti.net; "
        "frame-ancestors 'self'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    response.headers["Content-Security-Policy"] = csp_policy

    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Mount Static Files and Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

import permissions_manager
templates.env.globals["has_perm"] = permissions_manager.user_has_perm
templates.env.globals["has_any_perm"] = permissions_manager.user_has_any_perm
templates.env.globals["get_perm_registry"] = permissions_manager.load_registry
templates.env.globals["build_powertrack_perms"] = permissions_manager.build_powertrack_permissions_dict
templates.env.globals["get_user_perms_list"] = permissions_manager.get_user_effective_perms_list

# Import new routers
from routers.flasheo_router import router as flasheo_app_router
from routers.aprovisionamiento_router import router as aprov_app_router

app.include_router(flasheo_app_router)
app.include_router(aprov_app_router)

try:
    from routers.operaciones_router import router as operaciones_router
    app.include_router(operaciones_router)
except ImportError:
    pass

# Pydantic Schemas
class FeedbackCreate(BaseModel):
    content: str

class ChatMessageCreate(BaseModel):
    message: str

class KpiItem(BaseModel):
    title: str
    value: str
    trend: str = "up"

class KpiListUpdate(BaseModel):
    metrics: List[KpiItem]

class CalendarEventCreate(BaseModel):
    day: int
    title: str
    description: Optional[str] = None

class ExtensionUpdate(BaseModel):
    name: str

class ExtensionCreate(BaseModel):
    department: str
    name: str
    extension: str
    is_group: bool = False

class WorkerUpdate(BaseModel):
    email: str
    department: str
    cargo: str
    birthday_date: str
    full_name: str
    cedula: str

class SuspendUserRequest(BaseModel):
    suspension_reason: str

class UserUpdateWithSMTP(BaseModel):
    email: str
    password: Optional[str] = None
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None

class ConnectionManager:
    def __init__(self):
        # Email -> Conjunto de WebSockets activos (soporte multi-pestaña)
        self.active_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, email: str, websocket: WebSocket):
        await websocket.accept()
        is_first = email not in self.active_connections or len(self.active_connections[email]) == 0
        if email not in self.active_connections:
            self.active_connections[email] = set()
        self.active_connections[email].add(websocket)
        if is_first:
            await self.broadcast({"type": "presence", "email": email, "status": "online"})

    async def disconnect(self, email: str, websocket: WebSocket = None):
        if email in self.active_connections:
            if websocket and websocket in self.active_connections[email]:
                self.active_connections[email].discard(websocket)
            else:
                self.active_connections[email].clear()

            if not self.active_connections[email]:
                del self.active_connections[email]
                await self.broadcast({"type": "presence", "email": email, "status": "offline"})

    def get_online_emails(self) -> set[str]:
        return {email for email, conns in self.active_connections.items() if len(conns) > 0}

    async def broadcast(self, message: dict):
        for conns in list(self.active_connections.values()):
            for connection in list(conns):
                try:
                    await connection.send_json(message)
                except Exception:
                    pass
                
    async def send_personal_message(self, message: dict, email: str):
        if email in self.active_connections:
            for connection in list(self.active_connections[email]):
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()

# ==========================================
# RUTAS DE AUTENTICACIÓN
# ==========================================
@app.post("/api/auth/login")
async def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    client_ip = request.client.host if request.client else "unknown"

    # Rate limiting check
    if security.is_rate_limited(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Tu IP está temporalmente bloqueada por 5 minutos.",
        )

    clean_user = form_data.username.strip()
    user = db.query(models.User).filter(
        (models.User.username.ilike(clean_user)) |
        (models.User.email.ilike(clean_user))
    ).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        security.record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo o suspendido. Contacta a Administración/RRHH.",
        )

    # Success: reset rate limit attempts for this IP
    security.clear_failed_attempts(client_ip)

    access_token = security.create_access_token(data={"sub": user.username, "role": user.role})

    # Set HTTP-Only Secure Cookie
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age= security.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "permissions": user.permissions or "",
            "avatar_url": user.avatar_url
        }
    }

@app.post("/api/auth/logout")
@app.get("/api/auth/logout")
async def api_auth_logout():
    response = JSONResponse(content={"status": "success", "message": "Sesión cerrada correctamente."})
    response.delete_cookie(key="access_token", path="/", httponly=True, samesite="lax")
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="token", path="/")
    return response

@app.get("/logout")
async def logout_redirect():
    response = RedirectResponse(url="/login?logout=1", status_code=302)
    response.delete_cookie(key="access_token", path="/", httponly=True, samesite="lax")
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="token", path="/")
    return response

@app.get("/api/auth/me")
async def get_me(current_user: models.User = Depends(security.get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "permissions": current_user.permissions or "",
        "avatar_url": current_user.avatar_url
    }

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        current_user = security.get_current_user(request, db)
    except (HTTPException, Exception):
        return RedirectResponse(url="/login")

    all_users = db.query(models.User).filter(models.User.is_active == True).all()
    employees = db.query(models.Employee).all()
    emp_map = {emp.name: emp.department for emp in employees}
    online_emails = manager.get_online_emails()
    
    departments = {}
    for u in all_users:
        dept = emp_map.get(u.full_name, "General")
        if dept not in departments:
            departments[dept] = []
        departments[dept].append(u)

    return templates.TemplateResponse(request, "chat.html", {
        "request": request,
        "user": current_user,
        "departments": departments,
        "online_emails": online_emails
    })

# Helper para parsear fechas de cumpleaños en español ("19 de Enero", "YYYY-MM-DD", "DD/MM/YYYY")
MONTH_MAP = {
    'enero': 1, 'ene': 1,
    'febrero': 2, 'feb': 2,
    'marzo': 3, 'mar': 3,
    'abril': 4, 'abr': 4,
    'mayo': 5, 'may': 5,
    'junio': 6, 'jun': 6,
    'julio': 7, 'jul': 7,
    'agosto': 8, 'ago': 8,
    'septiembre': 9, 'sep': 9, 'setiembre': 9,
    'octubre': 10, 'oct': 10,
    'noviembre': 11, 'nov': 11,
    'diciembre': 12, 'dic': 12
}

def parse_birthday_day_month(bday_str: str):
    if not bday_str or not isinstance(bday_str, str):
        return None
    s = bday_str.strip().lower()
    
    # 1. Formato "DD de Mes" (ej: "19 de Enero", "3 de Febrero")
    m = re.match(r'^(\d{1,2})\s+de\s+([a-záéíóú]+)', s)
    if m:
        day = int(m.group(1))
        mes_str = m.group(2).replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        month = MONTH_MAP.get(mes_str)
        if month and 1 <= day <= 31:
            return day, month

    # 2. Formato ISO "YYYY-MM-DD"
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if m:
        month = int(m.group(2))
        day = int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return day, month

    # 3. Formato "DD/MM/YYYY" o "DD/MM//YYYY" o "DD-MM-YYYY"
    m = re.match(r'^(\d{1,2})[/\\-]+(\d{1,2})', s)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return day, month
        elif 1 <= day <= 12 and 1 <= month <= 31:
            return month, day

    # 4. Formato "Mes DD" (ej: "Enero 19")
    m = re.match(r'^([a-záéíóú]+)\s+(\d{1,2})', s)
    if m:
        mes_str = m.group(1).replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        day = int(m.group(2))
        month = MONTH_MAP.get(mes_str)
        if month and 1 <= day <= 31:
            return day, month

    return None

# ==========================================
# RUTAS DE INTRANET GENERAL (USUARIOS)
# ==========================================
@app.get("/api/intranet/dashboard")
async def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    hero = db.query(models.Announcement).filter(models.Announcement.is_active == True).first()
    resources = db.query(models.Resource).order_by(models.Resource.id.desc()).all()
    employees = db.query(models.Employee).all()
    kpis = db.query(models.KpiMetric).all()
    calendar_events = db.query(models.CalendarEvent).all()

    # Encuentra el próximo cumpleaños
    all_emps_with_bday = db.query(models.Employee).filter(models.Employee.birthday_date != None, models.Employee.birthday_date != "").all()
    closest_emp = None
    if all_emps_with_bday:
        today = datetime.now().date()
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        
        def get_next_bday_info(emp):
            parsed = parse_birthday_day_month(emp.birthday_date)
            if not parsed:
                return datetime(9999, 12, 31).date(), ""
            b_day, b_month = parsed
            try:
                calc_day = 28 if (b_month == 2 and b_day == 29) else b_day
                target = datetime(today.year, b_month, calc_day).date()
                if target < today:
                    target = datetime(today.year + 1, b_month, calc_day).date()
                formatted_str = f"{b_day} de {meses[b_month - 1]}"
                return target, formatted_str
            except Exception:
                return datetime(9999, 12, 31).date(), ""

        sorted_emps = sorted(all_emps_with_bday, key=lambda e: get_next_bday_info(e)[0])
        if sorted_emps:
            closest_emp = sorted_emps[0]
            _, formatted_date = get_next_bday_info(closest_emp)
            if formatted_date:
                closest_emp.birthday_date = formatted_date

    birthday_emp = closest_emp

    return {
        "user": {
            "full_name": current_user.full_name,
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role,
            "permissions": current_user.permissions or "",
            "avatar_url": current_user.avatar_url
        },
        "hero": hero,
        "resources": resources,
        "employees": employees,
        "kpis": kpis,
        "calendar_events": calendar_events,
        "birthday_employee": birthday_emp
    }

@app.post("/api/feedback")
async def create_feedback(
    data: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    fb = models.Feedback(user_email=current_user.email, content=data.content)
    db.add(fb)
    db.commit()
    return {"message": "Feedback guardado exitosamente."}

import json

@app.get("/reportes", response_class=HTMLResponse)
async def reportes_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if not permissions_manager.user_has_any_perm(user, ['sub_admin_reportes', 'ver_reportes', 'perm_reporte']):
            return RedirectResponse(url="/")
        return templates.TemplateResponse(request, "reportes.html", {"request": request, "user": user})
    except (HTTPException, Exception):
        return RedirectResponse(url="/login")
@app.get("/api/chat")
async def get_chat_messages(
    channel: str = "#General",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    # Actualizar estado de lectura
    read_state = db.query(models.ChatReadState).filter(
        models.ChatReadState.user_email == current_user.email,
        models.ChatReadState.channel == channel
    ).first()
    if not read_state:
        read_state = models.ChatReadState(user_email=current_user.email, channel=channel)
        db.add(read_state)
    else:
        read_state.last_read_timestamp = datetime.now()
    db.commit()

    messages = db.query(models.ChatMessage).filter(models.ChatMessage.channel == channel).order_by(models.ChatMessage.id.asc()).limit(50).all()
    return messages

@app.get("/api/chat/unread")
async def get_unread_channels(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    # Encontrar mensajes recientes
    # Para optimizar, se podría agrupar por canal, pero haremos un approach simple.
    unread_channels = set()
    
    # 1. Obtener los timestamps de lectura del usuario
    read_states = db.query(models.ChatReadState).filter(models.ChatReadState.user_email == current_user.email).all()
    read_map = {rs.channel: rs.last_read_timestamp for rs in read_states}
    
    # 2. Buscar canales con mensajes dirigidos al usuario o generales
    # Por simplicidad, traemos los ultimos 500 mensajes de todos los canales que le importan
    recent_messages = db.query(models.ChatMessage).order_by(models.ChatMessage.id.desc()).limit(200).all()
    
    for msg in recent_messages:
        # Solo evaluar mensajes que el usuario deba ver (general o directos)
        if msg.channel == "#General" or current_user.email in msg.channel:
            last_read = read_map.get(msg.channel)
            if not last_read or msg.created_at > last_read:
                # No considerar los mensajes que el propio usuario envió como "no leídos"
                if msg.user_email != current_user.email:
                    unread_channels.add(msg.channel)
                    
    return {"unread": list(unread_channels)}

@app.websocket("/api/ws/chat")
async def websocket_chat(websocket: WebSocket, db: Session = Depends(get_db)):
    token = websocket.query_params.get("token") or websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if token.startswith("Bearer "):
        token = token[len("Bearer "):]
    
    try:
        username = security._decode_token(token)
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            raise Exception()
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(user.email, websocket)
    try:
        while True:
            data_str = await websocket.receive_text()
            try:
                data = json.loads(data_str)
            except:
                # Fallback para mensajes de texto plano del chat antiguo
                data = {"message": data_str, "recipient_email": None}
                
            recipient_email = data.get("recipient_email")
            message_text = data.get("message")
            
            if recipient_email:
                emails = sorted([user.email, recipient_email])
                channel = f"private_{emails[0]}_{emails[1]}"
            else:
                channel = "#General"

            # Save to db
            msg = models.ChatMessage(
                user_email=user.email,
                user_name=user.full_name,
                channel=channel,
                message=message_text
            )
            db.add(msg)
            db.commit()
            
            payload = {
                "user_name": user.full_name,
                "user_email": user.email,
                "message": message_text,
                "channel": channel
            }
            
            # Broadcast o personal
            if recipient_email:
                await manager.send_personal_message(payload, recipient_email)
                # Opcional: enviarlo a ti mismo (si tienes varias pestañas)
                if recipient_email != user.email:
                    await manager.send_personal_message(payload, user.email)
            else:
                await manager.broadcast(payload)
    except WebSocketDisconnect:
        await manager.disconnect(user.email, websocket)
    except Exception:
        await manager.disconnect(user.email, websocket)

# ==========================================
# RUTAS DE GESTIÓN DE RRHH / ADMIN
# ==========================================
@app.post("/api/rrhh/hero")
async def update_hero_banner(
    title: Optional[str] = Form(None),
    image_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    hero = db.query(models.Announcement).first()
    if not hero:
        hero = models.Announcement(title="Bienvenido a la Intranet")
        db.add(hero)

    if title:
        hero.title = title

    if image_file and image_file.filename:
        filename = f"hero_{int(datetime.utcnow().timestamp())}_{image_file.filename}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(image_file.file, buffer)
        hero.image_url = f"/{UPLOAD_DIR}/{filename}"

    db.commit()
    db.refresh(hero)
    return {"message": "Anuncio principal actualizado.", "hero": hero}

@app.get("/api/rrhh/resources")
async def list_resources(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    return db.query(models.Resource).order_by(models.Resource.id.desc()).all()

@app.post("/api/rrhh/resources")
async def upload_resource(
    title: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    filename = f"doc_{int(datetime.utcnow().timestamp())}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_url = f"/{UPLOAD_DIR}/{filename}"
    res_obj = models.Resource(
        title=title,
        category=category,
        file_path=file_url,
        file_type=file.filename.split(".")[-1]
    )
    db.add(res_obj)
    db.commit()
    db.refresh(res_obj)
    return {"message": "Recurso publicado con éxito.", "resource": res_obj}

@app.delete("/api/rrhh/resources/{resource_id}")
async def delete_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    res_obj = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not res_obj:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    db.delete(res_obj)
    db.commit()
    return {"message": "Recurso eliminado."}

@app.get("/api/rrhh/departments")
async def get_departments(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    return db.query(models.Department).order_by(models.Department.name).all()

@app.post("/api/rrhh/departments")
async def add_department(
    name: str = Form(...),
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    dep = db.query(models.Department).filter(models.Department.name == name).first()
    if dep:
        raise HTTPException(status_code=400, detail="El departamento ya existe.")
    
    new_dep = models.Department(name=name)
    db.add(new_dep)
    db.commit()
    db.refresh(new_dep)
    return {"message": "Departamento creado con éxito.", "department": new_dep}

@app.post("/api/rrhh/employees")
async def add_employee(
    name: str = Form(...),
    apellido: str = Form(...),
    position: str = Form(...),
    department: str = Form(None),
    cedula: str = Form(None),
    birthday_date: str = Form(None),
    email: str = Form(None),
    smtp_user: str = Form(None),
    smtp_pass: str = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    if cedula:
        existing = db.query(models.Employee).filter(models.Employee.cedula == cedula).first()
        if existing:
            raise HTTPException(status_code=400, detail="Empleado ya se encuentra en sistema")

    if email:
        existing_emp = db.query(models.Employee).filter(models.Employee.email == email).first()
        if existing_emp:
            raise HTTPException(status_code=400, detail="El correo electrónico ya existe para otro empleado.")

    usuario = (name[0] + apellido).lower() if name and apellido else "usuario"
    base_username = usuario
    counter = 1
    while db.query(models.User).filter(models.User.username == usuario).first():
        usuario = f"{base_username}{counter}"
        counter += 1
        
    import random
    palabras = ['Power', 'Link', 'Gravity', 'System', 'Secure', 'Admin']
    password = random.choice(palabras) + random.choice(['*','#','$','&','@']) + str(random.randint(100,999))

    photo_url = "https://ngfihmioixtfnrmlrlam.supabase.co/storage/v1/object/public/power/WhatsApp_Image_2026-03-20_at_3.44.14_PM-removebg-preview.png"
    if photo and photo.filename:
        filename = f"emp_{int(datetime.utcnow().timestamp())}_{photo.filename}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)
        photo_url = f"/{UPLOAD_DIR}/{filename}"

    emp = models.Employee(name=name, apellido=apellido, email=email, position=position, department=department or "General", 
cedula=cedula, birthday_date=birthday_date, photo_url=photo_url)
    db.add(emp)
    
    hashed_pw = security.get_password_hash(password)
    new_user = models.User(
        username=usuario,
        email=email or f"{usuario}@empresa.com",
        hashed_password=hashed_pw,
        full_name=f"{name} {apellido}",
        role="user",
        avatar_url=photo_url,
        cargo=position,
        department=department or "General",
        birthday_date=birthday_date
    )
    db.add(new_user)
        
    db.commit()
    db.refresh(emp)
    
    # Send email
    if email:
        email_util.send_welcome_email(email, name, usuario, password, is_update=False)
        
    return {"message": "Empleado y credenciales agregados.", "employee": emp}

@app.put("/api/rrhh/employees/{emp_id}")
async def update_employee(
    emp_id: int,
    name: str = Form(...),
    apellido: str = Form(...),
    department: str = Form(None),
    cedula: str = Form(None),
    birthday_date: str = Form(None),
    email: str = Form(None),
    smtp_user: str = Form(None),
    smtp_pass: str = Form(None),
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
        
    # Validations for unique fields if they changed
    if cedula and cedula != emp.cedula:
        if db.query(models.Employee).filter(models.Employee.cedula == cedula).first():
            raise HTTPException(status_code=400, detail="Cédula ya está en uso")
            
    if email and email != emp.email:
        if db.query(models.Employee).filter(models.Employee.email == email).first():
            raise HTTPException(status_code=400, detail="Correo ya está en uso")

    emp.name = name
    emp.apellido = apellido
    emp.department = department or "General"
    emp.cedula = cedula
    emp.birthday_date = birthday_date
    emp.email = email
    
    db.commit()
    db.refresh(emp)
    
    if email:
        email_util.send_welcome_email(email, name, "", "", is_update=True)

    return {"message": "Empleado actualizado exitosamente.", "employee": emp}

@app.post("/api/rrhh/kpis")
async def update_kpis(
    data: KpiListUpdate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    # Clear and replace or update
    db.query(models.KpiMetric).delete()
    for item in data.metrics:
        db.add(models.KpiMetric(title=item.title, value=item.value, trend=item.trend))
    db.commit()
    return {"message": "Métricas KPI actualizadas."}


@app.post("/api/rrhh/calendar")
async def add_calendar_event(
    data: CalendarEventCreate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    evt = models.CalendarEvent(day=data.day, title=data.title, description=data.description)
    db.add(evt)
    db.commit()
    return {"message": "Evento agregado al calendario."}

@app.get("/api/rrhh/users")
async def list_users_permissions(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    users = db.query(models.User).order_by(models.User.full_name).all()
    employees_dict = {e.email: e.cedula for e in db.query(models.Employee).filter(models.Employee.email != None).all()}
    return [{
        "id": u.id,
        "full_name": u.full_name,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "permissions": u.permissions or "",
        "department": u.department or "",
        "cargo": u.cargo or "",
        "birthday_date": u.birthday_date or "",
        "is_active": u.is_active,
        "cedula": employees_dict.get(u.email) or ""
    } for u in users]

@app.post("/api/rrhh/users/{user_id}/permissions")
async def update_user_permissions(
    user_id: int,
    permissions: str = Form(""),
    role: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if role is not None and role.strip():
        user.role = role.strip().lower()
    raw_list = [p.strip() for p in (permissions or "").split(",") if p.strip()]
    normalized = permissions_manager.normalize_permissions_list(raw_list)
    user.permissions = ",".join(normalized)
    db.commit()
    return {
        "message": "Rol y permisos actualizados correctamente",
        "role": user.role,
        "permissions": user.permissions
    }

@app.get("/api/permisos/registry")
async def api_get_permisos_registry(
    current_user: models.User = Depends(security.get_current_user)
):
    return permissions_manager.load_registry()

@app.get("/api/permisos/audit")
async def api_get_permisos_audit(
    limit: int = Query(100),
    admin_user: models.User = Depends(security.require_admin)
):
    return {"logs": permissions_manager.get_permission_audit_logs(limit=limit)}

@app.post("/api/permisos/users/{user_id}")
async def api_update_user_role_and_permissions(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    payload = await request.json()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    old_role = (user.role or "user").lower()
    new_role = str(payload.get("role", old_role)).strip().lower()
    raw_perms = payload.get("permissions", [])
    if isinstance(raw_perms, str):
        raw_perms = [p.strip() for p in raw_perms.split(",") if p.strip()]

    # Protección Anti-Bloqueo (Self-Lockout Guard)
    if user.id == admin_user.id and old_role == "admin" and new_role != "admin":
        raise HTTPException(
            status_code=400,
            detail="Protección Anti-Bloqueo: No puedes quitarte tu propio rol de Administrador activo."
        )
    if old_role == "admin" and new_role != "admin":
        other_admins = db.query(models.User).filter(
            models.User.role == "admin",
            models.User.is_active == True,
            models.User.id != user.id
        ).count()
        if other_admins == 0:
            raise HTTPException(
                status_code=400,
                detail="Protección Anti-Bloqueo: Debe existir al menos un Administrador activo en el sistema."
            )

    user.role = new_role
    if new_role == "admin":
        reg = permissions_manager.load_registry()
        user.permissions = ",".join(reg["all_keys"])
    else:
        normalized = permissions_manager.normalize_permissions_list(raw_perms)
        user.permissions = ",".join(normalized)
    db.commit()

    client_ip = request.client.host if request.client else "local"
    eff_list = list(permissions_manager.expand_effective_permissions(user.role, user.permissions))
    permissions_manager.log_permission_audit(
        actor_username=admin_user.username,
        action="ACTUALIZAR_USUARIO",
        target=f"{user.full_name} ({user.username})",
        details=f"Rol: {old_role.upper()} -> {new_role.upper()} | Total llaves activas: {len(eff_list)}",
        ip=client_ip
    )

    return {
        "status": "ok",
        "message": f"Permisos de {user.full_name} guardados exitosamente",
        "user": {
            "id": user.id,
            "role": user.role,
            "permissions": user.permissions,
            "effective_permissions": eff_list
        }
    }

@app.post("/api/permisos/bulk-assign")
async def api_bulk_assign_role_or_permissions(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    payload = await request.json()
    user_ids = payload.get("user_ids", [])
    target_role = str(payload.get("role", "")).strip().lower()
    if not user_ids or not target_role:
        raise HTTPException(status_code=400, detail="Selecciona al menos un usuario y un rol válido.")

    reg = permissions_manager.load_registry()
    role_obj = next((r for r in reg["roles"] if r["id"] == target_role), None)
    if not role_obj:
        raise HTTPException(status_code=404, detail="Rol no encontrado en el catálogo.")

    perm_str = ",".join(reg["all_keys"] if target_role == "admin" else role_obj.get("permissions", []))
    updated_users = []

    for uid in user_ids:
        u = db.query(models.User).filter(models.User.id == int(uid)).first()
        if not u:
            continue
        # No degradar al propio admin en lote
        if u.id == admin_user.id and (u.role or "").lower() == "admin" and target_role != "admin":
            continue
        u.role = target_role
        u.permissions = perm_str
        updated_users.append({
            "id": u.id,
            "role": u.role,
            "effective_permissions": list(permissions_manager.expand_effective_permissions(u.role, u.permissions))
        })

    db.commit()
    client_ip = request.client.host if request.client else "local"
    permissions_manager.log_permission_audit(
        actor_username=admin_user.username,
        action="ASIGNACION_MASIVA_ROL",
        target=f"{len(updated_users)} usuarios",
        details=f"Asignó el rol '{role_obj['name']}' ({target_role}) en lote",
        ip=client_ip
    )
    return {
        "status": "ok",
        "message": f"Rol '{role_obj['name']}' aplicado a {len(updated_users)} usuario(s)",
        "updated_users": updated_users
    }

@app.post("/api/permisos/roles")
async def api_save_or_update_role(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    payload = await request.json()
    registry = permissions_manager.save_or_update_role(payload)
    role_id = str(payload.get("id", "")).strip().lower().replace(" ", "_")
    sync_users = bool(payload.get("sync_assigned_users", True))
    updated_count = 0
    if sync_users and role_id and role_id not in ("admin", "personalizado"):
        role_obj = next((r for r in registry["roles"] if r["id"] == role_id), None)
        if role_obj:
            perm_str = ",".join(role_obj.get("permissions", []))
            assigned_users = db.query(models.User).filter(models.User.role == role_id).all()
            for u in assigned_users:
                u.permissions = perm_str
                updated_count += 1
            if updated_count > 0:
                db.commit()

    client_ip = request.client.host if request.client else "local"
    permissions_manager.log_permission_audit(
        actor_username=admin_user.username,
        action="GUARDAR_PLANTILLA_ROL",
        target=f"Rol: {payload.get('name', role_id)} ({role_id})",
        details=f"Plantilla actualizada ({updated_count} usuarios sincronizados)",
        ip=client_ip
    )
    return {
        "status": "ok",
        "message": f"Rol guardado correctamente ({updated_count} usuarios sincronizados)",
        "registry": registry
    }

@app.delete("/api/permisos/roles/{role_id}")
async def api_delete_custom_role(
    role_id: str,
    request: Request,
    admin_user: models.User = Depends(security.require_admin)
):
    registry = permissions_manager.delete_custom_role(role_id)
    client_ip = request.client.host if request.client else "local"
    permissions_manager.log_permission_audit(
        actor_username=admin_user.username,
        action="ELIMINAR_ROL",
        target=f"Rol ID: {role_id}",
        details="Plantilla de rol personalizada eliminada",
        ip=client_ip
    )
    return {"status": "ok", "message": "Rol eliminado", "registry": registry}

@app.post("/api/permisos/catalogo")
async def api_register_new_window_or_permission(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    payload = await request.json()
    registry = permissions_manager.add_custom_window_or_permission(payload)
    assign_roles = payload.get("assign_roles", [])
    if assign_roles:
        for rid in assign_roles:
            role_obj = next((r for r in registry["roles"] if r["id"] == rid), None)
            if role_obj and rid != "admin":
                perm_str = ",".join(role_obj.get("permissions", []))
                for u in db.query(models.User).filter(models.User.role == rid).all():
                    u.permissions = perm_str
        db.commit()

    client_ip = request.client.host if request.client else "local"
    permissions_manager.log_permission_audit(
        actor_username=admin_user.username,
        action="REGISTRAR_VENTANA_O_PERMISO",
        target=f"{payload.get('name', '')} ({payload.get('id', '')})",
        details=f"Tipo: {payload.get('target_type')} | Roles asignados: {', '.join(assign_roles) if assign_roles else 'Solo Admin'}",
        ip=client_ip
    )
    return {
        "status": "ok",
        "message": "Nueva ventana / permiso registrado e integrado al sistema de roles",
        "registry": registry
    }

@app.put("/api/rrhh/users/{user_id}/edit-worker")
async def edit_worker_info(
    user_id: int,
    email: str = Form(...),
    department: str = Form(""),
    cargo: str = Form(""),
    birthday_date: str = Form(""),
    full_name: str = Form(""),
    cedula: str = Form(""),
    avatar: UploadFile = File(None),
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    user.email = email
    user.department = department
    user.cargo = cargo
    user.birthday_date = birthday_date
    user.full_name = full_name
    user.cedula = cedula
    
    if avatar and avatar.filename:
        upload_dir = "static/uploads/avatars"
        os.makedirs(upload_dir, exist_ok=True)
        new_filename = f"{uuid.uuid4().hex}.webp"
        filepath = os.path.join(upload_dir, new_filename)
        try:
            image = Image.open(avatar.file)
            image = image.convert("RGB")
            image.thumbnail((400, 400))
            image.save(filepath, "WEBP", quality=85)
            user.avatar_url = f"/{filepath.replace(os.sep, '/')}"
        except Exception as e:
            print("Error procesando imagen:", e)
            
    db.commit()
    return {"message": "Datos de trabajador actualizados"}

@app.post("/api/rrhh/users/{user_id}/activate")
async def activate_worker(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.is_active = True
    user.suspension_reason = ""
    db.commit()
    return {"message": "Usuario activado exitosamente"}

@app.post("/api/rrhh/users/{user_id}/suspend")
async def suspend_worker(
    user_id: int,
    data: SuspendUserRequest,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.is_active = False
    user.suspension_reason = data.suspension_reason
    db.commit()
    return {"message": "Usuario suspendido exitosamente"}

@app.post("/api/rrhh/users/{user_id}/resend-password")
async def resend_password(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    import random
    import string
    import logging
    logger = logging.getLogger("security")
    new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    user.hashed_password = security.get_password_hash(new_password)
    db.commit()
    logger.warning(f"AUDIT_SECURITY: Admin '{admin_user.username}' restablecio la contrasena del usuario '{user.username}' (ID: {user.id})")
    return {
        "message": f"Contraseña restablecida para el usuario '{user.username}'.\n\nATENCIÓN: Debe entregar manualmente esta clave temporal al trabajador para que pueda ingresar:\n\n{new_password}",
        "temporary_password": new_password
    }

@app.delete("/api/rrhh/users/{user_id}")
async def delete_worker_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.id == admin_user.id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta de administrador")

    # Si existe en Employee con el mismo email o nombre, eliminarlo también
    if user.email:
        emp = db.query(models.Employee).filter((models.Employee.email == user.email) | (models.Employee.name == user.full_name)).first()
        if emp:
            db.delete(emp)

    db.delete(user)
    db.commit()
    return {"message": f"Trabajador '{user.full_name}' eliminado correctamente de la base de datos"}

@app.delete("/api/rrhh/employees/{emp_id}")
async def delete_single_employee(
    emp_id: int,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    
    if emp.email:
        user = db.query(models.User).filter(models.User.email == emp.email).first()
        if user and user.role != 'admin':
            db.delete(user)

    db.delete(emp)
    db.commit()
    return {"message": f"Empleado '{emp.name}' eliminado correctamente"}

@app.get("/api/popup")
async def get_popup_notification(
    db: Session = Depends(get_db)
):
    popup = db.query(models.PopupNotification).order_by(models.PopupNotification.id.desc()).first()
    if popup and popup.is_active:
        return {"message": popup.message}
    return {"message": ""}

@app.post("/api/rrhh/popup")
async def update_popup_notification(
    message: str = Form(""),
    is_active: str = Form("true"),
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    is_act = is_active.lower() == "true"
    popup = db.query(models.PopupNotification).first()
    if not popup:
        popup = models.PopupNotification(message=message, is_active=is_act)
        db.add(popup)
    else:
        popup.message = message
        popup.is_active = is_act
    db.commit()
    return {"status": "success", "message": "Pop-up actualizado."}

# ==========================================
# RUTAS DE PLANTILLAS VISTA HTML
# ==========================================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    is_logout = request.query_params.get("logout") == "1"
    if not is_logout:
        token = security.get_token_from_request(request)
        if token:
            try:
                user = security.get_current_user(request, db)
                if user and user.is_active:
                    return RedirectResponse(url="/")
            except Exception:
                pass
    embed = request.query_params.get("embed") == "1"
    response = templates.TemplateResponse(request, "login.html", {"embed": embed})
    if is_logout:
        response.delete_cookie(key="access_token", path="/", httponly=True, samesite="lax")
        response.delete_cookie(key="access_token", path="/")
        response.delete_cookie(key="token", path="/")
    return response

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        return templates.TemplateResponse(request, "home.html", {"request": request, "user": user})
    except (HTTPException, Exception):
        return RedirectResponse(url="/login")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if not permissions_manager.user_has_any_perm(user, ["sub_admin_panel", "sub_admin_trabajadores", "cargar_datos_usuarios", "editar_usuarios", "act_trabajadores_ver"]):
            return RedirectResponse(url="/")
        
        employees = db.query(models.Employee).all()
        departments = db.query(models.Department).all()
        
        return templates.TemplateResponse(request, "rrhh.html", {
            "user": user,
            "employees": employees,
            "departments": departments
        })
    except (HTTPException, Exception):
        return RedirectResponse(url="/login")

@app.get("/admin/permisos", response_class=HTMLResponse)
async def admin_permisos_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if user.role != "admin" and not permissions_manager.user_has_any_perm(user, ["sub_admin_permisos", "gestionar_permisos", "act_permisos_ver"]):
            return RedirectResponse(url="/")
        users = db.query(models.User).order_by(models.User.full_name).all()
        registry = permissions_manager.load_registry()
        users_serialized = []
        for u in users:
            eff = list(permissions_manager.expand_effective_permissions(u.role, u.permissions or "", registry["catalog"]))
            users_serialized.append({
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "email": u.email,
                "role": (u.role or "user").lower(),
                "department": u.department or "General",
                "cargo": u.cargo or "",
                "is_active": u.is_active,
                "avatar_url": u.avatar_url or "",
                "permissions_raw": u.permissions or "",
                "effective_permissions": eff
            })
        return templates.TemplateResponse(request, "permisos.html", {
            "user": user,
            "users": users,
            "users_json": json.dumps(users_serialized, ensure_ascii=False),
            "registry_json": json.dumps(registry, ensure_ascii=False)
        })
    except (HTTPException, Exception):
        return RedirectResponse(url="/login")

@app.get("/integracion", response_class=HTMLResponse)
async def integracion_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if not permissions_manager.user_has_any_perm(user, ["sub_admin_integracion", "ver_integracion"]):
            return RedirectResponse(url="/")
        embed = request.query_params.get("embed") == "1"
        return templates.TemplateResponse(request, "integracion.html", {"user": user, "embed": embed})
    except (HTTPException, Exception):
        return RedirectResponse(url="/login")

@app.get("/helpdesk", response_class=HTMLResponse)
async def helpdesk_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        # Permiso abierto por defecto para todos
        return templates.TemplateResponse(request, "helpdesk.html", {"user": user})
    except (HTTPException, Exception):
        return RedirectResponse(url="/login")

def safe_date_str(val):
    if pd.isna(val) or val == "":
        return ""
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y")
    return str(val).split(" ")[0]

import urllib.request
import urllib.parse
import json
import time

def _do_fetch(api_token, is_nat):
    if is_nat is False:
        export_url = "https://powerlink.rubpi.com/api/exports/users?is_natural=false"
    elif is_nat is True:
        export_url = "https://powerlink.rubpi.com/api/exports/users?is_natural=true"
    else:
        export_url = "https://powerlink.rubpi.com/api/exports/users"

    req2 = urllib.request.Request(export_url, headers={'Authorization': f'Bearer {api_token}', 'Content-Type': 'application/json', 'Accept': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req2) as response:
            res2_data = json.loads(response.read().decode())
            task_id = res2_data.get('task_id') or res2_data.get('id')
    except Exception as e:
        raise Exception(f"Error al iniciar exportación: {str(e)}")

    if not task_id:
        raise Exception("No se obtuvo task_id")

    get_url = f"https://powerlink.rubpi.com/api/exports/users/{task_id}"
    
    for i in range(25): # try for 75 seconds
        time.sleep(3)
        req3 = urllib.request.Request(get_url, headers={'Authorization': f'Bearer {api_token}'}, method='GET')
        try:
            with urllib.request.urlopen(req3) as response:
                res3_data = json.loads(response.read().decode())
                return res3_data
        except urllib.error.HTTPError as e:
            if e.code == 400:
                continue
            raise Exception("Error de API: " + str(e.code))
        except Exception as e:
            raise Exception(f"Error al consultar tarea: {str(e)}")

    raise Exception("Tiempo de espera agotado para la tarea")

def fetch_powerlink_data(is_natural: Optional[bool] = None):
    login_url = "https://powerlink.rubpi.com/api/login"
    creds = {"username": "api_exp", "password": "-?J+\\FcmKT2zWl5A28=~"}
    data = json.dumps(creds).encode('utf-8')

    req = urllib.request.Request(login_url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            api_token = res_data.get('token') or res_data.get('access_token')
    except Exception as e:
        raise Exception(f"Error en login API: {str(e)}")

    if not api_token:
        raise Exception("No se pudo obtener token de la API")

    if is_natural is None:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_res = executor.submit(_do_fetch, api_token, True)
            future_corp = executor.submit(_do_fetch, api_token, False)
            data_res = future_res.result()
            data_corp = future_corp.result()
            
        combined = data_res.get("data", []) + data_corp.get("data", [])
        return {"data": combined}
    else:
        return _do_fetch(api_token, is_natural)

def scheduled_snapshot_job():
    """Guardado automático diario de snapshots (Residencial/Total y Corporativo) a las 8:00 PM."""
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp_str}] [AUTO-SNAPSHOT] Iniciando guardado automático programado de las 8:00 PM...")
    
    # 1. Guardar snapshot general
    try:
        data_gen = fetch_powerlink_data(is_natural=None)
        with open(os.path.join(UPLOAD_DIR, "last_snapshot.json"), "w", encoding="utf-8") as f:
            json.dump(data_gen, f)
        print(f"[{timestamp_str}] [AUTO-SNAPSHOT] OK Snapshot general/residencial guardado exitosamente ({len(data_gen)} contratos).")
    except Exception as e:
        print(f"[{timestamp_str}] [AUTO-SNAPSHOT] Error guardando snapshot general: {e}")

    # 2. Guardar snapshot corporativo
    try:
        data_corp = fetch_powerlink_data(is_natural=False)
        with open(os.path.join(UPLOAD_DIR, "last_snapshot_corporativo.json"), "w", encoding="utf-8") as f:
            json.dump(data_corp, f)
        print(f"[{timestamp_str}] [AUTO-SNAPSHOT] OK Snapshot corporativo guardado exitosamente ({len(data_corp)} contratos).")
    except Exception as e:
        print(f"[{timestamp_str}] [AUTO-SNAPSHOT] Error guardando snapshot corporativo: {e}")

# Iniciar scheduler diario a las 8:00 PM (20:00)
try:
    snapshot_scheduler = BackgroundScheduler()
    snapshot_scheduler.add_job(
        scheduled_snapshot_job,
        'cron',
        hour=20,
        minute=0,
        id='daily_snapshot_8pm',
        replace_existing=True
    )
    snapshot_scheduler.start()
    print("[SCHEDULER] Programador de tareas iniciado: Guardado automático de snapshot activo a las 8:00 PM (20:00 diario).")
except Exception as e:
    print(f"[SCHEDULER] Advertencia al iniciar programador: {e}")

@app.get("/api/integracion/api_users")
def get_api_users(request: Request, is_natural: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        data = fetch_powerlink_data(is_natural=is_natural)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/integracion/guardar_snapshot")
def guardar_snapshot(request: Request, tipo: str = Form("todos"), db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        if tipo.lower() == "corporativo":
            data = fetch_powerlink_data(is_natural=False)
            snapshot_path = os.path.join(UPLOAD_DIR, "last_snapshot_corporativo.json")
            label_tipo = "corporativo "
        elif tipo.lower() == "residencial":
            data = fetch_powerlink_data(is_natural=True)
            snapshot_path = os.path.join(UPLOAD_DIR, "last_snapshot.json")
            label_tipo = "residencial "
        else:
            data = fetch_powerlink_data(is_natural=None)
            snapshot_path = os.path.join(UPLOAD_DIR, "last_snapshot.json")
            label_tipo = ""
            
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
            
        current_time = datetime.now().strftime("%d/%m/%Y a las %I:%M %p")
        return {"message": f"Registro {label_tipo}guardado exitosamente.", "time": current_time}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/integracion/estado_respaldos")
def estado_respaldos(request: Request):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    def get_file_info(filename):
        path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(path):
            mtime = os.path.getmtime(path)
            return datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %I:%M %p")
        return "No disponible"

    return {
        "diario_residencial": get_file_info("last_snapshot.json"),
        "diario_corporativo": get_file_info("last_snapshot_corporativo.json"),
        "base_mensual": get_file_info("base_mensual.xlsx"),
        "base_mensual_corporativo": get_file_info("base_mensual_corporativo.xlsx")
    }

@app.post("/api/integracion/guardar_base_mensual")
async def guardar_base_mensual(request: Request, file_base: UploadFile = File(...)):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        content = await file_base.read()
        file_path = os.path.join(UPLOAD_DIR, "base_mensual.xlsx")
        with open(file_path, "wb") as f:
            f.write(content)
        return {"message": "Base mensual guardada exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/integracion/guardar_base_mensual_corporativo")
async def guardar_base_mensual_corporativo(request: Request, file_base: UploadFile = File(...)):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        content = await file_base.read()
        file_path = os.path.join(UPLOAD_DIR, "base_mensual_corporativo.xlsx")
        with open(file_path, "wb") as f:
            f.write(content)
        return {"message": "Base mensual corporativa guardada exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/integracion/procesar_api")
async def procesar_auditoria_api(
    request: Request,
    db: Session = Depends(get_db),
    fileOld: Optional[UploadFile] = File(None),
    fechaCorte: str = Form(...),
    fechaInstalaciones: str = Form(...),
    tipoCliente: str = Form("todos"),
    tipoComparativa: str = Form("diaria")
):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")
        
    is_corp = (tipoCliente.lower() == "corporativo")
    is_natural_param = False if is_corp else (True if tipoCliente.lower() == "residencial" else None)

    try:
        data_new = fetch_powerlink_data(is_natural=is_natural_param)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo datos actuales: {str(e)}")
        
    old_dict = {}
    if fileOld and fileOld.filename:
        # Modo: Comparar con Excel Subido
        content_old = await fileOld.read()
        df_old = pd.read_excel(io.BytesIO(content_old))
        df_old = df_old.fillna("")
        for _, row in df_old.iterrows():
            sid = str(row.get('ID Servicio', '')).strip()
            if sid:
                raw_st = str(row.get('Estado servicio', '')).strip().upper()
                if raw_st in ('EXONERADO', 'EXO.'): mapped_st = 'Exo.'
                elif raw_st in ('SUSPENDIDO', 'SUSP.'): mapped_st = 'Susp.'
                elif raw_st in ('POR RETIRAR', 'POR RET.'): mapped_st = 'Por Ret.'
                elif raw_st in ('TRANSFERIDO', 'TRANS.'): mapped_st = 'Trans.'
                elif raw_st in ('RETIRADO', 'RET.'): mapped_st = 'Ret.'
                elif raw_st in ('ACTIVO', 'ACT.'): mapped_st = 'Act.'
                else: mapped_st = raw_st.title() if raw_st else ''
                
                old_dict[sid] = {
                    'ID Servicio': sid,
                    'Cédula': str(row.get('Cédula', '')).strip(),
                    'Nombres': str(row.get('Nombres', '')).strip(),
                    'Plan': row.get('Plan', ''),
                    'Estado servicio': mapped_st,
                    'Costo del plan': row.get('Costo del plan', 0)
                }
    elif tipoComparativa == "mensual":
        # Modo: Comparar con Base Mensual (Excel guardado)
        is_todos = (tipoCliente.lower() == "todos")
        base_paths = []
        if is_todos or tipoCliente.lower() == "residencial":
            base_paths.append(os.path.join(UPLOAD_DIR, "base_mensual.xlsx"))
        if is_todos or tipoCliente.lower() == "corporativo":
            base_paths.append(os.path.join(UPLOAD_DIR, "base_mensual_corporativo.xlsx"))
            
        found_any = False
        for path in base_paths:
            if os.path.exists(path):
                found_any = True
                try:
                    df_old = pd.read_excel(path)
                    df_old = df_old.fillna("")
                    for idx, row in df_old.iterrows():
                        sid = str(row.get('ID Servicio', '')).strip()
                        if sid:
                            raw_st = str(row.get('Estado servicio', '')).strip().upper()
                            if raw_st in ('EXONERADO', 'EXO.'): mapped_st = 'Exo.'
                            elif raw_st in ('SUSPENDIDO', 'SUSP.'): mapped_st = 'Susp.'
                            elif raw_st in ('POR RETIRAR', 'POR RET.'): mapped_st = 'Por Ret.'
                            elif raw_st in ('TRANSFERIDO', 'TRANS.'): mapped_st = 'Trans.'
                            elif raw_st in ('RETIRADO', 'RET.'): mapped_st = 'Ret.'
                            elif raw_st in ('ACTIVO', 'ACT.'): mapped_st = 'Act.'
                            else: mapped_st = raw_st.title() if raw_st else ''
                            
                            old_dict[sid] = {
                                'ID Servicio': sid,
                                'Cédula': str(row.get('Cédula', '')).strip(),
                                'Nombres': str(row.get('Nombres', '')).strip(),
                                'Plan': row.get('Plan', ''),
                                'Estado servicio': mapped_st,
                                'Costo del plan': row.get('Costo del plan', 0)
                            }
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Error leyendo la base mensual en {path}: {str(e)}")
        
        if not found_any:
            raise HTTPException(status_code=400, detail="No existen bases mensuales guardadas para la selección actual. Por favor, carga el archivo del día 1 primero.")
    else:
        # Modo: Comparar con Snapshot Local Diaria
        is_todos = (tipoCliente.lower() == "todos")
        
        try:
            if is_todos:
                # Load both
                path_res = os.path.join(UPLOAD_DIR, "last_snapshot.json")
                path_corp = os.path.join(UPLOAD_DIR, "last_snapshot_corporativo.json")
                list_old = []
                if os.path.exists(path_res):
                    with open(path_res, "r", encoding="utf-8") as f:
                        list_old.extend(json.load(f).get("data", []))
                if os.path.exists(path_corp):
                    with open(path_corp, "r", encoding="utf-8") as f:
                        list_old.extend(json.load(f).get("data", []))
                if not list_old:
                    raise Exception("No existen snapshots guardados.")
            else:
                snapshot_filename = "last_snapshot_corporativo.json" if is_corp else "last_snapshot.json"
                snapshot_path = os.path.join(UPLOAD_DIR, snapshot_filename)
                if not os.path.exists(snapshot_path):
                    raise HTTPException(status_code=400, detail=f"No existe un registro anterior ({'corporativo' if is_corp else 'general'}). Por favor, haz clic en 'Guardar Registro Anterior' antes de comparar, o sube un Excel.")
                    
                with open(snapshot_path, "r", encoding="utf-8") as f:
                    list_old = json.load(f).get("data", [])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error leyendo el registro anterior: {str(e)}")
            
        for item in list_old:
            sid = str(item.get('id_servicio', '')).strip()
            if sid:
                raw_st = str(item.get('service_status', '')).strip().upper()
                if raw_st == 'EXONERADO': mapped_st = 'Exo.'
                elif raw_st == 'SUSPENDIDO': mapped_st = 'Susp.'
                elif raw_st == 'POR RETIRAR': mapped_st = 'Por Ret.'
                elif raw_st == 'TRANSFERIDO': mapped_st = 'Trans.'
                elif raw_st == 'RETIRADO': mapped_st = 'Ret.'
                elif raw_st == 'ACTIVO': mapped_st = 'Act.'
                else: mapped_st = raw_st.title() if raw_st else ''
                
                old_dict[sid] = {
                    'ID Servicio': sid,
                    'Cédula': f"{item.get('doc_type', '')}-{item.get('doc', '')}",
                    'Nombres': item.get('name', ''),
                    'Plan': item.get('plan', ''),
                    'Estado servicio': mapped_st,
                    'Costo del plan': item.get('amount', 0)
                }

    list_new = data_new.get("data", [])
    
    def map_to_excel_format(item):
        raw_st = str(item.get('service_status', '')).strip().upper()
        if raw_st == 'EXONERADO': mapped_st = 'Exo.'
        elif raw_st == 'SUSPENDIDO': mapped_st = 'Susp.'
        elif raw_st == 'POR RETIRAR': mapped_st = 'Por Ret.'
        elif raw_st == 'TRANSFERIDO': mapped_st = 'Trans.'
        elif raw_st == 'RETIRADO': mapped_st = 'Ret.'
        elif raw_st == 'ACTIVO': mapped_st = 'Act.'
        else: mapped_st = raw_st.title() if raw_st else ''
        
        doc_t = str(item.get('doc_type', '')).strip().upper()
        # In Venezuela, J, G, or C are corporate (Juridico, Gubernamental, Comuna)
        is_nat = doc_t not in ('J', 'G', 'C')
        if 'is_natural' in item:
            is_nat = bool(item['is_natural'])
            
        return {
            'ID Servicio': item.get('id_servicio', ''),
            'Cédula': f"{item.get('doc_type', '')}-{item.get('doc', '')}",
            'Nombres': item.get('name', ''),
            'Plan': item.get('plan', ''),
            'Tipo de servicio': item.get('service_type', ''),
            'Costo del plan': item.get('amount', 0),
            'Estado servicio': mapped_st,
            'Saldo actual': item.get('balance', 0),
            'Fecha última cambio de estado': item.get('last_status_change_date', ''),
            'Plan actual desde': item.get('current_plan_since', ''),
            'Fecha de instalación': item.get('creation_date', ''),
            'Teléfono 1': item.get('phone', ''),
            'Urbanismo': item.get('urban', ''),
            'is_natural': is_nat
        }

    try:
        corte_dt = datetime.strptime(fechaCorte, "%Y-%m-%d")
    except:
        hoy = datetime.now()
        corte_dt = datetime(hoy.year, hoy.month, 1)
        
    try:
        inst_dt = datetime.strptime(fechaInstalaciones, "%Y-%m-%d")
        inst_str = inst_dt.strftime("%d/%m/%Y")
    except:
        inst_str = ""

    is_excel_uploaded = bool(fileOld and fileOld.filename)
    today_str = datetime.now().strftime("%d/%m/%Y")

    totalActivos = 0
    totalActivosCorp = 0
    totalSuspendidosFecha = 0
    totalSuspendidosFechaCorp = 0
    totalExoneradosEmp = 0
    totalExoneradosReg = 0
    totalExoneradosRegCorp = 0
    
    # Variables Conciliación Residencial
    ingreso_ayer = 0.0
    ingreso_hoy = 0.0
    count_activos_ayer = 0
    count_activos_hoy = 0
    
    emp_exo_qty = 0
    emp_exo_mnt = 0.0
    res_exo_qty = 0
    res_exo_mnt = 0.0
    upgrades_qty = 0
    upgrades_mnt = 0.0
    cambios_3m_qty = 0
    cambios_3m_mnt = 0.0
    reconex_qty = 0
    reconex_mnt = 0.0
    reconex_exo_qty = 0
    reconex_exo_mnt = 0.0
    inst_3m_qty = 0
    inst_3m_mnt = 0.0
    inst_norm_qty = 0
    inst_norm_mnt = 0.0
    downgrades_qty = 0
    downgrades_mnt = 0.0
    susp_qty = 0
    susp_mnt = 0.0
    
    # Variables Conciliación Corporativa
    ingreso_ayer_corp = 0.0
    ingreso_hoy_corp = 0.0
    count_activos_ayer_corp = 0
    count_activos_hoy_corp = 0
    
    emp_exo_qty_corp = 0
    emp_exo_mnt_corp = 0.0
    res_exo_qty_corp = 0
    res_exo_mnt_corp = 0.0
    upgrades_qty_corp = 0
    upgrades_mnt_corp = 0.0
    cambios_3m_qty_corp = 0
    cambios_3m_mnt_corp = 0.0
    reconex_qty_corp = 0
    reconex_mnt_corp = 0.0
    reconex_exo_qty_corp = 0
    reconex_exo_mnt_corp = 0.0
    inst_3m_qty_corp = 0
    inst_3m_mnt_corp = 0.0
    inst_norm_qty_corp = 0
    inst_norm_mnt_corp = 0.0
    downgrades_qty_corp = 0
    downgrades_mnt_corp = 0.0
    susp_qty_corp = 0
    susp_mnt_corp = 0.0
    
    impacto_exclusion_tv = 0.0
    count_exclusion_tv = 0
    
    fechaCorte = datetime.now().strftime("%Y-%m-01")

    processed_sids = set()
    
    datosInstalaciones = []
    datosInstalacionesProceso = []
    datosCambiosPlan = []
    datosSeguimiento = []
    datosEstatus = []
    datosDeudores = []
    datosConciliacionDetalle = []
    datosClientesActivos = []
    
    def parse_amount(val):
        if val is None: return 0.0
        if isinstance(val, (int, float)): return float(val)
        s = str(val).replace('$', '').replace(' ', '').strip()
        if not s: return 0.0
        s = s.replace(',', '.')
        if s.count('.') > 1:
            parts = s.rsplit('.', 1)
            s = parts[0].replace('.', '') + '.' + parts[1]
        try:
            return float(s)
        except:
            return 0.0
            
    for item in list_new:
        row = map_to_excel_format(item)
        sid = str(row['ID Servicio']).strip()
        if not sid:
            continue
            
        processed_sids.add(sid)
            
        planNew = str(row['Plan']).strip()
        tipoServicioNew = str(row['Tipo de servicio']).strip().upper()
        
        try:
            costoDelPlanNew = parse_amount(row['Costo del plan'])
        except:
            costoDelPlanNew = 0.0
            
        if planNew.upper() == 'TV' or tipoServicioNew == 'IPTV':
            continue
            
        estadoServicioNew = str(row['Estado servicio']).strip().upper()
        
        try:
            saldoActual = parse_amount(row['Saldo actual'])
        except:
            saldoActual = 0.0
            
        raw_estado = row['Fecha última cambio de estado']
        raw_plan = row['Plan actual desde']
        raw_inst = row['Fecha de instalación']
        
        fechaEstadoFormat = safe_date_str(raw_estado)
        fechaPlanDesdeFormat = safe_date_str(raw_plan)
        fechaInstalacionFormat = safe_date_str(raw_inst)
        
        estado_dt = datetime.min
        inst_p_current = None
        plan_p = None
        if raw_estado:
            date_only = str(raw_estado).split("T")[0].split(" ")[0][:10]
            try:
                estado_dt = datetime.strptime(date_only, "%Y-%m-%d")
                fechaEstadoFormat = estado_dt.strftime("%d/%m/%Y")
            except:
                pass

        if raw_inst:
            date_only = str(raw_inst).split("T")[0].split(" ")[0][:10]
            try:
                inst_p_current = datetime.strptime(date_only, "%Y-%m-%d")
                fechaInstalacionFormat = inst_p_current.strftime("%d/%m/%Y")
            except:
                pass
                 
        if raw_plan:
             date_only = str(raw_plan).split("T")[0].split(" ")[0][:10]
             try:
                 plan_p = datetime.strptime(date_only, "%Y-%m-%d")
                 fechaPlanDesdeFormat = plan_p.strftime("%d/%m/%Y")
             except:
                 pass
                
        if estadoServicioNew == 'ACT.':
            if tipoServicioNew in ['PYME', 'CORPORATIVO']:
                totalActivosCorp += 1
                ingreso_hoy_corp += costoDelPlanNew
                count_activos_hoy_corp += 1
            else:
                totalActivos += 1
                ingreso_hoy += costoDelPlanNew
            datosClientesActivos.append({
                'ID Servicio': sid,
                'Cédula': row['Cédula'],
                'Nombres': row['Nombres'],
                'Plan': planNew,
                'Tipo de servicio': row['Tipo de servicio'],
                'Costo del plan': costoDelPlanNew,
                'Estado servicio': row['Estado servicio'],
                'Saldo Actual': saldoActual,
                'Fecha de instalación': fechaInstalacionFormat,
                'Teléfono 1': row['Teléfono 1'],
                'Urbanismo': row['Urbanismo']
            })
        elif estadoServicioNew == 'SUSP.':
            try:
                corte_res = corte_dt.replace(day=6)
            except ValueError:
                corte_res = corte_dt
                
            try:
                corte_corp = corte_dt.replace(day=10)
            except ValueError:
                corte_corp = corte_dt

            if tipoServicioNew in ['PYME', 'CORPORATIVO']:
                if estado_dt >= corte_corp:
                    totalSuspendidosFechaCorp += 1
            else:
                if estado_dt >= corte_res:
                    totalSuspendidosFecha += 1
        elif estadoServicioNew == 'EXO.':
            plan_lower = planNew.lower()
            if 'iptv' not in plan_lower and 'tv' not in plan_lower:
                nombre_lower = str(row.get('Nombres', '')).lower().strip()
                if '(emp)' in nombre_lower:
                    totalExoneradosEmp += 1
                else:
                    if tipoServicioNew in ['PYME', 'CORPORATIVO']:
                        totalExoneradosRegCorp += 1
                    else:
                        totalExoneradosReg += 1
                        
        is_this_corp = tipoServicioNew in ['PYME', 'CORPORATIVO']
                
        is_missing_in_old = (sid not in old_dict)
        
        is_in_range = False
        if inst_p_current and corte_dt and inst_dt:
            if corte_dt <= inst_p_current <= inst_dt:
                is_in_range = True
        
        if estadoServicioNew == 'ACT.' and (is_in_range or is_missing_in_old):
            datosInstalaciones.append({
                'ID Servicio': sid,
                'Cédula': row['Cédula'],
                'Nombres': row['Nombres'],
                'Estado servicio': row['Estado servicio'],
                'Plan': row['Plan'],
                'Costo del plan': row['Costo del plan'],
                'Fecha de instalación': fechaInstalacionFormat,
                'Urbanismo': row['Urbanismo'],
                'Saldo Actual': saldoActual
            })
                
        if estadoServicioNew == 'ACT.' and fechaInstalacionFormat == today_str:
            datosInstalacionesProceso.append({
                'ID Servicio': sid,
                'Cédula': row['Cédula'],
                'Nombres': row['Nombres'],
                'Estado servicio': row['Estado servicio'],
                'Plan': row['Plan'],
                'Costo del plan': row['Costo del plan'],
                'Fecha de instalación': fechaInstalacionFormat,
                'Urbanismo': row['Urbanismo'],
                'Saldo Actual': saldoActual
            })
                
        if estadoServicioNew == 'ACT.' and saldoActual < 0:
            datosDeudores.append({
                'ID Servicio': sid,
                'Cédula': row['Cédula'],
                'Nombres': row['Nombres'],
                'Estado servicio': row['Estado servicio'],
                'Saldo Actual (Deuda)': saldoActual,
                'Plan': row['Plan'],
                'Costo del plan': row['Costo del plan'],
                'Fecha Último Cambio Estado': fechaEstadoFormat,
                'Teléfono 1': row['Teléfono 1']
            })
            
        is_plan_in_range = True
        if plan_p and corte_dt and inst_dt:
            is_plan_in_range = (corte_dt <= plan_p <= inst_dt)
            
        is_estado_in_range = True
        if estado_dt and corte_dt and inst_dt:
            is_estado_in_range = (corte_dt <= estado_dt <= inst_dt)
            
        is_instalacion_in_range = True
        if inst_p_current and corte_dt and inst_dt:
            is_instalacion_in_range = (corte_dt <= inst_p_current <= inst_dt)
            
        row_old = old_dict.get(sid)
        if row_old is not None:
            planOld = str(row_old['Plan']).strip()
            estatusOld = str(row_old['Estado servicio']).strip().upper()
            estatusNew = estadoServicioNew
            try:
                costoOld = parse_amount(row_old['Costo del plan'])
            except:
                costoOld = 0.0
                
            billingAyer = costoOld if estatusOld == 'ACT.' else 0.0
            billingHoy = costoDelPlanNew if estatusNew == 'ACT.' else 0.0
            variacionNeta = billingHoy - billingAyer
            
            if estatusOld == 'ACT.':
                if is_this_corp:
                    ingreso_ayer_corp += costoOld
                    count_activos_ayer_corp += 1
                else:
                    ingreso_ayer += costoOld
                    count_activos_ayer += 1
                
            # Finanzas - Bridge (Conciliación Financiera)
            if estatusOld != 'EXO.' and estatusNew == 'EXO.':
                if 'EMP' in str(row.get('Nombres', '')).upper() or 'EMP' in row.get('Cédula', '').upper():
                    if is_this_corp:
                        emp_exo_qty_corp += 1
                        emp_exo_mnt_corp += variacionNeta
                    else:
                        emp_exo_qty += 1
                        emp_exo_mnt += variacionNeta
                else:
                    if is_this_corp:
                        res_exo_qty_corp += 1
                        res_exo_mnt_corp += variacionNeta
                    else:
                        res_exo_qty += 1
                        res_exo_mnt += variacionNeta
                        
            elif estatusOld == 'ACT.' and estatusNew == 'ACT.':
                if costoDelPlanNew > costoOld:
                    if '3 MESES BENEFICIO' in planOld.upper() and '3 MESES BENEFICIO' not in planNew.upper():
                        if is_this_corp:
                            cambios_3m_qty_corp += 1
                            cambios_3m_mnt_corp += variacionNeta
                        else:
                            cambios_3m_qty += 1
                            cambios_3m_mnt += variacionNeta
                    else:
                        if is_this_corp:
                            upgrades_qty_corp += 1
                            upgrades_mnt_corp += variacionNeta
                        else:
                            upgrades_qty += 1
                            upgrades_mnt += variacionNeta
                elif costoDelPlanNew < costoOld:
                    if is_this_corp:
                        downgrades_qty_corp += 1
                        downgrades_mnt_corp += variacionNeta
                    else:
                        downgrades_qty += 1
                        downgrades_mnt += variacionNeta
                        
            elif estatusOld in ['SUSP.', 'RET.', 'POR RET.', 'EXO.'] and estatusNew == 'ACT.':
                if estatusOld == 'EXO.':
                    if is_this_corp:
                        reconex_exo_qty_corp += 1
                        reconex_exo_mnt_corp += variacionNeta
                    else:
                        reconex_exo_qty += 1
                        reconex_exo_mnt += variacionNeta
                else:
                    if is_this_corp:
                        reconex_qty_corp += 1
                        reconex_mnt_corp += variacionNeta
                    else:
                        reconex_qty += 1
                        reconex_mnt += variacionNeta
                
            elif estatusOld == 'ACT.' and estatusNew in ['SUSP.', 'RET.', 'POR RET.']:
                if is_this_corp:
                    susp_qty_corp += 1
                    susp_mnt_corp += variacionNeta
                else:
                    susp_qty += 1
                    susp_mnt += variacionNeta
            
            if planOld != planNew and is_plan_in_range:
                datosCambiosPlan.append({
                    'ID Servicio': sid,
                    'Cédula': row['Cédula'],
                    'Nombres': row['Nombres'],
                    'Plan Anterior': planOld,
                    'Plan Nuevo': planNew,
                    'Costo Anterior': costoOld,
                    'Costo Nuevo': costoDelPlanNew,
                    'Variación de Costo': variacionNeta,
                    'Estado Actual': row['Estado servicio'],
                    'Estado Anterior': estatusOld,
                    'Estado Nuevo': estatusNew,
                    'Fecha Plan Actual Desde': fechaPlanDesdeFormat 
                })
                
            if (planOld != planNew and is_plan_in_range) or (estatusOld != estatusNew and is_estado_in_range):
                datosSeguimiento.append({
                    'ID Servicio': sid,
                    'Cédula': row['Cédula'],
                    'Nombres': row['Nombres'],
                    'Plan Anterior': planOld,
                    'Plan Nuevo': planNew,
                    'Costo Anterior': costoOld,
                    'Costo Nuevo': costoDelPlanNew,
                    'Variación de Costo': variacionNeta,
                    'Estado Anterior': estatusOld,
                    'Estado Nuevo': estatusNew,
                    'Fecha Último Cambio Estado': fechaEstadoFormat,
                    'Fecha Plan Actual Desde': fechaPlanDesdeFormat
                })
                
            if estatusOld != estatusNew and is_estado_in_range:
                datosEstatus.append({
                    'ID Servicio': sid,
                    'Cédula': row['Cédula'],
                    'Nombres': row['Nombres'],
                    'Plan Actual': planNew,
                    'Costo Anterior': costoOld,
                    'Costo Nuevo': costoDelPlanNew,
                    'Variación de Costo': variacionNeta,
                    'Estado Anterior': estatusOld,
                    'Estado Nuevo': estatusNew,
                    'Fecha Último Cambio Estado': fechaEstadoFormat
                })
        else:
            if estadoServicioNew == 'ACT.' and is_missing_in_old:
                if '3 MESES BENEFICIO' in planNew.upper():
                    if is_this_corp:
                        inst_3m_qty_corp += 1
                        inst_3m_mnt_corp += costoDelPlanNew
                    else:
                        inst_3m_qty += 1
                        inst_3m_mnt += costoDelPlanNew
                else:
                    if is_this_corp:
                        inst_norm_qty_corp += 1
                        inst_norm_mnt_corp += costoDelPlanNew
                    else:
                        inst_norm_qty += 1
                        inst_norm_mnt += costoDelPlanNew

    for sid, row_old in old_dict.items():
        if sid not in processed_sids:
            tipoServicioOld = str(row_old.get('Tipo de servicio', '')).strip().upper()
            planOld = str(row_old.get('Plan', '')).strip().upper()
            if planOld == 'TV' or tipoServicioOld == 'IPTV':
                continue
                
            is_this_corp = tipoServicioOld in ['PYME', 'CORPORATIVO']
                
            estatusOld = str(row_old['Estado servicio']).strip().upper()
            try:
                costoOld = parse_amount(row_old['Costo del plan'])
            except:
                costoOld = 0.0
                
            if estatusOld == 'ACT.':
                if is_this_corp:
                    ingreso_ayer_corp += costoOld
                    count_activos_ayer_corp += 1
                    susp_qty_corp += 1
                    susp_mnt_corp -= costoOld
                else:
                    ingreso_ayer += costoOld
                    count_activos_ayer += 1
                    susp_qty += 1
                    susp_mnt -= costoOld
                    
                datosConciliacionDetalle.append({
                    'ID Servicio': sid,
                    'Cédula': row_old.get('Cédula', '') or '-',
                    'Nombres': row_old.get('Nombres', '') or '-',
                    'Concepto': 'Retiros',
                    'Plan Anterior': str(row_old.get('Plan', '')),
                    'Plan Actual': '-',
                    'Estado Anterior': estatusOld,
                    'Estado Actual': 'No encontrado',
                    'Costo Anterior': costoOld,
                    'Costo Actual': 0.0,
                    'Variación': -costoOld,
                    'Fecha': '-'
                })

    def _sort_by_nombres(x): return x.get('Nombres', '')
    
    datosInstalaciones.sort(key=_sort_by_nombres)
    datosInstalacionesProceso.sort(key=_sort_by_nombres)
    datosCambiosPlan.sort(key=_sort_by_nombres)
    datosSeguimiento.sort(key=_sort_by_nombres)
    datosEstatus.sort(key=_sort_by_nombres)
    datosDeudores.sort(key=_sort_by_nombres)
    datosConciliacionDetalle.sort(key=_sort_by_nombres)
    datosClientesActivos.sort(key=_sort_by_nombres)

    # Generar cuadro resumen agrupado de Clientes Activos por Plan
    plan_aggregates = {}
    for c in datosClientesActivos:
        is_this_corp = c.get('Tipo de servicio', '').strip().upper() in ['PYME', 'CORPORATIVO']
        p_name = c['Plan'] or 'Sin Plan'
        if is_this_corp:
            p_name += " (Corp)"
        if p_name not in plan_aggregates:
            plan_aggregates[p_name] = {
                'Plan': p_name,
                'Cantidad': 0,
                'Sumatoria Costo': 0.0,
                'Precios': set()
            }
        plan_aggregates[p_name]['Cantidad'] += 1
        plan_aggregates[p_name]['Sumatoria Costo'] += float(c['Costo del plan'] or 0.0)
        plan_aggregates[p_name]['Precios'].add(float(c['Costo del plan'] or 0.0))

    datosPlanesActivos = []
    for p_name, p_data in plan_aggregates.items():
        cnt = p_data['Cantidad']
        tot_cost = p_data['Sumatoria Costo']
        precios_list = sorted(list(p_data['Precios']))
        precio_unitario_str = " / ".join([f"${p:g}" for p in precios_list]) if precios_list else "$0.00"
        precio_ref = precios_list[0] if len(precios_list) == 1 else (tot_cost / cnt if cnt > 0 else 0.0)
        
        datosPlanesActivos.append({
            'Plan': p_name,
            'Cantidad': cnt,
            'Precio Unitario': precio_unitario_str,
            'Precio Referencia': round(precio_ref, 2),
            'Sumatoria Costo': round(tot_cost, 2),
            'Porcentaje Clientes': round((cnt / totalActivos * 100), 2) if totalActivos > 0 else 0.0,
            'Porcentaje Ingresos': round((tot_cost / ingreso_hoy * 100), 2) if ingreso_hoy > 0 else 0.0
        })

    datosPlanesActivos.sort(key=lambda x: x['Cantidad'], reverse=True)

    resumen_list = [
        {"Indicador": "Activos Totales", "Valor": totalActivos},
        {"Indicador": f"Suspendidos (desde {fechaCorte})", "Valor": totalSuspendidosFecha},
        {"Indicador": "Exonerados (Empleados)", "Valor": totalExoneradosEmp},
        {"Indicador": "Exonerados (Regulares)", "Valor": totalExoneradosReg}
    ]

    return {
        "totales": {
            "activos": totalActivos,
            "activos_corp": totalActivosCorp,
            "suspendidos": totalSuspendidosFecha,
            "suspendidos_corp": totalSuspendidosFechaCorp,
            "exonEmp": totalExoneradosEmp,
            "exonReg": totalExoneradosReg,
            "exonRegCorp": totalExoneradosRegCorp
        },
        "conciliacion_financiera_res": {
            "has_excel": True,
            "ingreso_ayer": ingreso_ayer,
            "cant_ayer": count_activos_ayer,
            "ingreso_hoy": ingreso_hoy,
            "cant_hoy": totalActivos,
            "emp_exo_qty": emp_exo_qty,
            "emp_exo_mnt": emp_exo_mnt,
            "res_exo_qty": res_exo_qty,
            "res_exo_mnt": res_exo_mnt,
            "upgrades_qty": upgrades_qty,
            "upgrades_mnt": upgrades_mnt,
            "cambios_3m_qty": cambios_3m_qty,
            "cambios_3m_mnt": cambios_3m_mnt,
            "reconex_qty": reconex_qty,
            "reconex_mnt": reconex_mnt,
            "reconex_exo_qty": reconex_exo_qty,
            "reconex_exo_mnt": reconex_exo_mnt,
            "inst_3m_qty": inst_3m_qty,
            "inst_3m_mnt": inst_3m_mnt,
            "inst_norm_qty": inst_norm_qty,
            "inst_norm_mnt": inst_norm_mnt,
            "downgrades_qty": downgrades_qty,
            "downgrades_mnt": downgrades_mnt,
            "susp_qty": susp_qty,
            "susp_mnt": susp_mnt,
            "cant_diferencia_neta": totalActivos - count_activos_ayer
        },
        "conciliacion_financiera_corp": {
            "has_excel": True,
            "ingreso_ayer": ingreso_ayer_corp,
            "cant_ayer": count_activos_ayer_corp,
            "ingreso_hoy": ingreso_hoy_corp,
            "cant_hoy": count_activos_hoy_corp,
            "emp_exo_qty": emp_exo_qty_corp,
            "emp_exo_mnt": emp_exo_mnt_corp,
            "res_exo_qty": res_exo_qty_corp,
            "res_exo_mnt": res_exo_mnt_corp,
            "upgrades_qty": upgrades_qty_corp,
            "upgrades_mnt": upgrades_mnt_corp,
            "cambios_3m_qty": cambios_3m_qty_corp,
            "cambios_3m_mnt": cambios_3m_mnt_corp,
            "reconex_qty": reconex_qty_corp,
            "reconex_mnt": reconex_mnt_corp,
            "reconex_exo_qty": reconex_exo_qty_corp,
            "reconex_exo_mnt": reconex_exo_mnt_corp,
            "inst_3m_qty": inst_3m_qty_corp,
            "inst_3m_mnt": inst_3m_mnt_corp,
            "inst_norm_qty": inst_norm_qty_corp,
            "inst_norm_mnt": inst_norm_mnt_corp,
            "downgrades_qty": downgrades_qty_corp,
            "downgrades_mnt": downgrades_mnt_corp,
            "susp_qty": susp_qty_corp,
            "susp_mnt": susp_mnt_corp,
            "cant_diferencia_neta": count_activos_hoy_corp - count_activos_ayer_corp
        },
        "conciliacion_detalle": datosConciliacionDetalle,
        "resumen": resumen_list,
        "planesActivos": datosPlanesActivos,
        "clientesActivos": datosClientesActivos,
        "instalaciones": datosInstalaciones,
        "instalacionesProceso": datosInstalacionesProceso,
        "cambiosPlan": datosCambiosPlan,
        "seguimiento": datosSeguimiento,
        "estatus": datosEstatus,
        "deudores": datosDeudores
    }

def build_plan_aggregates(users, is_corp=False, is_cons=False):
    total_activos = 0
    total_monto = 0.0
    datos_clientes_activos = []
    plan_aggregates = {}

    for item in users:
        status = str(item.get('service_status', '')).strip().upper()
        if status in ('ACTIVO', 'ACT.'):
            plan = str(item.get('plan', '')).strip() or 'Sin Plan'
            service_type = str(item.get('service_type', '')).strip().upper()
            
            if plan.upper() == 'TV' or service_type == 'IPTV':
                continue
                
            if is_corp:
                if service_type not in ['PYME', 'CORPORATIVO']:
                    continue
            elif not is_cons:
                # This is residential (not corp, not cons)
                if service_type in ['PYME', 'CORPORATIVO']:
                    continue
                    
            try:
                amount = float(item.get('amount') or 0.0)
            except:
                amount = 0.0
                
            try:
                balance = float(item.get('balance') or 0.0)
            except:
                balance = 0.0

            raw_inst = item.get('creation_date', '')
            fecha_inst = safe_date_str(raw_inst)
            if raw_inst and 'T' in str(raw_inst):
                try:
                    fecha_inst = datetime.strptime(str(raw_inst).split('T')[0], "%Y-%m-%d").strftime("%d/%m/%Y")
                except:
                    pass

            sid = str(item.get('id_servicio', '')).strip()
            cedula = f"{item.get('doc_type', '')}-{item.get('doc', '')}" if item.get('doc') else ""
            nombre = str(item.get('name', '')).strip()
            urbanismo = str(item.get('urban', '')).strip()
            telefono = str(item.get('phone', '')).strip()

            total_activos += 1
            total_monto += amount

            datos_clientes_activos.append({
                'ID Servicio': sid,
                'Cédula': cedula,
                'Nombres': nombre,
                'Plan': plan,
                'Tipo de servicio': service_type,
                'Costo del plan': amount,
                'Estado servicio': 'Act.',
                'Saldo Actual': balance,
                'Fecha de instalación': fecha_inst,
                'Teléfono 1': telefono,
                'Urbanismo': urbanismo
            })

            if plan not in plan_aggregates:
                plan_aggregates[plan] = {
                    'Plan': plan,
                    'Cantidad': 0,
                    'Sumatoria Costo': 0.0,
                    'Precios': set()
                }
            plan_aggregates[plan]['Cantidad'] += 1
            plan_aggregates[plan]['Sumatoria Costo'] += amount
            plan_aggregates[plan]['Precios'].add(amount)

    datos_planes_activos = []
    for p_name, p_data in plan_aggregates.items():
        cnt = p_data['Cantidad']
        tot_cost = p_data['Sumatoria Costo']
        precios_list = sorted(list(p_data['Precios']))
        precio_unitario_str = " / ".join([f"${p:g}" for p in precios_list]) if precios_list else "$0.00"
        precio_ref = precios_list[0] if len(precios_list) == 1 else (tot_cost / cnt if cnt > 0 else 0.0)

        datos_planes_activos.append({
            'Plan': p_name,
            'Cantidad': cnt,
            'Precio Unitario': precio_unitario_str,
            'Precio Referencia': round(precio_ref, 2),
            'Sumatoria Costo': round(tot_cost, 2),
            'Porcentaje Clientes': round((cnt / total_activos * 100), 2) if total_activos > 0 else 0.0,
            'Porcentaje Ingresos': round((tot_cost / total_monto * 100), 2) if total_monto > 0 else 0.0
        })

    datos_planes_activos.sort(key=lambda x: x['Cantidad'], reverse=True)
    datos_clientes_activos.sort(key=lambda x: x.get('Nombres', ''))

    plan_lider = datos_planes_activos[0]['Plan'] if datos_planes_activos else 'N/A'
    arpu = round(total_monto / total_activos, 2) if total_activos > 0 else 0.0

    return {
        "totales": {
            "total_clientes_activos": total_activos,
            "total_costo_facturacion": round(total_monto, 2),
            "total_planes": len(datos_planes_activos),
            "plan_lider": plan_lider,
            "arpu_promedio": arpu
        },
        "planes": datos_planes_activos,
        "clientes": datos_clientes_activos
    }

@app.get("/api/reportes/clientes_activos_por_plan")
def get_clientes_activos_por_plan(
    request: Request,
    db: Session = Depends(get_db),
    tipo: str = Query("todos"),
    force_api: bool = Query(False)
):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    path_gen = os.path.join(UPLOAD_DIR, "last_snapshot.json")
    path_corp = os.path.join(UPLOAD_DIR, "last_snapshot_corporativo.json")

    data_gen = None
    data_corp = None

    if force_api or not os.path.exists(path_gen) or not os.path.exists(path_corp):
        try:
            data_gen = fetch_powerlink_data(is_natural=None)
            with open(path_gen, "w", encoding="utf-8") as f:
                json.dump(data_gen, f)
        except Exception as e:
            if not os.path.exists(path_gen):
                raise HTTPException(status_code=500, detail=f"Error al consultar API General: {str(e)}")

        try:
            data_corp = fetch_powerlink_data(is_natural=False)
            with open(path_corp, "w", encoding="utf-8") as f:
                json.dump(data_corp, f)
        except Exception as e:
            if not os.path.exists(path_corp):
                raise HTTPException(status_code=500, detail=f"Error al consultar API Corporativo: {str(e)}")

    if data_gen is None and os.path.exists(path_gen):
        with open(path_gen, "r", encoding="utf-8") as f:
            data_gen = json.load(f)

    if data_corp is None and os.path.exists(path_corp):
        with open(path_corp, "r", encoding="utf-8") as f:
            data_corp = json.load(f)

    users_gen = (data_gen or {}).get("data", [])

    resumen_res = build_plan_aggregates(users_gen, is_corp=False, is_cons=False)
    resumen_corp = build_plan_aggregates(users_gen, is_corp=True, is_cons=False)
    resumen_cons = build_plan_aggregates(users_gen, is_corp=False, is_cons=True)

    fecha_snapshot = ""
    if os.path.exists(path_gen):
        mtime = os.path.getmtime(path_gen)
        fecha_snapshot = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %I:%M %p")

    return {
        "residencial": resumen_res,
        "corporativo": resumen_corp,
        "consolidado": resumen_cons,
        "fecha_snapshot": fecha_snapshot,
        # Compatibilidad directa
        "totales": resumen_cons["totales"],
        "planes": resumen_cons["planes"],
        "clientes": resumen_cons["clientes"]
    }

@app.get("/api/metricas/crecimiento")
def get_metricas_crecimiento(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")
        
    snapshot_path = os.path.join(UPLOAD_DIR, "last_snapshot.json")
    if not os.path.exists(snapshot_path):
        return {"activos_power": 0}
        
    try:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            data_old = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo snapshot: {str(e)}")
        
    list_old = data_old.get("data", [])
    activos_power = 0
    activos_iptv = 0
    
    sectores = set()
    for item in list_old:
        status = str(item.get('service_status', '')).strip().upper()
        plan = str(item.get('plan', '')).strip().upper()
        service_type = str(item.get('service_type', '')).strip().upper()
        sector = str(item.get('sector', '')).strip()
        
        if sector and sector.lower() not in ["none", "null"]:
            sectores.add(sector)
        
        if status == 'ACTIVO':
            if plan in ['IPTV', 'TV'] or service_type in ['IPTV', 'TV']:
                activos_iptv += 1
            else:
                activos_power += 1
            
    return {
        "activos_power": activos_power,
        "activos_iptv": activos_iptv,
        "zonas_habilitadas": len(sectores)
    }


@app.get("/api/intranet/calendar")
async def get_calendar_events(
    year: int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    # Fetch events
    events = db.query(models.CalendarEvent).filter(
        models.CalendarEvent.year == year,
        models.CalendarEvent.month == month
    ).all()
    
    # Fetch birthdays for this month
    employees = db.query(models.Employee).filter(models.Employee.birthday_date != None, models.Employee.birthday_date != "").all()
    birthdays = []
    seen_names = set()

    DEFAULT_LOGO = "https://ngfihmioixtfnrmlrlam.supabase.co/storage/v1/object/public/power/WhatsApp_Image_2026-03-20_at_3.44.14_PM-removebg-preview.png"
    users_all = db.query(models.User).all()
    user_avatar_map = {u.email: u.avatar_url for u in users_all if u.email and u.avatar_url and u.avatar_url != "/static/img/default-avatar.png" and u.avatar_url != DEFAULT_LOGO}
    user_name_avatar_map = {u.full_name.lower(): u.avatar_url for u in users_all if u.full_name and u.avatar_url and u.avatar_url != "/static/img/default-avatar.png" and u.avatar_url != DEFAULT_LOGO}

    for emp in employees:
        parsed = parse_birthday_day_month(emp.birthday_date)
        if parsed:
            b_day, b_month = parsed
            if b_month == month:
                emp_name = getattr(emp, 'full_name', None) or f"{emp.name} {emp.apellido or ''}".strip()
                seen_names.add(emp_name.lower())
                
                # Obtener foto real o logo por defecto
                photo = emp.photo_url
                if not photo or photo == "/static/img/default-avatar.png":
                    if emp.email and emp.email in user_avatar_map:
                        photo = user_avatar_map[emp.email]
                    elif emp_name.lower() in user_name_avatar_map:
                        photo = user_name_avatar_map[emp_name.lower()]
                
                if not photo or photo == "/static/img/default-avatar.png":
                    photo = DEFAULT_LOGO

                birthdays.append({
                    "day": b_day,
                    "name": emp_name,
                    "photo_url": photo,
                    "department": emp.department or "General"
                })

    # Also check users with birthday recorded
    users_with_bday = db.query(models.User).filter(models.User.birthday_date != None, models.User.birthday_date != "").all()
    for u in users_with_bday:
        u_name = (u.full_name or u.username).strip()
        if u_name.lower() not in seen_names:
            parsed = parse_birthday_day_month(u.birthday_date)
            if parsed:
                b_day, b_month = parsed
                if b_month == month:
                    seen_names.add(u_name.lower())
                    photo = u.avatar_url
                    if not photo or photo == "/static/img/default-avatar.png":
                        photo = DEFAULT_LOGO
                    birthdays.append({
                        "day": b_day,
                        "name": u_name,
                        "photo_url": photo,
                        "department": u.department or "General"
                    })
            
    # Structure data by day
    days_data = {}
    
    for ev in events:
        if ev.day not in days_data:
            days_data[ev.day] = {"events": [], "birthdays": []}
        days_data[ev.day]["events"].append({
            "id": ev.id,
            "title": ev.title,
            "description": ev.description
        })
        
    for b in birthdays:
        if b["day"] not in days_data:
            days_data[b["day"]] = {"events": [], "birthdays": []}
        days_data[b["day"]]["birthdays"].append(b)
        
    return days_data



@app.post("/api/rrhh/calendar_events")
async def add_calendar_event(
    title: str = Form(...),
    description: str = Form(None),
    date: str = Form(...), # format YYYY-MM-DD
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    try:
        dt = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido")
        
    ev = models.CalendarEvent(
        title=title,
        description=description,
        day=dt.day,
        month=dt.month,
        year=dt.year
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return {"message": "Evento agregado", "event": ev}

@app.delete("/api/rrhh/calendar_events/{event_id}")
async def delete_calendar_event(
    event_id: int,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    ev = db.query(models.CalendarEvent).filter(models.CalendarEvent.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    db.delete(ev)
    db.commit()
    return {"message": "Evento eliminado"}

@app.get("/api/rrhh/calendar_events")
async def get_calendar_events_admin(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    # Get future events or all events
    today = datetime.now()
    events = db.query(models.CalendarEvent).order_by(
        models.CalendarEvent.year.desc(),
        models.CalendarEvent.month.desc(),
        models.CalendarEvent.day.desc()
    ).limit(50).all()
    return events


# ==========================================
# DIRECTORIO TELEFONICO
# ==========================================
@app.get("/directorio", response_class=HTMLResponse)
async def view_directorio(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        employees = db.query(models.Employee).all()
        return templates.TemplateResponse(request, "directorio.html", {"request": request, "user": user, "employees": employees})
    except (HTTPException, Exception):
        return RedirectResponse(url="/login")

@app.get("/api/directorio/extensions")
async def get_extensions(db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_user)):
    extensions = db.query(models.PhoneExtension).all()
    # Group by department
    data = {}
    for ext in extensions:
        if ext.department not in data:
            data[ext.department] = []
        data[ext.department].append({
            "id": ext.id,
            "name": ext.name,
            "extension": ext.extension,
            "is_group": ext.is_group
        })
    return data

@app.post("/api/directorio/extensions")
async def create_extension(ext: ExtensionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_user)):
    if current_user.role != "admin" and "editar_directorio" not in (current_user.permissions or ""):
        raise HTTPException(status_code=403, detail="No autorizado")
    new_ext = models.PhoneExtension(**ext.model_dump())
    db.add(new_ext)
    db.commit()
    db.refresh(new_ext)
    return {"message": "Extensión creada", "id": new_ext.id}

@app.put("/api/directorio/extensions/{ext_id}")
async def update_extension(ext_id: int, ext_update: ExtensionUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_user)):
    if current_user.role != "admin" and "editar_directorio" not in (current_user.permissions or ""):
        raise HTTPException(status_code=403, detail="No autorizado")
    ext = db.query(models.PhoneExtension).filter(models.PhoneExtension.id == ext_id).first()
    if not ext:
        raise HTTPException(status_code=404, detail="Extensión no encontrada")
    ext.name = ext_update.name
    db.commit()
    return {"message": "Extensión actualizada"}

@app.put("/api/users/{user_id}/edit")
async def edit_user(user_id: int, user_data: UserUpdateWithSMTP, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_user)):
    if current_user.role != "admin" and "editar_usuarios" not in (current_user.permissions or ""):
        raise HTTPException(status_code=403, detail="No autorizado")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    user.email = user_data.email
    if user_data.password:
        user.hashed_password = security.get_password_hash(user_data.password)
    db.commit()
    
    if user.email:
        email_sent = email_util.send_credentials_update_email(user.email, user.full_name or user.username, user.email, user_data.password)
        if not email_sent:
            return {"message": "Usuario actualizado, pero falló el envío del correo de notificación."}

    return {"message": "Usuario actualizado y notificación procesada correctamente."}

@app.get("/historico", response_class=HTMLResponse)
async def view_historico(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if not permissions_manager.user_has_any_perm(user, ["sub_admin_historico", "ver_historico"]):
            return RedirectResponse(url="/")
        embed = request.query_params.get("embed") == "1"
        
        # Obtener los 50 últimos cambios históricos
        recent_history_query = db.query(models.ClientHistory, models.Client).join(
            models.Client, models.ClientHistory.client_id == models.Client.id
        ).order_by(models.ClientHistory.record_date.desc()).limit(50).all()
        
        recent_events = []
        for h, c in recent_history_query:
            recent_events.append({
                "service_id": c.service_id,
                "cedula": c.cedula,
                "client_name": c.name,
                "plan": c.current_plan,
                "event_type": h.event_type,
                "old_value": h.old_value,
                "new_value": h.new_value,
                "date": h.record_date.strftime("%d/%m/%Y %H:%M") if h.record_date else "-"
            })

        return templates.TemplateResponse(request, "historico.html", {"user": user, "embed": embed, "recent_events": recent_events})
    except (HTTPException, Exception):
        return RedirectResponse(url="/login")

@app.get("/api/historico/{cedula}")
async def api_get_historico(cedula: str, db: Session = Depends(get_db)):
    cedula_clean = cedula.strip().lower()
    
    # Búsqueda flexible por cédula (ej. "12345678" coincide con "V-12345678")
    client = db.query(models.Client).filter(models.Client.cedula.ilike(f"%{cedula_clean}%")).first()
    
    if not client:
        # Intento de buscar por ID de servicio si la cédula no dio resultado
        client = db.query(models.Client).filter(models.Client.service_id.ilike(f"%{cedula_clean}%")).first()
        if not client:
            raise HTTPException(status_code=404, detail=f"No se encontró cliente con la búsqueda: {cedula}")

    history = db.query(models.ClientHistory).filter(
        models.ClientHistory.client_id == client.id
    ).order_by(models.ClientHistory.record_date.desc()).all()
    
    return {
        "client": {
            "name": client.name,
            "cedula": client.cedula,
            "service_id": client.service_id,
            "current_plan": client.current_plan,
            "status": client.status,
            "client_type": client.client_type,
            "installation_date": client.installation_date,
        },
        "history": [
            {
                "record_date": h.record_date,
                "event_type": h.event_type,
                "old_value": h.old_value,
                "new_value": h.new_value
            } for h in history
        ]
    }

_clients_index = {}
_clients_mtimes = (0, 0)

def _get_clients_index():
    global _clients_index, _clients_mtimes
    path_res = os.path.join(UPLOAD_DIR, "last_snapshot.json")
    path_corp = os.path.join(UPLOAD_DIR, "last_snapshot_corporativo.json")
    
    mtime_res = os.path.getmtime(path_res) if os.path.exists(path_res) else 0
    mtime_corp = os.path.getmtime(path_corp) if os.path.exists(path_corp) else 0
    current_mtimes = (mtime_res, mtime_corp)
    
    if _clients_index and _clients_mtimes == current_mtimes:
        return _clients_index
        
    new_index = {}
    import re
    from collections import defaultdict
    
    def _format_phone(p):
        p = str(p or '').strip()
        if not p: return ''
        digits = re.sub(r'[^0-9]', '', p)
        if digits.startswith('58') and len(digits) == 12:
            return '0' + digits[2:5] + '-' + digits[5:]
        if digits.startswith('0') and len(digits) == 11:
            return digits[:4] + '-' + digits[4:]
        return p

    contracts_by_doc = defaultdict(list)
    client_meta_by_doc = {}

    def _process_item(u, tipo_cliente):
        doc = str(u.get('doc', '')).strip()
        if not doc:
            return
        dt = str(u.get('doc_type', '')).strip().upper()
        onu = u.get('onu_sn') or u.get('onu') or u.get('onu_mac') or ''
        if ' / ' in onu:
            onu = onu.split(' / ')[0].strip()
        
        sid = u.get('id_servicio')
        plan = (u.get('plan') or '').strip()
        status = (u.get('service_status') or 'ACTIVO').strip().upper()
        addr = (u.get('address') or '').strip()
        urban = (u.get('urban') or '').strip()
        sector = (u.get('sector') or '').strip()
        tel1 = _format_phone(u.get('phone'))
        tel2 = _format_phone(u.get('phone_2'))

        contract = {
            'id_servicio': sid,
            'contrato': f"Contrato #{sid}" if sid else "Contrato Principal",
            'plan': plan,
            'estado_servicio': status,
            'tipo_cliente': tipo_cliente,
            'onu': onu,
            'onu_sn': u.get('onu_sn') or '',
            'onu_mac': u.get('onu_mac') or '',
            'ubicacion': addr,
            'urban': urban,
            'sector': sector,
            'city': (u.get('city') or '').strip(),
            'state': (u.get('state') or '').strip(),
            'telefono1': tel1,
            'telefono_raw': u.get('phone') or '',
            'telefono2': tel2,
            'email': (u.get('email') or '').strip(),
            'ip_address': (u.get('ip_address') or '').strip()
        }

        if doc not in client_meta_by_doc:
            client_meta_by_doc[doc] = {
                'doc': doc,
                'doc_type': dt,
                'nombre': (u.get('name') or '').strip()
            }
        elif not client_meta_by_doc[doc]['nombre'] and u.get('name'):
            client_meta_by_doc[doc]['nombre'] = (u.get('name') or '').strip()

        # Evitar duplicar el mismo contrato por id_servicio
        existing_sids = {c['id_servicio'] for c in contracts_by_doc[doc] if c.get('id_servicio')}
        if not sid or sid not in existing_sids:
            contracts_by_doc[doc].append(contract)

    # Cargar residencial
    if os.path.exists(path_res):
        try:
            with open(path_res, "r", encoding="utf-8") as f:
                res_data = json.load(f).get("data", [])
                for u in res_data:
                    _process_item(u, 'Residencial')
        except Exception as e:
            print(f"Error indexando last_snapshot.json: {e}")

    # Cargar corporativo
    if os.path.exists(path_corp):
        try:
            with open(path_corp, "r", encoding="utf-8") as f:
                corp_data = json.load(f).get("data", [])
                for u in corp_data:
                    _process_item(u, 'Corporativo')
        except Exception as e:
            print(f"Error indexando last_snapshot_corporativo.json: {e}")

    # Construir índice unificado con lista de contratos por cliente
    for doc, clist in contracts_by_doc.items():
        meta = client_meta_by_doc.get(doc, {'doc': doc, 'doc_type': '', 'nombre': ''})
        dt = meta['doc_type']
        
        # Priorizar contratos ACTIVOS primero, luego orden por ID
        clist.sort(key=lambda x: (0 if x.get('estado_servicio') == 'ACTIVO' else 1, x.get('id_servicio') or 0))
        primary = clist[0]

        client_data = {
            'encontrado': True,
            'cedula': f"{dt}-{doc}" if dt else doc,
            'doc': doc,
            'doc_type': dt,
            'nombre': meta['nombre'],
            'tipo_cliente': primary.get('tipo_cliente', 'Residencial'),
            'total_contratos': len(clist),
            'contratos': clist,
            # Campos directos de compatibilidad con código existente
            'id_servicio': primary.get('id_servicio'),
            'plan': primary.get('plan', ''),
            'estado_servicio': primary.get('estado_servicio', ''),
            'onu': primary.get('onu', ''),
            'telefono1': primary.get('telefono1', ''),
            'telefono_raw': primary.get('telefono_raw', ''),
            'telefono2': primary.get('telefono2', ''),
            'ubicacion': primary.get('ubicacion', ''),
            'urban': primary.get('urban', '')
        }

        new_index[doc] = client_data
        if dt:
            new_index[f"{dt}-{doc}"] = client_data
            new_index[f"{dt}{doc}"] = client_data
        
        # Indexar también por id_servicio para búsquedas directas por número de servicio/contrato
        for c in clist:
            if c.get('id_servicio'):
                sid_str = str(c['id_servicio']).strip()
                if sid_str and sid_str not in new_index:
                    new_index[sid_str] = client_data

    _clients_index = new_index
    _clients_mtimes = current_mtimes
    return _clients_index

@app.get("/api/clientes/consulta")
def api_consultar_cliente(q: str = Query(...), db: Session = Depends(get_db)):
    import re
    query_str = q.strip().upper()
    if not query_str:
        return {"encontrado": False, "mensaje": "Parámetro de búsqueda vacío"}
        
    index = _get_clients_index()
    
    # 1. Búsqueda directa por la cadena ingresada
    if query_str in index:
        return index[query_str]
        
    # 2. Búsqueda por dígitos limpios
    digits = re.sub(r'[^0-9]', '', query_str)
    if digits and digits in index:
        return index[digits]
        
    # 3. Intentos con prefijos comunes (V, J, E, G)
    for prefix in ['V-', 'J-', 'E-', 'G-']:
        test_key = f"{prefix}{digits}"
        if test_key in index:
            return index[test_key]
            
    # 4. Fallback a la base de datos SQL
    if digits and hasattr(db, 'query'):
        try:
            clients_sql = db.query(models.Client).filter(
                (models.Client.cedula.ilike(f"%{digits}%")) | (models.Client.service_id == digits)
            ).all()
            
            if clients_sql:
                first_client = clients_sql[0]
                sql_contracts = []
                for cs in clients_sql:
                    sql_contracts.append({
                        "id_servicio": cs.service_id,
                        "contrato": f"Contrato #{cs.service_id}" if cs.service_id else "Contrato Principal",
                        "plan": cs.current_plan or "",
                        "estado_servicio": (cs.status or "ACTIVO").upper(),
                        "tipo_cliente": cs.client_type or "Residencial",
                        "onu": "",
                        "onu_sn": "",
                        "onu_mac": "",
                        "ubicacion": "",
                        "urban": "",
                        "sector": "",
                        "city": "",
                        "state": "",
                        "telefono1": "",
                        "telefono_raw": "",
                        "telefono2": "",
                        "email": "",
                        "ip_address": ""
                    })
                return {
                    "encontrado": True,
                    "cedula": first_client.cedula or digits,
                    "doc": digits,
                    "doc_type": "",
                    "nombre": first_client.name,
                    "tipo_cliente": first_client.client_type or "Residencial",
                    "total_contratos": len(sql_contracts),
                    "contratos": sql_contracts,
                    "id_servicio": first_client.service_id,
                    "plan": first_client.current_plan or "",
                    "estado_servicio": first_client.status or "",
                    "onu": "",
                    "telefono1": "",
                    "telefono_raw": "",
                    "telefono2": "",
                    "ubicacion": "",
                    "urban": ""
                }
        except Exception as e:
            print(f"Error consultando SQL client fallback: {e}")
        
    return {"encontrado": False, "mensaje": f"No se encontró cliente con documento: {q}"}

def scheduled_snapshot_job():
    try:
        data = fetch_powerlink_data(is_natural=None)
        snapshot_path = os.path.join(UPLOAD_DIR, "last_snapshot.json")
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        print(f"[{datetime.now()}] Snapshot diario general guardado exitosamente.")
    except Exception as e:
        print(f"[{datetime.now()}] Error guardando snapshot diario general: {str(e)}")

    try:
        data_corp = fetch_powerlink_data(is_natural=False)
        snapshot_path_corp = os.path.join(UPLOAD_DIR, "last_snapshot_corporativo.json")
        with open(snapshot_path_corp, "w", encoding="utf-8") as f:
            json.dump(data_corp, f)
        print(f"[{datetime.now()}] Snapshot diario corporativo guardado exitosamente.")
    except Exception as e:
        print(f"[{datetime.now()}] Error guardando snapshot diario corporativo: {str(e)}")

scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_snapshot_job, 'cron', hour=16, minute=0)

@app.on_event("startup")
def startup_event():
    scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


@app.get("/api/users/chat_directory")
async def api_get_chat_directory(only_online: bool = True, db: Session = Depends(get_db)):
    all_users = db.query(models.User).filter(models.User.is_active == True).all()
    employees = db.query(models.Employee).all()
    emp_map = {emp.name: emp.department for emp in employees}
    
    online_emails = manager.get_online_emails()
    
    departments = {}
    for u in all_users:
        is_online = u.email in online_emails
        if only_online and not is_online:
            continue
        dept = emp_map.get(u.full_name, "General")
        if dept not in departments:
            departments[dept] = []
        departments[dept].append({
            "email": u.email,
            "full_name": u.full_name,
            "avatar_url": u.avatar_url,
            "is_online": is_online
        })
    return departments



# ==========================================
# ENDPOINTS REPORTES
# ==========================================

reporte_clients = []

async def notify_reporte_clients():
    for queue in reporte_clients:
        await queue.put("update")

@app.get("/reporte", response_class=HTMLResponse)
async def view_reporte(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if not permissions_manager.user_has_any_perm(user, ['sub_soporte_reporte', 'ver_reportes', 'perm_reporte']):
            return RedirectResponse(url="/")
        embed = request.query_params.get("embed") == "1"
        return templates.TemplateResponse(request, "reporte.html", {"request": request, "user": user, "embed": embed})
    except (HTTPException, Exception):
        return RedirectResponse(url="/login")

@app.get("/api/db")
async def api_get_db():
    try:
        data = {}
        if os.path.exists("db.json"):
            with open("db.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        
        # Asegurar listas por defecto
        for key in ['reports', 'afectaciones', 'techs', 'assignments', 'motivos', 'zonas', 'users', 'logs']:
            if key not in data or not isinstance(data[key], list):
                data[key] = []

        # Auto-cargar colecciones VGT si no existen en db.json
        vgt_defaults = {
            'vgt_routes': 'static/vgt/routes_db.json',
            'vgt_technicians': 'static/vgt/technicians_db.json',
            'vgt_drivers': 'static/vgt/drivers_db.json',
            'vgt_vehicles': 'static/vgt/vehicles_db.json'
        }
        for vkey, vpath in vgt_defaults.items():
            if vkey not in data or not isinstance(data[vkey], list) or len(data[vkey]) == 0:
                if os.path.exists(vpath):
                    try:
                        with open(vpath, "r", encoding="utf-8") as vf:
                            data[vkey] = json.load(vf)
                    except Exception:
                        data[vkey] = []
                else:
                    data[vkey] = []

        if 'vgt_teams' not in data or not isinstance(data['vgt_teams'], list):
            data['vgt_teams'] = []
                
        # Aliases para máxima compatibilidad
        data['reportes'] = data.get('reports', [])
        data['cuadrillas'] = data.get('techs', [])
        data['coordinacion'] = data.get('assignments', [])
        data['operadores'] = data.get('users', [])
        data['bitacora'] = data.get('logs', [])
        
        return data
    except Exception as e:
        return {
            "reports": [], "reportes": [],
            "afectaciones": [],
            "techs": [], "cuadrillas": [],
            "assignments": [], "coordinacion": [],
            "motivos": [],
            "zonas": [],
            "users": [], "operadores": [],
            "logs": [], "bitacora": [],
            "vgt_routes": [],
            "vgt_technicians": [],
            "vgt_drivers": [],
            "vgt_vehicles": [],
            "vgt_teams": []
        }

@app.post("/api/db")
async def api_post_db(request: Request):
    try:
        payload = await request.json()
        
        data = {}
        if os.path.exists("db.json"):
            try:
                with open("db.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
                
        # Mapeo de campos compatibles tanto en inglés como en español
        mappings = [
            (['reports', 'reportes'], 'reports'),
            (['techs', 'cuadrillas'], 'techs'),
            (['assignments', 'coordinacion'], 'assignments'),
            (['afectaciones'], 'afectaciones'),
            (['motivos'], 'motivos'),
            (['zonas'], 'zonas'),
            (['users', 'operadores'], 'users'),
            (['logs', 'bitacora'], 'logs'),
            (['vgt_routes'], 'vgt_routes'),
            (['vgt_technicians'], 'vgt_technicians'),
            (['vgt_drivers'], 'vgt_drivers'),
            (['vgt_vehicles'], 'vgt_vehicles'),
            (['vgt_teams'], 'vgt_teams'),
        ]
        
        for keys, canonical_key in mappings:
            for k in keys:
                if k in payload and isinstance(payload[k], list):
                    # Si el payload viene con lista vacía pero db.json ya tiene datos de motivos/zonas/vgt, no sobreescribir con vacío
                    if len(payload[k]) == 0 and len(data.get(canonical_key, [])) > 0 and canonical_key in ['motivos', 'zonas', 'vgt_routes', 'vgt_technicians', 'vgt_drivers', 'vgt_vehicles']:
                        continue
                    data[canonical_key] = payload[k]
                    break
                
        with open("db.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        await notify_reporte_clients()
        return {"status": "ok", "message": "Database saved and clients notified"}
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

@app.post("/api/login")
async def api_reporte_login(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
        raw_username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "")).strip()

        if not raw_username or not password:
            return JSONResponse(status_code=400, content={"status": "error", "success": False, "message": "Debes ingresar usuario y contraseña"})

        # Buscar en la tabla principal de Trabajadores (models.User) por username o email
        user = db.query(models.User).filter(
            (models.User.username.ilike(raw_username)) |
            (models.User.email.ilike(raw_username))
        ).first()

        if not user:
            return JSONResponse(status_code=401, content={"status": "error", "success": False, "message": "Usuario o correo no registrado en el sistema de trabajadores"})

        # Validar si el trabajador se encuentra activo o suspendido
        if not user.is_active:
            reason = f": {user.suspension_reason}" if user.suspension_reason else ""
            return JSONResponse(status_code=403, content={"status": "error", "success": False, "message": f"Usuario inactivo o suspendido{reason}. Contacta a Administración / RRHH."})

        # Validar contraseña con el hash de seguridad
        password_ok = False
        if user.hashed_password:
            try:
                password_ok = security.verify_password(password, user.hashed_password)
            except Exception:
                password_ok = False
            # Fallback en caso de contraseñas migradas en texto plano
            if not password_ok and user.hashed_password == password:
                password_ok = True

        if not password_ok:
            return JSONResponse(status_code=401, content={"status": "error", "success": False, "message": "Contraseña incorrecta"})

        # Generar token de acceso
        access_token = security.create_access_token(data={"sub": user.username, "role": user.role})

        return {
            "status": "ok",
            "success": True,
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "name": user.full_name or user.username,
                "full_name": user.full_name or user.username,
                "role": user.role or "user",
                "cargo": user.cargo or "",
                "department": user.department or "",
                "permissions": user.permissions or "",
                "avatar_url": user.avatar_url or ""
            }
        }
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

@app.get("/api/stream")
async def api_reporte_stream(request: Request):
    queue = asyncio.Queue()
    reporte_clients.append(queue)
    async def event_generator():
        yield "data: connected\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=2.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    pass
        finally:
            if queue in reporte_clients:
                reporte_clients.remove(queue)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
