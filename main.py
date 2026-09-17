import os
import shutil
import io
import pandas as pd
from typing import List, Optional
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, Depends, HTTPException, status, Request, Form, File, UploadFile, Response, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
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
    return response

# Mount Static Files and Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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

class UserUpdateWithSMTP(BaseModel):
    email: str
    password: str
    smtp_user: str
    smtp_pass: str

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, email: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[email] = websocket

    def disconnect(self, email: str):
        if email in self.active_connections:
            del self.active_connections[email]

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            try:
                await connection.send_json(message)
            except:
                pass
                
    async def send_personal_message(self, message: dict, email: str):
        if email in self.active_connections:
            try:
                await self.active_connections[email].send_json(message)
            except:
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

    user = db.query(models.User).filter(models.User.username == form_data.username.strip()).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        security.record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
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
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Sesión cerrada correctamente."}

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
        username = security._decode_token(token)
        current_user = db.query(models.User).filter(models.User.username == username).first()
        if not current_user:
            return RedirectResponse(url="/login")
    except:
        return RedirectResponse(url="/login")

    all_users = db.query(models.User).filter(models.User.is_active == True).all()
    employees = db.query(models.Employee).all()
    emp_map = {emp.name: emp.department for emp in employees}
    
    departments = {}
    for u in all_users:
        dept = emp_map.get(u.full_name, "General")
        if dept not in departments:
            departments[dept] = []
        departments[dept].append(u)

    return templates.TemplateResponse(request, "chat.html", {
        "request": request,
        "user": current_user,
        "departments": departments
    })

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
        
        def get_next_bday(emp):
            try:
                # El HTML envia YYYY-MM-DD
                bday = datetime.strptime(emp.birthday_date, '%Y-%m-%d').date()
                this_year_bday = bday.replace(year=today.year)
                if this_year_bday < today:
                    this_year_bday = this_year_bday.replace(year=today.year + 1)
                return this_year_bday
            except:
                return datetime(9999, 12, 31).date()

        sorted_emps = sorted(all_emps_with_bday, key=get_next_bday)
        closest_emp = sorted_emps[0]
        
        # Formatear la fecha para que se vea bonita (ej. 15 de Octubre)
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        try:
            bday_dt = datetime.strptime(closest_emp.birthday_date, '%Y-%m-%d').date()
            closest_emp.birthday_date = f"{bday_dt.day} de {meses[bday_dt.month - 1]}"
        except:
            pass
            
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
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        token = token[len("Bearer "):]
    if not token:
        return RedirectResponse(url="/login")
    try:
        username = security._decode_token(token)
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            return RedirectResponse(url="/login")
        if user.role != 'admin' and 'ver_reportes' not in (user.permissions or ''):
            return RedirectResponse(url="/")
        return templates.TemplateResponse(request, "reportes.html", {"request": request, "user": user})
    except:
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
        manager.disconnect(user.email)

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
        avatar_url=photo_url
    )
    db.add(new_user)
        
    db.commit()
    db.refresh(emp)
    
    # Send email
    if email and smtp_user and smtp_pass:
        email_util.send_welcome_email(email, name, usuario, password, smtp_user, smtp_pass, is_update=False)
        
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
    
    if email and smtp_user and smtp_pass:
        email_util.send_welcome_email(email, name, "", "", smtp_user, smtp_pass, is_update=True)

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
    return [{"id": u.id, "full_name": u.full_name, "email": u.email, "role": u.role, "permissions": u.permissions or ""} for u in users]

@app.post("/api/rrhh/users/{user_id}/permissions")
async def update_user_permissions(
    user_id: int,
    permissions: str = Form(""),
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(security.require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.permissions = permissions
    db.commit()
    return {"message": "Permisos actualizados correctamente"}

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
async def login_page(request: Request):
    embed = request.query_params.get("embed") == "1"
    return templates.TemplateResponse(request, "login.html", {"embed": embed})

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        embed = request.query_params.get("embed") == "1"
        return templates.TemplateResponse(request, "intranet.html", {"user": user, "embed": embed})
    except HTTPException:
        return RedirectResponse(url="/login")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if user.role not in ["admin", "rrhh"] and "cargar_datos_usuarios" not in (user.permissions or ""):
            return RedirectResponse(url="/")
        
        employees = db.query(models.Employee).all()
        departments = db.query(models.Department).all()
        
        return templates.TemplateResponse(request, "rrhh.html", {
            "user": user,
            "employees": employees,
            "departments": departments
        })
    except HTTPException:
        return RedirectResponse(url="/login")

@app.get("/integracion", response_class=HTMLResponse)
async def integracion_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if user.role not in ["admin", "integracion", "rrhh"] and "ver_integracion" not in (user.permissions or ""):
            return RedirectResponse(url="/")
        embed = request.query_params.get("embed") == "1"
        return templates.TemplateResponse(request, "integracion.html", {"user": user, "embed": embed})
    except HTTPException:
        return RedirectResponse(url="/login")

@app.get("/helpdesk", response_class=HTMLResponse)
async def helpdesk_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
        if user.role not in ["admin"] and "ver_helpdesk" not in (user.permissions or ""):
            return RedirectResponse(url="/")
        return templates.TemplateResponse(request, "helpdesk.html", {"user": user})
    except HTTPException:
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
        data_res = _do_fetch(api_token, True)
        data_corp = _do_fetch(api_token, False)
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
    impacto_instalaciones = 0.0
    impacto_reconexiones = 0.0
    impacto_upgrades = 0.0
    impacto_upgrades_beneficio = 0.0
    impacto_downgrades = 0.0
    impacto_retiros_post_corte = 0.0
    impacto_retiros_pre_corte = 0.0
    impacto_otros = 0.0

    count_activos_ayer = 0
    count_instalaciones = 0
    count_reconexiones = 0
    count_upgrades = 0
    count_upgrades_beneficio = 0
    count_downgrades = 0
    count_retiros_post_corte = 0
    count_retiros_pre_corte = 0
    count_otros = 0
    
    # Variables Conciliación Corporativa
    ingreso_ayer_corp = 0.0
    ingreso_hoy_corp = 0.0
    count_activos_ayer_corp = 0
    count_activos_hoy_corp = 0
    
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
    
    for item in list_new:
        row = map_to_excel_format(item)
        sid = str(row['ID Servicio']).strip()
        if not sid:
            continue
            
        processed_sids.add(sid)
            
        planNew = str(row['Plan']).strip()
        tipoServicioNew = str(row['Tipo de servicio']).strip().upper()
        
        try:
            costoDelPlanNew = float(row['Costo del plan'])
        except:
            costoDelPlanNew = 0.0
            
        if planNew.upper() in ['IPTV', 'TV'] or tipoServicioNew in ['IPTV', 'TV']:
            continue
            
        estadoServicioNew = str(row['Estado servicio']).strip().upper()
        
        try:
            saldoActual = float(row['Saldo actual'])
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
            elif tipoServicioNew == 'RESIDENCIAL':
                if 'tv' not in planNew.lower() and 'iptv' not in planNew.lower():
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
            elif tipoServicioNew == 'RESIDENCIAL':
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
                    elif tipoServicioNew == 'RESIDENCIAL':
                        totalExoneradosReg += 1
                        
        if tipoServicioNew in ['PYME', 'CORPORATIVO']:
            row_old_corp = old_dict.get(sid)
            if row_old_corp is not None:
                estatusOldCorp = str(row_old_corp['Estado servicio']).strip().upper()
                if estatusOldCorp == 'ACT.':
                    try:
                        costoOldCorp = float(row_old_corp['Costo del plan'])
                    except:
                        costoOldCorp = 0.0
                    ingreso_ayer_corp += costoOldCorp
                    count_activos_ayer_corp += 1
            continue
                
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
                costoOld = float(row_old['Costo del plan'])
            except:
                costoOld = 0.0
                
            billingAyer = costoOld if estatusOld == 'ACT.' else 0.0
            billingHoy = costoDelPlanNew if estatusNew == 'ACT.' else 0.0
            variacionNeta = billingHoy - billingAyer
            
            if estatusOld == 'ACT.':
                ingreso_ayer += costoOld
                count_activos_ayer += 1
                
            # Finanzas - Bridge
            if estatusOld != 'ACT.' and estatusNew == 'ACT.' and is_estado_in_range:
                if is_instalacion_in_range and '3 MESES' in planNew.upper():
                    impacto_instalaciones += costoDelPlanNew
                    count_instalaciones += 1
                    datosConciliacionDetalle.append({
                        'ID Servicio': sid,
                        'Cédula': row['Cédula'],
                        'Nombres': row['Nombres'],
                        'Concepto': 'Nuevas Instalaciones (3 Meses Beneficio)',
                        'Plan Anterior': planOld,
                        'Plan Actual': planNew,
                        'Estado Anterior': estatusOld,
                        'Estado Actual': estatusNew,
                        'Costo Anterior': costoOld,
                        'Costo Actual': costoDelPlanNew,
                        'Variación': costoDelPlanNew,
                        'Fecha': fechaInstalacionFormat
                    })
                else:
                    impacto_reconexiones += costoDelPlanNew
                    count_reconexiones += 1
                    datosConciliacionDetalle.append({
                        'ID Servicio': sid,
                        'Cédula': row['Cédula'],
                        'Nombres': row['Nombres'],
                        'Concepto': 'Reconexiones',
                        'Plan Anterior': planOld,
                        'Plan Actual': planNew,
                        'Estado Anterior': estatusOld,
                        'Estado Actual': estatusNew,
                        'Costo Anterior': costoOld,
                        'Costo Actual': costoDelPlanNew,
                        'Variación': costoDelPlanNew,
                        'Fecha': fechaEstadoFormat
                    })
            elif estatusOld == 'ACT.' and estatusNew != 'ACT.' and is_estado_in_range:
                if estado_dt >= corte_dt:
                    impacto_retiros_post_corte += costoOld
                    count_retiros_post_corte += 1
                else:
                    impacto_retiros_pre_corte += costoOld
                    count_retiros_pre_corte += 1
                datosConciliacionDetalle.append({
                    'ID Servicio': sid,
                    'Cédula': row['Cédula'],
                    'Nombres': row['Nombres'],
                    'Concepto': 'Retiros',
                    'Plan Anterior': planOld,
                    'Plan Actual': planNew,
                    'Estado Anterior': estatusOld,
                    'Estado Actual': estatusNew,
                    'Costo Anterior': costoOld,
                    'Costo Actual': 0.0,
                    'Variación': -costoOld,
                    'Fecha': fechaEstadoFormat
                })
            elif estatusOld == 'ACT.' and estatusNew == 'ACT.' and is_plan_in_range:
                if costoDelPlanNew > costoOld:
                    if '3 MESES BENEFICIO' in planOld.upper() or '3 MESES BENEFICIO' in planNew.upper():
                        impacto_upgrades_beneficio += (costoDelPlanNew - costoOld)
                        count_upgrades_beneficio += 1
                        concepto_upg = 'Cambios 3 Meses Beneficio a otro Plan'
                    else:
                        impacto_upgrades += (costoDelPlanNew - costoOld)
                        count_upgrades += 1
                        concepto_upg = 'Upgrades de Plan'
                    datosConciliacionDetalle.append({
                        'ID Servicio': sid,
                        'Cédula': row['Cédula'],
                        'Nombres': row['Nombres'],
                        'Concepto': concepto_upg,
                        'Plan Anterior': planOld,
                        'Plan Actual': planNew,
                        'Estado Anterior': estatusOld,
                        'Estado Actual': estatusNew,
                        'Costo Anterior': costoOld,
                        'Costo Actual': costoDelPlanNew,
                        'Variación': costoDelPlanNew - costoOld,
                        'Fecha': fechaPlanDesdeFormat
                    })
                elif costoDelPlanNew < costoOld:
                    impacto_downgrades += (costoOld - costoDelPlanNew)
                    count_downgrades += 1
                    datosConciliacionDetalle.append({
                        'ID Servicio': sid,
                        'Cédula': row['Cédula'],
                        'Nombres': row['Nombres'],
                        'Concepto': 'Downgrades de Plan',
                        'Plan Anterior': planOld,
                        'Plan Actual': planNew,
                        'Estado Anterior': estatusOld,
                        'Estado Actual': estatusNew,
                        'Costo Anterior': costoOld,
                        'Costo Actual': costoDelPlanNew,
                        'Variación': -(costoOld - costoDelPlanNew),
                        'Fecha': fechaPlanDesdeFormat
                    })
            else:
                if estatusOld == 'ACT.' and estatusNew == 'ACT.' and costoOld != costoDelPlanNew:
                    # Ajuste manual de precio (mismo plan o fuera de rango)
                    impacto_otros += (costoDelPlanNew - costoOld)
                    count_otros += 1
                    datosConciliacionDetalle.append({
                        'ID Servicio': sid,
                        'Cédula': row['Cédula'],
                        'Nombres': row['Nombres'],
                        'Concepto': 'Ajuste Manual / Cambio Fuera de Rango',
                        'Plan Anterior': planOld,
                        'Plan Actual': planNew,
                        'Estado Anterior': estatusOld,
                        'Estado Actual': estatusNew,
                        'Costo Anterior': costoOld,
                        'Costo Actual': costoDelPlanNew,
                        'Variación': costoDelPlanNew - costoOld,
                        'Fecha': fechaPlanDesdeFormat if planOld != planNew else 'N/A'
                    })
                elif estatusOld != 'ACT.' and estatusNew == 'ACT.':
                    # Reactivación fuera de rango
                    impacto_otros += costoDelPlanNew
                    count_otros += 1
                    datosConciliacionDetalle.append({
                        'ID Servicio': sid,
                        'Cédula': row['Cédula'],
                        'Nombres': row['Nombres'],
                        'Concepto': 'Reactivación Fuera de Rango',
                        'Plan Anterior': planOld,
                        'Plan Actual': planNew,
                        'Estado Anterior': estatusOld,
                        'Estado Actual': estatusNew,
                        'Costo Anterior': costoOld,
                        'Costo Actual': costoDelPlanNew,
                        'Variación': costoDelPlanNew,
                        'Fecha': fechaEstadoFormat
                    })
                elif estatusOld == 'ACT.' and estatusNew != 'ACT.':
                    # Retiro fuera de rango
                    impacto_otros -= costoOld
                    count_otros += 1
                    datosConciliacionDetalle.append({
                        'ID Servicio': sid,
                        'Cédula': row['Cédula'],
                        'Nombres': row['Nombres'],
                        'Concepto': 'Retiro Fuera de Rango',
                        'Plan Anterior': planOld,
                        'Plan Actual': planNew,
                        'Estado Anterior': estatusOld,
                        'Estado Actual': estatusNew,
                        'Costo Anterior': costoOld,
                        'Costo Actual': 0.0,
                        'Variación': -costoOld,
                        'Fecha': fechaEstadoFormat
                    })
            
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
            if estadoServicioNew == 'ACT.':
                if is_instalacion_in_range:
                    impacto_instalaciones += costoDelPlanNew
                    count_instalaciones += 1
                    datosConciliacionDetalle.append({
                        'ID Servicio': sid,
                        'Cédula': row['Cédula'],
                        'Nombres': row['Nombres'],
                        'Concepto': 'Nuevas Instalaciones',
                        'Plan Anterior': '-',
                        'Plan Actual': planNew,
                        'Estado Anterior': '-',
                        'Estado Actual': estadoServicioNew,
                        'Costo Anterior': 0.0,
                        'Costo Actual': costoDelPlanNew,
                        'Variación': costoDelPlanNew,
                        'Fecha': fechaInstalacionFormat
                    })
                else:
                    impacto_otros += costoDelPlanNew
                    count_otros += 1
                    datosConciliacionDetalle.append({
                        'ID Servicio': sid,
                        'Cédula': row['Cédula'],
                        'Nombres': row['Nombres'],
                        'Concepto': 'Instalación Fuera de Rango',
                        'Plan Anterior': '-',
                        'Plan Actual': planNew,
                        'Estado Anterior': '-',
                        'Estado Actual': estadoServicioNew,
                        'Costo Anterior': 0.0,
                        'Costo Actual': costoDelPlanNew,
                        'Variación': costoDelPlanNew,
                        'Fecha': fechaInstalacionFormat
                    })

    for sid, row_old in old_dict.items():
        if sid not in processed_sids:
            tipoServicioOld = str(row_old.get('Tipo de servicio', '')).strip().upper()
            if tipoServicioOld in ['PYME', 'CORPORATIVO']:
                continue
                
            estatusOld = str(row_old['Estado servicio']).strip().upper()
            try:
                costoOld = float(row_old['Costo del plan'])
            except:
                costoOld = 0.0
                
            if estatusOld == 'ACT.':
                ingreso_ayer += costoOld
                impacto_retiros_pre_corte += costoOld
                count_activos_ayer += 1
                count_retiros_pre_corte += 1
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
        p_name = c['Plan'] or 'Sin Plan'
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
            "instalaciones": impacto_instalaciones,
            "cant_instalaciones": count_instalaciones,
            "reconexiones": impacto_reconexiones,
            "cant_reconexiones": count_reconexiones,
            "upgrades": impacto_upgrades,
            "cant_upgrades": count_upgrades,
            "upgrades_beneficio": impacto_upgrades_beneficio,
            "cant_upgrades_beneficio": count_upgrades_beneficio,
            "downgrades": impacto_downgrades,
            "cant_downgrades": count_downgrades,
            "retiros": impacto_retiros_post_corte + impacto_retiros_pre_corte,
            "cant_retiros": count_retiros_post_corte + count_retiros_pre_corte,
            "cant_diferencia_neta": totalActivos - count_activos_ayer
        },
        "conciliacion_financiera_corp": {
            "has_excel": True,
            "ingreso_ayer": ingreso_ayer_corp,
            "cant_ayer": count_activos_ayer_corp,
            "ingreso_hoy": ingreso_hoy_corp,
            "cant_hoy": count_activos_hoy_corp,
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

def build_plan_aggregates(users):
    total_activos = 0
    total_monto = 0.0
    datos_clientes_activos = []
    plan_aggregates = {}

    for item in users:
        status = str(item.get('service_status', '')).strip().upper()
        if status in ('ACTIVO', 'ACT.'):
            plan = str(item.get('plan', '')).strip() or 'Sin Plan'
            service_type = str(item.get('service_type', '')).strip().upper()
            
            # Omitir IPTV si corresponde
            if plan.upper() in ['IPTV', 'TV'] or service_type in ['IPTV', 'TV']:
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
    users_corp = (data_corp or {}).get("data", [])

    corp_sids = {str(u.get('id_servicio', '')).strip() for u in users_corp if str(u.get('id_servicio', '')).strip()}
    users_res = [u for u in users_gen if str(u.get('id_servicio', '')).strip() not in corp_sids]

    all_dict = {}
    for u in users_res:
        sid = str(u.get('id_servicio', '')).strip()
        if sid: all_dict[sid] = u
    for u in users_corp:
        sid = str(u.get('id_servicio', '')).strip()
        if sid: all_dict[sid] = u
    users_cons = list(all_dict.values())

    resumen_res = build_plan_aggregates(users_res)
    resumen_corp = build_plan_aggregates(users_corp)
    resumen_cons = build_plan_aggregates(users_cons)

    return {
        "residencial": resumen_res,
        "corporativo": resumen_corp,
        "consolidado": resumen_cons,
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
    
    for item in list_old:
        status = str(item.get('service_status', '')).strip().upper()
        plan = str(item.get('plan', '')).strip().upper()
        service_type = str(item.get('service_type', '')).strip().upper()
        
        if status == 'ACTIVO':
            if plan in ['IPTV', 'TV'] or service_type in ['IPTV', 'TV']:
                activos_iptv += 1
            else:
                activos_power += 1
            
    return {
        "activos_power": activos_power,
        "activos_iptv": activos_iptv
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
    
    # Fetch birthdays for this month (we look at all employees with a birthday)
    employees = db.query(models.Employee).filter(models.Employee.birthday_date != None, models.Employee.birthday_date != "").all()
    birthdays = []
    for emp in employees:
        try:
            bday = datetime.strptime(emp.birthday_date, '%Y-%m-%d').date()
            if bday.month == month:
                birthdays.append({
                    "day": bday.day,
                    "name": emp.full_name if hasattr(emp, 'full_name') else f"{emp.name} {emp.apellido or ''}".strip(),
                    "photo_url": emp.photo_url or "/static/img/default-avatar.png",
                    "department": emp.department
                })
        except:
            pass
            
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
async def view_directorio(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_user)):
    employees = db.query(models.Employee).all()
    return templates.TemplateResponse(request, "directorio.html", {"request": request, "user": current_user, "employees": employees})

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
    
    try:
        msg = MIMEMultipart()
        msg['From'] = user_data.smtp_user
        msg['To'] = user.email
        msg['Subject'] = "Actualización de Credenciales - Intranet Powerlink"
        
        body = f"Hola {user.full_name},\n\nTus credenciales de acceso han sido actualizadas.\n\nNuevo Correo: {user.email}\nNueva Contraseña: {user_data.password}\n\nSaludos,\nAdministración."
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP('mail.smtp2go.com', 2525)
        server.starttls()
        server.login(user_data.smtp_user, user_data.smtp_pass)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        return {"message": "Usuario actualizado, pero falló el envío de correo.", "error": str(e)}

    return {"message": "Usuario actualizado y correo enviado correctamente."}

@app.get("/historico", response_class=HTMLResponse)
async def view_historico(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
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
    except HTTPException:
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
async def api_get_chat_directory(db: Session = Depends(get_db)):
    all_users = db.query(models.User).filter(models.User.is_active == True).all()
    employees = db.query(models.Employee).all()
    emp_map = {emp.name: emp.department for emp in employees}
    
    departments = {}
    for u in all_users:
        dept = emp_map.get(u.full_name, "General")
        if dept not in departments:
            departments[dept] = []
        departments[dept].append({
            "email": u.email,
            "full_name": u.full_name,
            "avatar_url": u.avatar_url
        })
    return departments

