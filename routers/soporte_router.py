# -*- coding: utf-8 -*-
"""
routers.soporte_router — Módulo de Documentación de Casos de Soporte Remoto.
Reemplaza y optimiza el flujo de Google Sheets ("Incidencias de soporte remoto"):
  1. Búsqueda instantánea por Cédula/RIF en la base de clientes (Rubpi Snapshots / DB local),
     retornando TODOS los servicios y direcciones asociados para selección en modal.
  2. Registro ultrarrápido con selección manual de HUB por botones, fallas (Reporte),
     resolución (Solución), canal (Observación) y estado de router.
  3. Numeración consecutiva automática por día (N° Caso), métricas en vivo e historial.
  4. Exportación compatible 1:1 con la estructura del Google Sheets del equipo.
"""
import csv
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from database import Base, engine, get_db
import models
import security

# Asegurar que la tabla support_cases exista en la base de datos activa
try:
    models.Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"[SOPORTE] Advertencia verificando tablas: {e}")

templates = Jinja2Templates(directory="templates")
router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "static/uploads")
GOOGLE_SHEETS_WEBHOOK_URL = os.getenv(
    "GOOGLE_SHEETS_WEBHOOK_URL",
    "https://script.google.com/macros/s/AKfycbwqpPJoqAdWqz7u9gxw6uOq0LSwaHvbcq14c8VoXX2FnpQUzKmhj0BQGkBcSMiHead_ZA/exec",
)


def _enviar_casos_a_google_sheets(casos_dicts: list) -> dict:
    """Envía uno o múltiples casos recién creados hacia Google Sheets mediante el Webhook de Apps Script."""
    if not GOOGLE_SHEETS_WEBHOOK_URL or not casos_dicts:
        return {"ok": False, "detalle": "Webhook no configurado"}
    try:
        resp = requests.post(
            GOOGLE_SHEETS_WEBHOOK_URL,
            json={"casos": casos_dicts},
            timeout=20,
        )
        data = resp.json()
        if data.get("status") == "ok":
            return {
                "ok": True,
                "insertados": data.get("insertados", len(casos_dicts)),
                "desde_fila": data.get("desde_fila"),
                "hasta_fila": data.get("hasta_fila"),
            }
        return {"ok": False, "detalle": data.get("message", "Respuesta no exitosa de Google Sheets")}
    except Exception as e:
        print(f"[SOPORTE -> SHEETS] Error enviando a Google Sheets: {e}")
        return {"ok": False, "detalle": str(e)}

# ============================================================================
# CATÁLOGOS OFICIALES EXTRAÍDOS DEL HISTÓRICO DE SOPORTE REMOTO (52,000+ CASOS)
# ============================================================================
CATALOGO_HUBS = [
    {"code": "CMDP", "label": "CMDP"},
    {"code": "MAC", "label": "MAC"},
    {"code": "VALL", "label": "VALL"},
    {"code": "TEJ", "label": "TEJ"},
    {"code": "SJ", "label": "SJ"},
    {"code": "RET", "label": "RET"},
    {"code": "CUM", "label": "CUM"},
    {"code": "PRIN", "label": "PRIN"},
    {"code": "PROP", "label": "PROP"},
    {"code": "TIB", "label": "TIB"},
    {"code": "PAR", "label": "PAR"},
    {"code": "N/A", "label": "N/A"},
]

CATALOGO_REPORTES = [
    "Sin servicio",
    "Lentitud",
    "Intermitencia",
    "Afectación",
    "Asesoría",
    "Cambio de clave",
    "Adecuaciones",
    "Suspendido administrativamente",
    "PowerLink GO",
    "Falla de acceso web / Streaming",
    "Fibra caída / holgada",
]

CATALOGO_SOLUCIONES = [
    "Reinicio / Resincronización de ONU",
    "Visita técnica",
    "Cambio de VLAN",
    "Red interna / Router cliente",
    "Caso de afectación",
    "Asesoría facilitada",
    "Cambio de clave realizado",
    "Remitido a otro departamento",
    "Adecuación de red",
    "Falla de proveedor",
    "Sin respuesta del cliente",
]

# Mapeo inteligente Falla -> Resolución automática (elimina doble clic en casos redundantes)
MAPEO_FALLA_SOLUCION_DIRECTA = {
    "Afectación": "Caso de afectación",
    "Cambio de clave": "Cambio de clave realizado",
    "Adecuaciones": "Adecuación de red",
    "Suspendido administrativamente": "Remitido a otro departamento",
    "Asesoría": "Asesoría facilitada",
    "Fibra caída / holgada": "Visita técnica",
}

CATALOGO_OBSERVACIONES = [
    "Rubpi",
    "Llamada",
    "Requerimientos",
]


def _cargar_catalogo_subsectores() -> list:
    path_sub = os.path.join(UPLOAD_DIR, "catalogo_subsectores.json")
    try:
        if os.path.exists(path_sub):
            with open(path_sub, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[SOPORTE] Error cargando catalogo_subsectores.json: {e}")
    return []


CATALOGO_SUBSECTORES = _cargar_catalogo_subsectores()


# ============================================================================
# ÍNDICE MULTISERVICIO EN MEMORIA (UN CLIENTE -> MÚLTIPLES DIRECCIONES/CONTRATOS)
# ============================================================================
_multi_clients_index = {}
_multi_services_by_id = {}
_multi_clients_mtimes = (0, 0)


def _format_phone(p: Optional[str]) -> str:
    p = str(p or "").strip()
    if not p:
        return ""
    digits = re.sub(r"[^0-9]", "", p)
    if digits.startswith("58") and len(digits) == 12:
        return "0" + digits[2:5] + "-" + digits[5:]
    if digits.startswith("0") and len(digits) == 11:
        return digits[:4] + "-" + digits[4:]
    return p


def _build_zona_str(u: dict) -> str:
    parts = []
    for k in ("state", "city", "urban", "sector"):
        val = str(u.get(k) or "").strip()
        if val and val.lower() not in [p.lower() for p in parts]:
            parts.append(val)
    return ", ".join(parts)


def _normalizar_zona_oficial(texto: str) -> str:
    """
    Normaliza cualquier dirección/sector de la API o del Sheets a las macro-zonas oficiales,
    agrupando San Pedro dentro de LOS TEQUES tal como fue solicitado.
    """
    u = str(texto or "").upper().strip()
    u_clean = re.sub(r"\b(N/A|SIN ZONA|NONE|SIN DIRECCION REGISTRADA)\b", "", u).strip()
    if not u_clean:
        return ""
    if any(k in u_clean for k in ("TEJERIA", "TEJERÍA", "SANTOS MICHELENA", "CURIEPE", "JABILLAL", "CAÑAOTE", "CANAOTE", "BUCARAL", "TRAPICHE DEL MEDIO", "TINAPUEY", "LA GRUTA", "ARAGUA")):
        return "TEJERIAS"
    if any(k in u_clean for k in ("CARRIZAL", "LLANO ALTO", "BRISAS DE ORIENTE", "CORRALITO", "BAROLA", "YERBA BUENA", "JOSE MANUEL ALVAREZ", "JOSÉ MANUEL ALVAREZ", "MONTAÑA ALTA", "MONTANA ALTA", "POTRERITO", "COLISEO", "LOMAS DE URQUIA", "AMIGOS REUNIDOS")):
        return "CARRIZAL"
    if any(k in u_clean for k in ("SAN DIEGO", "CECILIO ACOSTA", "SAN JOSE", "SAN JOSÉ", "AGUA FRIA", "CANTARANA", "GUAREGUARE", "EL NARANJAL", "EL PRADO", "CORTADA EL GUAYABO", "EL PEÑON", "EL PENON", "LA CRUCECITA", "LA OCI", "LAS YEGUAS", "VISTA HERMOSA")):
        return "SAN DIEGO"
    if any(k in u_clean for k in ("LOS SALIAS", "SAN ANTONIO DE LOS ALTOS", "SAN ANTORIO", "LA ROSALEDA", "LOS CASTORES", "LAS MINAS", "LAS POLONIAS", "EL RETIRO", "LOS HELECHOS", "LA MORITA", "EL PARAMO", "EL PÁRAMO", "RES. OPS", "SIERRA BRAVA", "LA POMOROSA", "C.C LA CASONA", "C.C COLINAS", "LAS CHURUATAS")):
        return "SAN ANTONIO"
    if "SAN ANTONIO" in u_clean and "EL VALLE" not in u_clean and "CARACAS" not in u_clean:
        return "SAN ANTONIO"
    if any(k in u_clean for k in ("PROPATRIA", "CATIA", "LA SILSA", "PEREZ BONALDE", "PÉREZ BONALDE", "MAGALLANES", "CALLE ECUADOR", "CALLE COLOMBIA", "CERRO NEGRO")):
        return "PROPATRIA"
    if "LA VEGA" in u_clean:
        return "LA VEGA"
    if any(k in u_clean for k in ("COCHE", "VEREDAS DE COCHE", "LAS MAYAS")):
        return "COCHE"
    if any(k in u_clean for k in ("CUMBRE ROJA", "CUMBRE ROJAS", "CAÑA LARGA", "CANA LARGA", "TRABUCO")):
        return "CUMBRE ROJA"
    if any(k in u_clean for k in ("EL VALLE", "BRUZUAL", "LOS JARDINES", "CALLE 18", "EL 70", "LOS EUCALIPTOS", "EL CEIBO", "LOS CARDONES", "EL TAMARINDO", "CALLE 5 DE JULIO", "SANTA ROSALIA", "TURMERITO", "FONVICA", "LIBERTADOR", "CARACAS")):
        return "EL VALLE"
    # San Pedro y sectores de Guaicaipuro se agrupan en LOS TEQUES
    if any(k in u_clean for k in ("LOS TEQUES", "SAN PEDRO", "POZO DE ROSAS", "GUAICAIPURO", "LA MATICA", "LA MACARENA", "MACARENA", "EL PASO", "EL NACIONAL", "LAGUNETICA", "EL VIGIA", "LA QUINTA", "SOLAR DE LA QUINTA", "GUAREMAL", "RAMO VERDE", "SANTA EULALIA", "PALO ALTO", "LOS LAGOS", "SANTA ROSA", "LOS ALPES", "EL CHORRITO", "RETAMAL", "EL BARBECHO", "EL TRIGO", "CABOTAJE", "ROMULO GALLEGO", "ALBERTO RAVELL", "23 DE ENERO", "LA ESTRELLA", "PUNTA BRAVA", "JOSE GREGORIO", "VALLE ALTO", "BERMUDEZ", "ALTO VERDE")):
        return "LOS TEQUES"
    return u_clean


def _get_multi_clients_index():
    """
    Indexa todos los contratos de last_snapshot.json y last_snapshot_corporativo.json
    agrupando en una LISTA todos los servicios que pertenecen a una misma Cédula o RIF.
    """
    global _multi_clients_index, _multi_services_by_id, _multi_clients_mtimes

    path_res = os.path.join(UPLOAD_DIR, "last_snapshot.json")
    path_corp = os.path.join(UPLOAD_DIR, "last_snapshot_corporativo.json")

    mtime_res = os.path.getmtime(path_res) if os.path.exists(path_res) else 0
    mtime_corp = os.path.getmtime(path_corp) if os.path.exists(path_corp) else 0
    current_mtimes = (mtime_res, mtime_corp)

    if _multi_clients_index and _multi_clients_mtimes == current_mtimes:
        return _multi_clients_index, _multi_services_by_id

    new_index = {}
    by_service_id = {}

    def _add_record(u: dict, default_tipo: str):
        doc_raw = str(u.get("doc") or "").strip().upper()
        if not doc_raw:
            return
        doc_digits = re.sub(r"[^0-9A-Z]", "", doc_raw)
        only_nums = re.sub(r"[^0-9]", "", doc_raw)
        dt = str(u.get("doc_type") or "").strip().upper()

        id_srv = str(u.get("id_servicio") or "").strip()
        service_type = str(u.get("service_type") or default_tipo).strip().upper()

        onu_val = u.get("onu_sn") or u.get("onu") or u.get("onu_mac") or ""
        if " / " in str(onu_val):
            onu_val = str(onu_val).split(" / ")[0].strip()

        address = str(u.get("address") or "").strip()
        urban = str(u.get("urban") or "").strip()
        city = str(u.get("city") or "").strip()
        sector = str(u.get("sector") or "").strip()
        state = str(u.get("state") or "").strip()
        zona_compuesta = _build_zona_str(u)
        zona_oficial = _normalizar_zona_oficial(f"{zona_compuesta} {address}")

        item = {
            "id_servicio": id_srv,
            "id_usuario": str(u.get("id_usuario") or ""),
            "cedula": f"{dt}-{doc_raw}" if dt and not doc_raw.startswith(dt) else doc_raw,
            "doc": only_nums or doc_digits,
            "doc_type": dt,
            "nombre": str(u.get("name") or "").strip(),
            "telefono1": _format_phone(u.get("phone")),
            "telefono2": _format_phone(u.get("phone_2")),
            "email": str(u.get("email") or "").strip(),
            "ubicacion": address or urban or zona_compuesta or "Sin dirección registrada",
            "zona": zona_oficial or urban or city or zona_compuesta or "",
            "zona_completa": zona_compuesta,
            "state": state,
            "city": city,
            "urban": urban,
            "sector": sector,
            "plan": str(u.get("plan") or "Sin plan").strip(),
            "estado_servicio": str(u.get("service_status") or "DESCONOCIDO").strip().upper(),
            "tipo_servicio": service_type,
            "onu": str(onu_val),
            "vlan": str(u.get("vlan") or ""),
        }

        keys_to_register = set()
        if doc_digits:
            keys_to_register.add(doc_digits)
        if only_nums:
            keys_to_register.add(only_nums)
        if dt and only_nums:
            keys_to_register.add(f"{dt}-{only_nums}")
            keys_to_register.add(f"{dt}{only_nums}")
        if dt and doc_digits:
            keys_to_register.add(f"{dt}-{doc_digits}")
            keys_to_register.add(f"{dt}{doc_digits}")

        for k in keys_to_register:
            lst = new_index.setdefault(k, [])
            # Evitar duplicar el mismo id_servicio dentro de la misma cédula
            if id_srv and any(existing.get("id_servicio") == id_srv for existing in lst):
                continue
            lst.append(item)

        if id_srv:
            by_service_id[id_srv] = item

    if os.path.exists(path_res):
        try:
            with open(path_res, "r", encoding="utf-8") as f:
                for u in json.load(f).get("data", []):
                    _add_record(u, "RESIDENCIAL")
        except Exception as e:
            print(f"[SOPORTE] Error indexando last_snapshot.json: {e}")

    if os.path.exists(path_corp):
        try:
            with open(path_corp, "r", encoding="utf-8") as f:
                for u in json.load(f).get("data", []):
                    _add_record(u, "CORPORATIVO")
        except Exception as e:
            print(f"[SOPORTE] Error indexando last_snapshot_corporativo.json: {e}")

    _multi_clients_index = new_index
    _multi_services_by_id = by_service_id
    _multi_clients_mtimes = current_mtimes
    return _multi_clients_index, _multi_services_by_id


# ============================================================================
# ESQUEMAS PYDANTIC
# ============================================================================
class SupportCaseCreate(BaseModel):
    cedula: str
    nombre_cliente: Optional[str] = ""
    id_servicio: Optional[str] = ""
    telefono: Optional[str] = ""
    plan: Optional[str] = ""
    analista: Optional[str] = ""
    reporte: str
    solucion: str
    observacion: Optional[str] = "Rubpi"
    notas_adicionales: Optional[str] = ""
    hub: str
    zona: Optional[str] = ""
    ubicacion: Optional[str] = ""
    router_limitado: Optional[bool] = False
    router_modelo: Optional[str] = ""
    fecha_iso: Optional[str] = ""  # Opcional (por defecto hoy)


class SupportCaseUpdate(BaseModel):
    cedula: Optional[str] = None
    nombre_cliente: Optional[str] = None
    id_servicio: Optional[str] = None
    telefono: Optional[str] = None
    plan: Optional[str] = None
    reporte: Optional[str] = None
    solucion: Optional[str] = None
    observacion: Optional[str] = None
    notas_adicionales: Optional[str] = None
    hub: Optional[str] = None
    zona: Optional[str] = None
    ubicacion: Optional[str] = None
    router_limitado: Optional[bool] = None
    router_modelo: Optional[str] = None


class SupportBulkAfectacionCreate(BaseModel):
    cantidad: int
    hub: str
    ubicacion: str
    zona: Optional[str] = ""
    observacion: Optional[str] = "Rubpi"
    fecha_iso: Optional[str] = ""


# ============================================================================
# VISTA PRINCIPAL HTML
# ============================================================================
@router.get("/soporte/casos", response_class=HTMLResponse)
async def soporte_casos_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
    except Exception:
        return RedirectResponse(url="/login")

    embed = request.query_params.get("embed") == "1"
    return templates.TemplateResponse(
        request,
        "soporte_casos.html",
        {
            "user": user,
            "embed": embed,
            "hubs": CATALOGO_HUBS,
            "reportes": CATALOGO_REPORTES,
            "soluciones": CATALOGO_SOLUCIONES,
            "observaciones": CATALOGO_OBSERVACIONES,
            "subsectores": CATALOGO_SUBSECTORES,
        },
    )


# ============================================================================
# ENDPOINTS API: BÚSQUEDA DE CLIENTE CON MÚLTIPLES SERVICIOS / DIRECCIONES
# ============================================================================
@router.get("/api/soporte/buscar_cliente")
def buscar_cliente_por_cedula(
    request: Request,
    q: str = Query(..., description="Cédula, RIF o ID de servicio del cliente"),
    db: Session = Depends(get_db),
):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    raw_q = q.strip().upper()
    if not raw_q:
        return {"encontrado": False, "servicios": [], "mensaje": "Ingrese una cédula o RIF"}

    clean_alnum = re.sub(r"[^0-9A-Z]", "", raw_q)
    clean_digits = re.sub(r"[^0-9]", "", raw_q)

    index, by_service_id = _get_multi_clients_index()

    servicios_encontrados = []
    seen_ids = set()

    # 1. Búsqueda por clave exacta, alfanumérica o solo dígitos
    for candidate_key in (raw_q, clean_alnum, clean_digits):
        if candidate_key and candidate_key in index:
            for srv in index[candidate_key]:
                sid = srv.get("id_servicio") or f"{srv.get('ubicacion')}-{srv.get('plan')}"
                if sid not in seen_ids:
                    seen_ids.add(sid)
                    servicios_encontrados.append(srv)

    # 2. Si no se halló por cédula, probar si ingresó directamente un ID de servicio
    if not servicios_encontrados and clean_digits and clean_digits in by_service_id:
        srv = by_service_id[clean_digits]
        # Si encontramos el servicio por ID, traer todos los servicios del titular para que pueda verlos
        doc_titular = srv.get("doc")
        if doc_titular and doc_titular in index:
            servicios_encontrados = list(index[doc_titular])
        else:
            servicios_encontrados = [srv]

    # 3. Fallback a la tabla SQL models.Client si no está en el snapshot JSON
    if not servicios_encontrados and clean_digits:
        try:
            sql_clients = (
                db.query(models.Client)
                .filter(
                    or_(
                        models.Client.cedula.ilike(f"%{clean_digits}%"),
                        models.Client.service_id == clean_digits,
                    )
                )
                .limit(20)
                .all()
            )
            for c in sql_clients:
                servicios_encontrados.append(
                    {
                        "id_servicio": str(c.service_id or ""),
                        "id_usuario": "",
                        "cedula": str(c.cedula or clean_digits),
                        "doc": clean_digits,
                        "doc_type": "",
                        "nombre": str(c.name or ""),
                        "telefono1": "",
                        "telefono2": "",
                        "email": "",
                        "ubicacion": "Dirección no especificada en DB local",
                        "zona": "",
                        "zona_completa": "",
                        "plan": str(c.current_plan or ""),
                        "estado_servicio": str(c.status or "ACTIVO").upper(),
                        "tipo_servicio": str(c.client_type or "RESIDENCIAL").upper(),
                        "onu": "",
                        "vlan": "",
                    }
                )
        except Exception as e:
            print(f"[SOPORTE] Error fallback SQL Client: {e}")

    # Ordenar servicios: primero los que tienen dirección física e Internet (RESIDENCIAL/CORPORATIVO) y estado ACTIVO
    def _sort_priority(s: dict):
        is_iptv = 1 if "IPTV" in str(s.get("tipo_servicio", "")).upper() else 0
        is_active = 0 if s.get("estado_servicio") == "ACTIVO" else 1
        return (is_iptv, is_active, str(s.get("id_servicio") or ""))

    servicios_encontrados.sort(key=_sort_priority)

    # 4. Consultar historial previo en SupportCase para esta cédula (últimos 5 casos, HUB dominante y alarmas de reincidencia)
    historial_casos = []
    ultimo_hub_sugerido = ""
    ultima_zona_sugerida = ""
    ultima_ubicacion_sugerida = ""
    total_historial_casos = 0
    casos_ultima_semana = 0
    casos_ultimo_mes = 0
    nivel_alarma = "NORMAL"

    if clean_digits:
        try:
            all_prev = (
                db.query(models.SupportCase)
                .filter(models.SupportCase.cedula.ilike(f"%{clean_digits}%"))
                .order_by(desc(models.SupportCase.id))
                .all()
            )
            total_historial_casos = len(all_prev)
            for pc in all_prev[:5]:
                historial_casos.append(pc.to_dict())
            if all_prev:
                hub_counts = Counter(
                    (pc.hub or "").strip().upper()
                    for pc in all_prev
                    if (pc.hub or "").strip().upper() not in ("", "N/A", "SIN HUB", "NONE")
                )
                if hub_counts:
                    ultimo_hub_sugerido = hub_counts.most_common(1)[0][0]
                else:
                    ultimo_hub_sugerido = all_prev[0].hub or ""
                ultima_zona_sugerida = all_prev[0].zona or ""
                ultima_ubicacion_sugerida = all_prev[0].ubicacion or ""

                # Calcular reincidencia en los últimos 7 días y en el mes actual (según la fecha más reciente o hoy)
                hoy_dt = datetime.now()
                hace_7d = (hoy_dt - timedelta(days=7)).strftime("%Y-%m-%d")
                mes_actual = hoy_dt.strftime("%Y-%m")
                for pc in all_prev:
                    f_iso = (pc.fecha_iso or "").strip()
                    if f_iso >= hace_7d:
                        casos_ultima_semana += 1
                    if f_iso.startswith(mes_actual):
                        casos_ultimo_mes += 1

                if casos_ultima_semana >= 3 or casos_ultimo_mes >= 5:
                    nivel_alarma = "CRITICA"
                elif casos_ultima_semana == 2 or casos_ultimo_mes >= 3:
                    nivel_alarma = "ALTA"
                elif casos_ultimo_mes == 2:
                    nivel_alarma = "OBSERVACION"
        except Exception as e:
            print(f"[SOPORTE] Error consultando historial de casos: {e}")

    if not servicios_encontrados:
        return {
            "encontrado": False,
            "cedula_buscada": raw_q,
            "total_servicios": 0,
            "multiple": False,
            "servicios": [],
            "historial_casos": historial_casos,
            "total_historial_casos": total_historial_casos,
            "casos_ultima_semana": casos_ultima_semana,
            "casos_ultimo_mes": casos_ultimo_mes,
            "nivel_alarma": nivel_alarma,
            "ultimo_hub_sugerido": ultimo_hub_sugerido,
            "ultima_zona_sugerida": ultima_zona_sugerida,
            "ultima_ubicacion_sugerida": ultima_ubicacion_sugerida,
            "mensaje": f"No se encontró cliente en base de datos para '{raw_q}'. Puedes completar los datos manualmente.",
        }

    titular = servicios_encontrados[0]
    return {
        "encontrado": True,
        "cedula": titular.get("cedula") or raw_q,
        "doc": titular.get("doc") or clean_digits,
        "nombre": titular.get("nombre") or "",
        "telefono": titular.get("telefono1") or "",
        "total_servicios": len(servicios_encontrados),
        "multiple": len(servicios_encontrados) > 1,
        "servicios": servicios_encontrados,
        "historial_casos": historial_casos,
        "total_historial_casos": total_historial_casos,
        "casos_ultima_semana": casos_ultima_semana,
        "casos_ultimo_mes": casos_ultimo_mes,
        "nivel_alarma": nivel_alarma,
        "ultimo_hub_sugerido": ultimo_hub_sugerido,
        "ultima_zona_sugerida": ultima_zona_sugerida,
        "ultima_ubicacion_sugerida": ultima_ubicacion_sugerida,
    }


# ============================================================================
# ENDPOINT PARA ACTUALIZAR SNAPSHOT DE CLIENTES RUBPI BAJO DEMANDA
# ============================================================================
@router.post("/api/soporte/sincronizar_clientes")
def sincronizar_base_clientes(request: Request):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    login_url = "https://powerlink.rubpi.com/api/login"
    creds = {"username": "api_exp", "password": "-?J+\\FcmKT2zWl5A28=~"}

    try:
        req = urllib.request.Request(
            login_url,
            data=json.dumps(creds).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            login_data = json.loads(resp.read().decode())
            api_token = login_data.get("token") or login_data.get("access_token")
        if not api_token:
            raise Exception("No se recibió token de Rubpi API")

        def _export_and_wait(url_export: str):
            r = urllib.request.Request(
                url_export,
                headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(r, timeout=15) as resp2:
                tid = json.loads(resp2.read().decode()).get("task_id")
            if not tid:
                raise Exception("No se recibió task_id de exportación")
            for _ in range(25):
                time.sleep(2)
                r2 = urllib.request.Request(
                    f"https://powerlink.rubpi.com/api/exports/users/{tid}",
                    headers={"Authorization": f"Bearer {api_token}"},
                    method="GET",
                )
                try:
                    with urllib.request.urlopen(r2, timeout=30) as resp3:
                        return json.loads(resp3.read().decode())
                except urllib.error.HTTPError as he:
                    if he.code == 400:
                        continue
                    raise
            raise Exception("Tiempo de espera agotado descargando clientes")

        data_gen = _export_and_wait("https://powerlink.rubpi.com/api/exports/users")
        path_res = os.path.join(UPLOAD_DIR, "last_snapshot.json")
        with open(path_res, "w", encoding="utf-8") as f:
            json.dump(data_gen, f)

        data_corp = _export_and_wait("https://powerlink.rubpi.com/api/exports/users?is_natural=0")
        path_corp = os.path.join(UPLOAD_DIR, "last_snapshot_corporativo.json")
        with open(path_corp, "w", encoding="utf-8") as f:
            json.dump(data_corp, f)

        # Forzar recarga del índice en memoria
        global _multi_clients_mtimes
        _multi_clients_mtimes = (0, 0)
        idx, by_srv = _get_multi_clients_index()

        return {
            "status": "ok",
            "total_contratos": len(by_srv),
            "mensaje": f"Base de clientes actualizada ({len(by_srv)} servicios indexados).",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sincronizando clientes: {str(e)}")


# ============================================================================
# ENDPOINTS CRUD DE CASOS DE SOPORTE REMOTO
# ============================================================================
@router.get("/api/soporte/casos")
def listar_casos_soporte(
    request: Request,
    fecha_iso: Optional[str] = Query(None, description="YYYY-MM-DD o 'todas'"),
    desde: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    hasta: Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD"),
    q: Optional[str] = Query(None, description="Búsqueda por cédula, cliente, dirección o servicio"),
    hub: Optional[str] = Query(None),
    analista: Optional[str] = Query(None),
    reporte: Optional[str] = Query(None),
    solucion: Optional[str] = Query(None),
    limit: int = Query(300, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    user = security.get_current_user(request, db)
    hoy_iso = datetime.now().strftime("%Y-%m-%d")
    target_fecha = fecha_iso if fecha_iso else hoy_iso

    query = db.query(models.SupportCase)
    tiene_busqueda = bool(q and q.strip())

    # Si el analista escribe una cédula o término en el buscador, buscar en TODO el historial de fechas
    if desde and hasta:
        query = query.filter(models.SupportCase.fecha_iso >= desde, models.SupportCase.fecha_iso <= hasta)
    elif not tiene_busqueda and target_fecha != "todas":
        query = query.filter(models.SupportCase.fecha_iso == target_fecha)

    if hub and hub != "TODOS":
        query = query.filter(models.SupportCase.hub == hub)
    if analista and analista != "TODOS":
        query = query.filter(models.SupportCase.analista.ilike(f"%{analista}%"))
    if reporte and reporte != "TODOS":
        query = query.filter(models.SupportCase.reporte == reporte)
    if solucion and solucion != "TODOS":
        query = query.filter(models.SupportCase.solucion == solucion)

    if tiene_busqueda:
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.SupportCase.cedula.ilike(term),
                models.SupportCase.nombre_cliente.ilike(term),
                models.SupportCase.ubicacion.ilike(term),
                models.SupportCase.zona.ilike(term),
                models.SupportCase.id_servicio.ilike(term),
                models.SupportCase.notas_adicionales.ilike(term),
            )
        )

    casos = (
        query.order_by(
            desc(models.SupportCase.fecha_iso),
            desc(models.SupportCase.numero_caso),
            desc(models.SupportCase.id),
        )
        .limit(limit)
        .all()
    )

    # Calcular métricas del día actual (o de la fecha seleccionada)
    metric_date = target_fecha if target_fecha != "todas" else hoy_iso
    casos_dia = (
        db.query(models.SupportCase)
        .filter(models.SupportCase.fecha_iso == metric_date)
        .all()
    )

    nombre_usuario_actual = (user.full_name or user.username or "").strip()
    total_dia = len(casos_dia)
    mis_casos_dia = sum(
        1 for c in casos_dia if (c.analista or "").strip().lower() == nombre_usuario_actual.lower()
    )
    max_num_dia = max((c.numero_caso or 0 for c in casos_dia), default=0)

    hub_counts = Counter(c.hub for c in casos_dia if c.hub)
    reporte_counts = Counter(c.reporte for c in casos_dia if c.reporte)
    analista_counts = Counter(c.analista for c in casos_dia if c.analista)

    # Verificar cuántos contratos hay indexados en memoria
    _, by_srv = _get_multi_clients_index()

    return {
        "fecha_activa": metric_date,
        "usuario_actual": nombre_usuario_actual,
        "total_indexados_api": len(by_srv),
        "resumen": {
            "total_dia": total_dia,
            "mis_casos_dia": mis_casos_dia,
            "proximo_numero_caso": max_num_dia + 1,
            "por_hub": dict(hub_counts.most_common(12)),
            "por_reporte": dict(reporte_counts.most_common(8)),
            "por_analista": dict(analista_counts.most_common(10)),
        },
        "casos": [c.to_dict() for c in casos],
    }


@router.post("/api/soporte/casos")
def crear_caso_soporte(
    payload: SupportCaseCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    user = security.get_current_user(request, db)

    cedula_clean = (payload.cedula or "").strip().upper()
    if not cedula_clean:
        raise HTTPException(status_code=400, detail="La cédula o RIF del cliente es obligatoria.")
    if not (payload.reporte or "").strip():
        raise HTTPException(status_code=400, detail="Debe seleccionar o indicar la falla reportada.")
    if not (payload.solucion or "").strip():
        raise HTTPException(status_code=400, detail="Debe seleccionar o indicar la resolución aplicada.")
    if not (payload.hub or "").strip():
        raise HTTPException(status_code=400, detail="Debe elegir el HUB mediante los botones de selección.")

    now = datetime.now()
    if payload.fecha_iso and re.match(r"^\d{4}-\d{2}-\d{2}$", payload.fecha_iso.strip()):
        fecha_iso = payload.fecha_iso.strip()
        dt_obj = datetime.strptime(fecha_iso, "%Y-%m-%d")
        fecha_display = f"{dt_obj.day}/{dt_obj.strftime('%m/%Y')}"
    else:
        fecha_iso = now.strftime("%Y-%m-%d")
        fecha_display = f"{now.day}/{now.strftime('%m/%Y')}"

    # Calcular el consecutivo N° CASO del día (igual que en la hoja de Google Sheets)
    max_num = (
        db.query(func.max(models.SupportCase.numero_caso))
        .filter(models.SupportCase.fecha_iso == fecha_iso)
        .scalar()
    )
    siguiente_numero = (max_num or 0) + 1

    analista_nombre = (payload.analista or "").strip() or (user.full_name or user.username or "Soporte")

    # Siempre priorizar la dirección, zona y datos del titular desde la API si la cédula existe
    nombre_final = (payload.nombre_cliente or "").strip()
    id_srv_final = (payload.id_servicio or "").strip()
    tel_final = (payload.telefono or "").strip()
    plan_final = (payload.plan or "").strip()
    ubicacion_final = (payload.ubicacion or "").strip()
    zona_final = (payload.zona or "").strip()

    digits_ced = re.sub(r"[^0-9]", "", cedula_clean)
    alnum_ced = re.sub(r"[^0-9A-Z]", "", cedula_clean)
    hub_final = payload.hub.strip().upper()
    tiene_direcciones_distintas = False

    if digits_ced:
        idx_map, _ = _get_multi_clients_index()
        srvs_api = idx_map.get(cedula_clean) or idx_map.get(alnum_ced) or idx_map.get(digits_ced)
        if srvs_api:
            dirs_fibra = {
                re.sub(r"[^A-Z0-9]", "", str(s.get("ubicacion") or "").upper())
                for s in srvs_api
                if "IPTV" not in str(s.get("tipo_servicio") or "").upper()
                and re.sub(r"[^A-Z0-9]", "", str(s.get("ubicacion") or "").upper()) not in ("", "SINDIRECCIONREGISTRADA", "NA", "NONE")
            }
            tiene_direcciones_distintas = len(dirs_fibra) > 1

            elegido_api = srvs_api[0]
            if id_srv_final:
                for s in srvs_api:
                    if str(s.get("id_servicio")) == id_srv_final:
                        elegido_api = s
                        break
            nombre_final = elegido_api.get("nombre") or nombre_final
            id_srv_final = elegido_api.get("id_servicio") or id_srv_final
            tel_final = elegido_api.get("telefono1") or tel_final
            plan_final = elegido_api.get("plan") or plan_final
            ubicacion_final = elegido_api.get("ubicacion") or ubicacion_final
            zona_final = elegido_api.get("zona") or zona_final

        # Si el cliente NO tiene múltiples direcciones físicas distintas, normalizar su HUB al dominante histórico
        if not tiene_direcciones_distintas and len(digits_ced) >= 5:
            prev_hubs = (
                db.query(models.SupportCase.hub)
                .filter(models.SupportCase.cedula.ilike(f"%{digits_ced}%"))
                .all()
            )
            conteo_hub = Counter(
                (ph[0] or "").strip().upper()
                for ph in prev_hubs
                if (ph[0] or "").strip().upper() not in ("", "N/A", "SIN HUB", "NONE")
            )
            if conteo_hub:
                hub_final = conteo_hub.most_common(1)[0][0]

    nuevo_caso = models.SupportCase(
        fecha=fecha_display,
        fecha_iso=fecha_iso,
        numero_caso=siguiente_numero,
        cedula=cedula_clean,
        nombre_cliente=nombre_final,
        id_servicio=id_srv_final,
        telefono=tel_final,
        plan=plan_final,
        analista=analista_nombre,
        reporte=payload.reporte.strip(),
        solucion=payload.solucion.strip(),
        observacion=(payload.observacion or "Rubpi").strip(),
        notas_adicionales=(payload.notas_adicionales or "").strip(),
        hub=hub_final,
        zona=_normalizar_zona_oficial(f"{zona_final} {ubicacion_final}"),
        ubicacion=ubicacion_final,
        router_limitado=bool(payload.router_limitado),
        router_modelo=(payload.router_modelo or "").strip(),
        created_at=now,
    )

    db.add(nuevo_caso)
    db.commit()
    db.refresh(nuevo_caso)

    return {
        "status": "ok",
        "mensaje": f"Caso #{siguiente_numero} registrado exitosamente",
        "caso": nuevo_caso.to_dict(),
    }


@router.post("/api/soporte/casos/masivos")
def crear_casos_afectacion_masivos(
    payload: SupportBulkAfectacionCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    user = security.get_current_user(request, db)

    cantidad = int(payload.cantidad or 0)
    if cantidad < 1 or cantidad > 500:
        raise HTTPException(status_code=400, detail="La cantidad de tickets debe estar entre 1 y 500.")

    hub_clean = (payload.hub or "").strip().upper()
    if not hub_clean:
        raise HTTPException(status_code=400, detail="Debe seleccionar el HUB para la afectación.")

    ubicacion_clean = (payload.ubicacion or "").strip()
    if not ubicacion_clean:
        raise HTTPException(status_code=400, detail="Debe seleccionar o indicar el sub-sector / dirección.")

    zona_clean = _normalizar_zona_oficial(f"{payload.zona or ''} {ubicacion_clean}") or "LOS TEQUES"

    now = datetime.now()
    if payload.fecha_iso and re.match(r"^\d{4}-\d{2}-\d{2}$", payload.fecha_iso.strip()):
        fecha_iso = payload.fecha_iso.strip()
        dt_obj = datetime.strptime(fecha_iso, "%Y-%m-%d")
        fecha_display = f"{dt_obj.day}/{dt_obj.strftime('%m/%Y')}"
    else:
        fecha_iso = now.strftime("%Y-%m-%d")
        fecha_display = f"{now.day}/{now.strftime('%m/%Y')}"

    max_num = (
        db.query(func.max(models.SupportCase.numero_caso))
        .filter(models.SupportCase.fecha_iso == fecha_iso)
        .scalar()
    )
    base_numero = (max_num or 0) + 1
    analista_nombre = (user.full_name or user.username or "Soporte").strip()
    obs_clean = (payload.observacion or "Rubpi").strip()

    nuevos_objetos = []
    for i in range(cantidad):
        num_actual = base_numero + i
        nuevos_objetos.append(
            models.SupportCase(
                fecha=fecha_display,
                fecha_iso=fecha_iso,
                numero_caso=num_actual,
                cedula="S/C - AFECTACIÓN",
                nombre_cliente=f"Afectación Masiva ({ubicacion_clean})",
                id_servicio="",
                telefono="",
                plan="",
                analista=analista_nombre,
                reporte="Afectación",
                solucion="Caso de afectación",
                observacion=obs_clean,
                notas_adicionales="Generado por lote de afectación masiva",
                hub=hub_clean,
                zona=zona_clean,
                ubicacion=ubicacion_clean,
                router_limitado=False,
                router_modelo="",
                created_at=now,
            )
        )

    db.add_all(nuevos_objetos)
    db.commit()

    ultimo_num = base_numero + cantidad - 1
    return {
        "status": "ok",
        "cantidad_creada": cantidad,
        "desde_caso": base_numero,
        "hasta_caso": ultimo_num,
        "zona": zona_clean,
        "ubicacion": ubicacion_clean,
        "mensaje": f"Se crearon {cantidad} tickets de Afectación (#{base_numero} al #{ultimo_num}) en {zona_clean}.",
    }


@router.put("/api/soporte/casos/{case_id}")
def actualizar_caso_soporte(
    case_id: int,
    payload: SupportCaseUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    caso = db.query(models.SupportCase).filter(models.SupportCase.id == case_id).first()
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    for field, val in payload.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(caso, field, val.strip() if isinstance(val, str) else val)

    db.commit()
    db.refresh(caso)
    return {"status": "ok", "caso": caso.to_dict()}


@router.delete("/api/soporte/casos/{case_id}")
def eliminar_caso_soporte(
    case_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    caso = db.query(models.SupportCase).filter(models.SupportCase.id == case_id).first()
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    db.delete(caso)
    db.commit()
    return {"status": "ok", "mensaje": "Caso eliminado correctamente"}


# ============================================================================
# EXPORTACIÓN A CSV / EXCEL IDÉNTICA AL GOOGLE SHEETS
# ============================================================================
@router.get("/api/soporte/exportar")
def exportar_casos_csv(
    request: Request,
    fecha_iso: Optional[str] = Query(None),
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    hub: Optional[str] = Query(None),
    analista: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    query = db.query(models.SupportCase)
    if desde and hasta:
        query = query.filter(models.SupportCase.fecha_iso >= desde, models.SupportCase.fecha_iso <= hasta)
    elif fecha_iso and fecha_iso != "todas":
        query = query.filter(models.SupportCase.fecha_iso == fecha_iso)

    if hub and hub != "TODOS":
        query = query.filter(models.SupportCase.hub == hub)
    if analista and analista != "TODOS":
        query = query.filter(models.SupportCase.analista.ilike(f"%{analista}%"))

    casos = query.order_by(models.SupportCase.fecha_iso.asc(), models.SupportCase.numero_caso.asc()).all()

    output = io.StringIO()
    # BOM UTF-8 para que Microsoft Excel abra acentos y eñes perfectamente
    output.write("\ufeff")
    writer = csv.writer(output)

    # Encabezados idénticos al Google Sheets + columnas extra útiles al final
    writer.writerow(
        [
            "FECHA",
            "N CASO",
            "Cedula",
            "Analista",
            "Reporte",
            "Solucion",
            "Observacion",
            "HUB",
            "ZONA",
            "UBICACION",
            "ROUTER LIMITADO",
            "ROUTER",
            "CLIENTE",
            "ID SERVICIO",
            "HORA",
        ]
    )

    for c in casos:
        writer.writerow(
            [
                c.fecha,
                c.numero_caso,
                c.cedula,
                c.analista,
                c.reporte,
                c.solucion,
                c.observacion or "Rubpi",
                c.hub,
                c.zona or "",
                c.ubicacion or "",
                "TRUE" if c.router_limitado else "FALSE",
                c.router_modelo or "",
                c.nombre_cliente or "",
                c.id_servicio or "",
                c.created_at.strftime("%H:%M:%S") if c.created_at else "",
            ]
        )

    output.seek(0)
    filename_date = fecha_iso or datetime.now().strftime("%Y-%m-%d")
    headers = {
        "Content-Disposition": f'attachment; filename="Incidencias_Soporte_Remoto_{filename_date}.csv"'
    }
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


# ============================================================================
# NODO DE ESTADÍSTICAS PURO — SOPORTE REMOTO
# ============================================================================
@router.get("/soporte/estadisticas", response_class=HTMLResponse)
async def soporte_estadisticas_page(request: Request, db: Session = Depends(get_db)):
    token = security.get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/login")
    try:
        user = security.get_current_user(request, db)
    except Exception:
        return RedirectResponse(url="/login")

    embed = request.query_params.get("embed") == "1"
    return templates.TemplateResponse(
        request,
        "soporte_casos.html",
        {
            "user": user,
            "embed": embed,
            "vista_inicial": "estadisticas",
            "hubs": CATALOGO_HUBS,
            "reportes": CATALOGO_REPORTES,
            "soluciones": CATALOGO_SOLUCIONES,
            "observaciones": CATALOGO_OBSERVACIONES,
            "subsectores": CATALOGO_SUBSECTORES,
        },
    )


@router.get("/api/soporte/estadisticas")
def obtener_estadisticas_soporte(
    request: Request,
    desde: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    hasta: Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD"),
    analista: Optional[str] = Query(None),
    canal: Optional[str] = Query(None),
    hub: Optional[str] = Query(None),
    reporte: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    query = db.query(models.SupportCase)

    if desde:
        query = query.filter(models.SupportCase.fecha_iso >= desde)
    if hasta:
        query = query.filter(models.SupportCase.fecha_iso <= hasta)
    if analista and analista != "TODOS":
        query = query.filter(models.SupportCase.analista == analista)
    if canal and canal != "TODOS":
        query = query.filter(models.SupportCase.observacion == canal)
    if hub and hub != "TODOS":
        query = query.filter(models.SupportCase.hub == hub)
    if reporte and reporte != "TODOS":
        query = query.filter(models.SupportCase.reporte == reporte)

    casos = query.all()
    total = len(casos)

    cnt_reporte = Counter()
    cnt_solucion = Counter()
    cnt_canal = Counter()
    cnt_analista = Counter()
    cnt_hub = Counter()
    cnt_zona = Counter()
    cnt_dia = Counter()
    cnt_zonas_afectacion = Counter()
    escalados_visita = 0
    routers_limitados = 0

    for c in casos:
        rep = (c.reporte or "Sin especificar").strip()
        sol = (c.solucion or "Sin especificar").strip()
        can = (c.observacion or "Rubpi").strip()
        ana = (c.analista or "Sin asignar").strip()
        hb = (c.hub or "N/A").strip().upper()
        zn = _normalizar_zona_oficial(f"{c.zona or ''} {c.ubicacion or ''}") or "SIN ZONA"
        f_iso = (c.fecha_iso or "").strip()

        cnt_reporte[rep] += 1
        cnt_solucion[sol] += 1
        cnt_canal[can] += 1
        cnt_analista[ana] += 1
        cnt_hub[hb] += 1
        cnt_zona[zn] += 1
        if f_iso:
            cnt_dia[f_iso] += 1

        if "afectaci" in rep.lower() and zn != "SIN ZONA":
            cnt_zonas_afectacion[zn] += 1

        if "visita" in sol.lower():
            escalados_visita += 1
        if c.router_limitado:
            routers_limitados += 1

    resueltos_remoto = max(0, total - escalados_visita)
    pct_remoto = round((resueltos_remoto * 100.0 / total), 1) if total > 0 else 0.0
    pct_visita = round((escalados_visita * 100.0 / total), 1) if total > 0 else 0.0

    def _format_counter(counter_obj: Counter, limit_n: int = 25):
        items = []
        for k, v in counter_obj.most_common(limit_n):
            pct = round((v * 100.0 / total), 1) if total > 0 else 0.0
            items.append({"nombre": k, "cantidad": v, "porcentaje": pct})
        return items

    # Lista global de analistas registrados para poblar el selector de filtro
    analistas_db = [
        r[0]
        for r in db.query(models.SupportCase.analista)
        .distinct()
        .order_by(models.SupportCase.analista.asc())
        .all()
        if r[0]
    ]

    serie_diaria = [
        {"fecha_iso": k, "cantidad": cnt_dia[k]}
        for k in sorted(cnt_dia.keys())
    ]

    return {
        "total_casos": total,
        "resueltos_remoto": resueltos_remoto,
        "porcentaje_remoto": pct_remoto,
        "escalados_visita": escalados_visita,
        "porcentaje_visita": pct_visita,
        "routers_limitados": routers_limitados,
        "por_reporte": _format_counter(cnt_reporte, 50),
        "por_solucion": _format_counter(cnt_solucion, 25),
        "por_canal": _format_counter(cnt_canal, 10),
        "por_analista": _format_counter(cnt_analista, 30),
        "por_hub": _format_counter(cnt_hub, 15),
        "por_zona": _format_counter(cnt_zona, 20),
        "zonas_afectacion": [k for k, _ in cnt_zonas_afectacion.most_common(15)],
        "por_dia": serie_diaria,
        "analistas_disponibles": analistas_db,
    }


# ============================================================================
# REPORTE DE COINCIDENCIA / REINCIDENCIA Y ALARMAS POR CLIENTE (SEMANAL Y MENSUAL)
# ============================================================================
@router.get("/api/soporte/reincidencias")
def obtener_reincidencias_clientes(
    request: Request,
    modo: str = Query("mes", description="semana | mes | todo"),
    mes: Optional[str] = Query(None, description="YYYY-MM para vista mensual"),
    fecha_ref: Optional[str] = Query(None, description="YYYY-MM-DD para vista semanal (últimos 7 días)"),
    min_casos: int = Query(2, ge=1, le=50),
    hub: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Buscar cliente por Cédula o Nombre"),
    limit: int = Query(150, ge=10, le=1000),
    db: Session = Depends(get_db),
):
    token = security.get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    # Determinar la fecha más reciente en la BD para usar como referencia por defecto
    max_fecha_db = (
        db.query(func.max(models.SupportCase.fecha_iso))
        .filter(models.SupportCase.fecha_iso.like("2026-%"))
        .scalar()
    ) or datetime.now().strftime("%Y-%m-%d")

    ref_date_str = (fecha_ref or "").strip() or max_fecha_db
    try:
        ref_dt = datetime.strptime(ref_date_str, "%Y-%m-%d")
    except ValueError:
        ref_dt = datetime.now()
        ref_date_str = ref_dt.strftime("%Y-%m-%d")

    semana_inicio_str = (ref_dt - timedelta(days=6)).strftime("%Y-%m-%d")
    mes_eval = (mes or "").strip() or ref_date_str[:7]

    # Consultar todos los casos con cédula válida
    query = db.query(models.SupportCase)
    if hub and hub != "TODOS":
        query = query.filter(models.SupportCase.hub == hub.strip().upper())

    q_clean = (q or "").strip()
    q_digits = re.sub(r"[^0-9]", "", q_clean)
    if q_clean:
        if q_digits and len(q_digits) >= 4:
            query = query.filter(
                or_(
                    models.SupportCase.cedula.ilike(f"%{q_digits}%"),
                    models.SupportCase.nombre_cliente.ilike(f"%{q_clean}%"),
                )
            )
        else:
            query = query.filter(
                or_(
                    models.SupportCase.cedula.ilike(f"%{q_clean}%"),
                    models.SupportCase.nombre_cliente.ilike(f"%{q_clean}%"),
                    models.SupportCase.ubicacion.ilike(f"%{q_clean}%"),
                )
            )

    todos_casos = query.order_by(models.SupportCase.fecha_iso.asc(), models.SupportCase.id.asc()).all()

    clientes_map = {}
    meses_disponibles = set()

    for c in todos_casos:
        ced_raw = (c.cedula or "").strip().upper()
        digits = re.sub(r"[^0-9]", "", ced_raw)
        if not digits or len(digits) < 5:
            continue

        f_iso = (c.fecha_iso or "").strip()
        if len(f_iso) >= 7:
            meses_disponibles.add(f_iso[:7])

        entry = clientes_map.get(digits)
        if not entry:
            entry = {
                "cedula": digits,
                "nombre_cliente": c.nombre_cliente or "Cliente Registrado",
                "id_servicio": c.id_servicio or "",
                "telefono": c.telefono or "",
                "hub": c.hub or "N/A",
                "zona": c.zona or "SIN ZONA",
                "ubicacion": c.ubicacion or "",
                "casos_semana": 0,
                "casos_mes": 0,
                "casos_periodo": 0,
                "casos_historial": 0,
                "visitas_periodo": 0,
                "router_limitado": False,
                "fallas_counter": Counter(),
                "soluciones_counter": Counter(),
                "fallas_globales": Counter(),
                "soluciones_globales": Counter(),
                "fechas_periodo": [],
                "por_mes": Counter(),
                "por_semana": Counter(),
                "ultimos_casos": [],
                "todos_casos_cliente": [],
            }
            clientes_map[digits] = entry

        # Actualizar metadatos más completos
        if c.nombre_cliente:
            entry["nombre_cliente"] = c.nombre_cliente
        if c.id_servicio:
            entry["id_servicio"] = c.id_servicio
        if c.telefono:
            entry["telefono"] = c.telefono
        if c.hub and c.hub != "N/A":
            entry["hub"] = c.hub
        if c.zona and c.zona != "SIN ZONA":
            entry["zona"] = c.zona
        if c.ubicacion and c.ubicacion != "N/A":
            entry["ubicacion"] = c.ubicacion
        if c.router_limitado:
            entry["router_limitado"] = True

        entry["casos_historial"] += 1
        rep_all = (c.reporte or "Sin especificar").strip()
        sol_all = (c.solucion or "Sin especificar").strip()
        entry["fallas_globales"][rep_all] += 1
        entry["soluciones_globales"][sol_all] += 1
        entry["todos_casos_cliente"].append(
            {
                "fecha": c.fecha,
                "fecha_iso": c.fecha_iso,
                "numero_caso": c.numero_caso,
                "reporte": rep_all,
                "solucion": sol_all,
                "analista": c.analista,
                "observacion": c.observacion or "Rubpi",
                "hub": c.hub,
                "router_limitado": bool(c.router_limitado),
            }
        )

        if len(f_iso) == 10:
            ym = f_iso[:7]
            entry["por_mes"][ym] += 1
            try:
                dt_c = datetime.strptime(f_iso, "%Y-%m-%d")
                iso_yr, iso_wk, _ = dt_c.isocalendar()
                lunes_sem = dt_c - timedelta(days=dt_c.weekday())
                dom_sem = lunes_sem + timedelta(days=6)
                wk_label = f"Sem {iso_wk:02d} ({lunes_sem.strftime('%d/%m')} - {dom_sem.strftime('%d/%m')})"
                entry["por_semana"][wk_label] += 1
            except ValueError:
                pass

        en_semana = semana_inicio_str <= f_iso <= ref_date_str
        en_mes = f_iso.startswith(mes_eval)

        if en_semana:
            entry["casos_semana"] += 1
        if en_mes:
            entry["casos_mes"] += 1

        incluir_en_periodo = (
            (modo == "semana" and en_semana)
            or (modo == "mes" and en_mes)
            or (modo == "todo")
        )
        if incluir_en_periodo:
            entry["casos_periodo"] += 1
            rep_clean = (c.reporte or "Sin especificar").strip()
            sol_clean = (c.solucion or "Sin especificar").strip()
            entry["fallas_counter"][rep_clean] += 1
            entry["soluciones_counter"][sol_clean] += 1
            if "visita" in sol_clean.lower():
                entry["visitas_periodo"] += 1
            if c.fecha:
                entry["fechas_periodo"].append(c.fecha)
            entry["ultimos_casos"].append(
                {
                    "fecha": c.fecha,
                    "fecha_iso": c.fecha_iso,
                    "numero_caso": c.numero_caso,
                    "reporte": rep_clean,
                    "solucion": sol_clean,
                    "analista": c.analista,
                    "observacion": c.observacion or "Rubpi",
                    "hub": c.hub,
                    "router_limitado": bool(c.router_limitado),
                }
            )

    resultados = []
    kpi_criticas = 0
    kpi_altas = 0
    kpi_observacion = 0

    for digits, item in clientes_map.items():
        # Si hay búsqueda específica por cliente (`q`), mostrar aunque tenga 1 caso; si no, exigir `min_casos`
        umbral_efectivo = 1 if q_clean else min_casos
        if item["casos_periodo"] < umbral_efectivo:
            continue

        c_sem = item["casos_semana"]
        c_mes = item["casos_mes"]
        c_per = item["casos_periodo"]

        # Clasificación de Alarma Semanal y Mensual
        if c_sem >= 3 or c_mes >= 5 or (modo == "semana" and c_per >= 3) or (modo == "mes" and c_per >= 5):
            nivel = "CRITICA"
            motivo_alarma = f"{c_sem} rep. en 7 días / {c_mes} en el mes"
            kpi_criticas += 1
        elif c_sem == 2 or c_mes >= 3 or (modo == "semana" and c_per == 2) or (modo == "mes" and c_per >= 3):
            nivel = "ALTA"
            motivo_alarma = f"{c_sem} rep. en 7 días / {c_mes} en el mes"
            kpi_altas += 1
        else:
            nivel = "OBSERVACION"
            motivo_alarma = f"{c_per} reportes en el periodo"
            kpi_observacion += 1

        falla_top = "—"
        if item["fallas_counter"]:
            top_k, top_v = item["fallas_counter"].most_common(1)[0]
            falla_top = f"{top_k} ({top_v})"

        desglose_meses = [
            {"mes": k, "cantidad": item["por_mes"][k]}
            for k in sorted(item["por_mes"].keys(), reverse=True)[:12]
        ]
        desglose_semanas = [
            {"semana": k, "cantidad": v}
            for k, v in item["por_semana"].most_common(8)
        ]

        resumen_fallas = [
            {"nombre": k, "cantidad": v}
            for k, v in item["fallas_counter"].most_common(12)
        ]
        resumen_soluciones = [
            {"nombre": k, "cantidad": v}
            for k, v in item["soluciones_counter"].most_common(12)
        ]

        resultados.append(
            {
                "cedula": item["cedula"],
                "nombre_cliente": item["nombre_cliente"],
                "id_servicio": item["id_servicio"],
                "telefono": item["telefono"],
                "hub": item["hub"],
                "zona": item["zona"],
                "ubicacion": item["ubicacion"],
                "casos_semana": c_sem,
                "casos_mes": c_mes,
                "casos_periodo": c_per,
                "casos_historial": item["casos_historial"],
                "visitas_periodo": item["visitas_periodo"],
                "router_limitado": item["router_limitado"],
                "falla_frecuente": falla_top,
                "fechas_periodo": item["fechas_periodo"][-8:],
                "ultima_fecha": item["fechas_periodo"][-1] if item["fechas_periodo"] else "—",
                "nivel_alarma": nivel,
                "motivo_alarma": motivo_alarma,
                "desglose_meses": desglose_meses,
                "desglose_semanas": desglose_semanas,
                "resumen_fallas": resumen_fallas,
                "resumen_soluciones": resumen_soluciones,
                "ultimos_casos": list(reversed(item["ultimos_casos"])),
            }
        )

    # Ordenar por prioridad de alarma y mayor cantidad de coincidencias en el periodo
    orden_prioridad = {"CRITICA": 3, "ALTA": 2, "OBSERVACION": 1}
    resultados.sort(
        key=lambda x: (
            orden_prioridad.get(x["nivel_alarma"], 0),
            x["casos_periodo"],
            x["casos_semana"],
            x["casos_mes"],
            x["casos_historial"],
        ),
        reverse=True,
    )

    return {
        "modo": modo,
        "mes_evaluado": mes_eval,
        "fecha_ref": ref_date_str,
        "semana_inicio": semana_inicio_str,
        "min_casos": min_casos,
        "total_clientes_alarma": len(resultados),
        "kpi_criticas": kpi_criticas,
        "kpi_altas": kpi_altas,
        "kpi_observacion": kpi_observacion,
        "meses_disponibles": sorted(list(meses_disponibles), reverse=True),
        "clientes": resultados[:limit],
    }


