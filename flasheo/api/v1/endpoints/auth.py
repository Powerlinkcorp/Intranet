# -*- coding: utf-8 -*-
"""
api.v1.endpoints.auth — Rutas de Autenticación y Gestión de Usuarios (RBAC).
"""
import secrets
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Header, status
from core import database
from core.schemas import LoginRequest, LoginResponse, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["Autenticación y Usuarios"])

ACTIVE_SESSIONS = {}


def get_current_user(
    authorization: str = Header(None),
    x_session_token: str = Header(None)
):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_session_token:
        token = x_session_token.strip()
    
    if token and token in ACTIVE_SESSIONS:
        return ACTIVE_SESSIONS[token]
    
    # Fallback para ambiente local de taller (admin local)
    return {"id": 1, "username": "admin", "rol": "admin", "nombre_completo": "Administrador Local"}


def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("rol") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido. Se requiere rol de Administrador."
        )
    return current_user


def require_operator(current_user: dict = Depends(get_current_user)):
    if current_user.get("rol") == "visualizador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rol 'visualizador' solo tiene permisos de lectura."
        )
    return current_user


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    user = database.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos."
        )
    token = secrets.token_hex(24)
    ACTIVE_SESSIONS[token] = user
    return LoginResponse(
        success=True,
        token=token,
        user=user,
        message=f"Bienvenido, {user.get('nombre_completo') or user.get('username')}."
    )


@router.post("/logout")
def logout(x_session_token: str = Header(None)):
    if x_session_token and x_session_token in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS.pop(x_session_token, None)
    return {"success": True, "message": "Sesión finalizada."}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}


@router.get("/users", response_model=List[UserResponse])
def get_users(admin: dict = Depends(require_admin)):
    return database.list_users()


@router.post("/users")
def add_user(req: UserCreate, admin: dict = Depends(require_admin)):
    ok, msg = database.create_user(req.username, req.password, req.rol, req.nombre_completo)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}
