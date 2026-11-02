import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict
from dotenv import load_dotenv

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
import models

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "secretkey1234567890supersecretkey")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Rate Limiting anti fuerza bruta — IP -> lista de timestamps de intentos fallidos
LOGIN_ATTEMPTS: Dict[str, list] = {}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME_SECONDS = 300  # 5 minutos de bloqueo


def is_rate_limited(ip_address: str) -> bool:
    if ip_address in ("127.0.0.1", "localhost", "::1", "unknown"):
        return False
    now = time.time()
    attempts = LOGIN_ATTEMPTS.get(ip_address, [])
    recent = [t for t in attempts if now - t < LOCKOUT_TIME_SECONDS]
    LOGIN_ATTEMPTS[ip_address] = recent
    return len(recent) >= MAX_LOGIN_ATTEMPTS


def record_failed_attempt(ip_address: str):
    now = time.time()
    LOGIN_ATTEMPTS.setdefault(ip_address, []).append(now)


def clear_failed_attempts(ip_address: str):
    LOGIN_ATTEMPTS.pop(ip_address, None)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _extract_token_from_request(request: Request) -> Optional[str]:
    """
    Extrae el token JWT desde:
    1. Cookie HTTP-Only 'access_token'
    2. Header Authorization: Bearer <token>
    Llamada como función pura (sin Depends).
    """
    # Prioridad 1: cookie
    cookie_val = request.cookies.get("access_token")
    if cookie_val:
        return cookie_val[len("Bearer "):] if cookie_val.startswith("Bearer ") else cookie_val

    # Prioridad 2: header Authorization
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):]

    return None


def get_token_from_request(request: Request) -> Optional[str]:
    """Alias público para uso directo (sin Depends)."""
    return _extract_token_from_request(request)


def _decode_token(token: str) -> str:
    """Decodifica un JWT y retorna el username del sujeto. Lanza HTTPException si es inválido."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalido: sin sujeto.",
            )
        return username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso invalido o expirado.",
        )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    """
    Dependencia FastAPI para obtener el usuario autenticado.
    Compatible con llamada directa (sin Depends) desde rutas HTML.
    """
    token = _extract_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se encontro token de autenticacion.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = _decode_token(token)

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o no encontrado.",
        )
    return user


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    perms = current_user.permissions or ""
    if current_user.role not in ["admin", "rrhh"] and "cargar_datos_usuarios" not in perms and "gestionar_permisos" not in perms and "editar_usuarios" not in perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requieren permisos de Gestor/Administrador.",
        )
    return current_user
