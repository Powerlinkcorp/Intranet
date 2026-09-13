import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="user") # "admin" (RRHH) or "user"
    permissions = Column(String, default="") # e.g. "cargar_datos_usuarios,ver_integracion"
    avatar_url = Column(String, default="/static/img/default-avatar.png")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    link_url = Column(String, default="#")
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False) # "Solicitudes", "Aplicaciones", "Plantillas", "Manual Empleado"
    file_path = Column(String, nullable=False)
    file_type = Column(String, default="pdf")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    apellido = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    cedula = Column(String, unique=True, index=True, nullable=True)
    position = Column(String, nullable=True)
    department = Column(String, default="General")
    photo_url = Column(String, nullable=True)
    birthday_date = Column(String, nullable=True) # e.g. "18 de Julio"

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

class KpiMetric(Base):
    __tablename__ = "kpi_metrics"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    value = Column(String, nullable=False)
    trend = Column(String, default="up") # "up", "down", "neutral"
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class PopupNotification(Base):
    __tablename__ = "popup_notifications"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Integer, nullable=False)
    month = Column(Integer, default=7)
    year = Column(Integer, default=2026)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, nullable=False)
    user_name = Column(String, nullable=False)
    channel = Column(String, default="#General")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ChatReadState(Base):
    __tablename__ = "chat_read_states"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, index=True, nullable=False)
    channel = Column(String, index=True, nullable=False)
    last_read_timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class PhoneExtension(Base):
    __tablename__ = 'phone_extensions'

    id = Column(Integer, primary_key=True, index=True)
    department = Column(String, index=True)
    name = Column(String)
    extension = Column(String)
    is_group = Column(Boolean, default=False)

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(String, index=True, nullable=False, unique=True)
    cedula = Column(String, index=True, nullable=True)
    name = Column(String, nullable=False)
    client_type = Column(String, default="Residencial") # Residencial, Corporativo
    current_plan = Column(String, nullable=True)
    status = Column(String, nullable=True)
    installation_date = Column(String, nullable=True)
    last_status_change_date = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    histories = relationship("ClientHistory", back_populates="client")

class ClientHistory(Base):
    __tablename__ = "client_history"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    record_date = Column(DateTime, nullable=False, index=True) # The date of the excel file or sweep
    event_type = Column(String, nullable=False) # e.g. STATUS_CHANGE, PLAN_CHANGE
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    client = relationship("Client", back_populates="histories")
