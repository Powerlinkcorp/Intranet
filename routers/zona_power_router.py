import os
import re
import csv
import io
import json
import subprocess
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse, PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, SessionLocal
import models
import security
import permissions_manager
from email_util import send_email_message

router = APIRouter(tags=["Zona Power"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "static/uploads")

# Caché en memoria de clientes (cédula -> datos) para respuestas instantáneas (<1ms)
_clients_cache = {}
_cache_loaded = False

DEFAULTS_CONFIG = {
    "tiempo_cortesia_min": "30",
    "tiempo_inactividad_min": "30",
    "limite_dispositivos": "2",
    "whatsapp_url": "https://wa.link/xow3um",
    "telefono_soporte": "+582127203500",
    "email_notificaciones": "bcarrero@powerlink.com.ve",
    "ssid_nombre": "Zona Power",
    "portal_activo": "true",
    "limite_bajada_mbps": "5",
    "limite_subida_mbps": "3",
    "modo_qos": "dinamico",
    "capacidad_estacion_mbps": "1000",
    "piso_minimo_cliente_mbps": "5",
    "dias_reintento_cortesia": "7",
    "dias_recordar_mac_abonado": "7",
    "nombre_estacion": "CC La Colina",
    "url_redireccion_destino": "https://powerlink.com.ve",
    "horario_habilitado": "false",
    "horario_inicio": "06:00",
    "horario_fin": "22:00",
    "banner_activo": "false",
    "banner_tipo": "promocion",
    "banner_texto": "¡Conéctate con la fibra óptica de Power Link! Conoce nuestros planes residenciales y corporativos.",
    "banner_url": "https://powerlink.com.ve",
    "gateway_ip": "192.168.110.1"
}

# ==========================================
# DICCIONARIO GEOGRÁFICO DE VENEZUELA
# (24 Entidades Federales y todos sus Municipios)
# ==========================================
MUNICIPIOS_VENEZUELA = {
    "Amazonas": ["Alto Orinoco", "Atabapo", "Atures (Puerto Ayacucho)", "Autana", "Manapiare", "Maroa", "Río Negro"],
    "Anzoátegui": ["Anaco", "Aragua", "Diego Bautista Urbaneja (Lechería)", "Fernando Peñalver (Puerto Píritu)", "Francisco de Miranda", "Francisco del Carmen Carvajal", "Guanta", "Independencia", "José Gregorio Monagas", "Juan Antonio Sotillo (Puerto La Cruz)", "Juan Manuel Cajigal", "Libertad", "Manuel Ezequiel Bruzual", "Pedro María Freites (Cantaura)", "Píritu", "San José de Guanipa", "San Juan de Capistrano", "Santa Ana", "Simón Bolívar (Barcelona)", "Simón Rodríguez (El Tigre)", "Sir Arthur McGregor"],
    "Apure": ["Achaguas", "Biruaca", "Muñoz", "Páez (Guasdualito)", "Pedro Camejo", "Rómulo Gallegos", "San Fernando"],
    "Aragua": ["Bolívar (San Mateo)", "Camatagua", "Francisco Linares Alcántara (Santa Rita)", "Girardot (Maracay)", "José Ángel Lamas (Santa Cruz)", "José Félix Ribas (La Victoria)", "José Rafael Revenga (El Consejo)", "Libertador (Palo Negro)", "Mario Briceño Iragorry (El Limón)", "Ocumare de la Costa de Oro", "San Casimiro", "San Sebastián", "Santiago Mariño (Turmero)", "Santos Michelena (Las Tejerías)", "Sucre (Cagua)", "Tovar (Colonia Tovar)", "Urdaneta (Barbacoas)", "Zamora (Villa de Cura)"],
    "Barinas": ["Alberto Arvelo Torrealba", "Andrés Eloy Blanco", "Antonio José de Sucre", "Arismendi", "Barinas", "Bolívar", "Cruz Paredes", "Ezequiel Zamora", "Obispos", "Pedraza", "Rojas", "Sosa"],
    "Bolívar": ["Angostura (Raúl Leoni)", "Angostura del Orinoco (Ciudad Bolívar)", "Caroní (Ciudad Guayana)", "Cedeño", "Chien (Padre Pedro Chien)", "El Callao", "Gran Sabana (Santa Elena de Uairén)", "Piar (Upata)", "Roscio (Guasipati)", "Sifontes (Tumeremo)", "Sucre"],
    "Carabobo": ["Bejuma", "Carlos Arvelo (Güigüe)", "Diego Ibarra (Mariara)", "Guacara", "Juan José Mora (Morón)", "Libertador (Tocuyito)", "Los Guayos", "Miranda", "Montalbán", "Naguanagua", "Puerto Cabello", "San Diego", "San Joaquín", "Valencia"],
    "Cojedes": ["Anzoátegui", "Ezequiel Zamora (San Carlos)", "Girardot", "Lima Blanco", "Pao de San Juan Bautista", "Ricaurte", "Rómulo Gallegos", "Tinaco", "Tinaquillo"],
    "Delta Amacuro": ["Antonio Díaz", "Casacoima", "Pedernales", "Tucupita"],
    "Distrito Capital": ["Libertador (Caracas)"],
    "Falcón": ["Acosta", "Bolívar", "Buchivacoa", "Cacique Manaure", "Carirubana (Punto Fijo)", "Colina", "Dabajuro", "Democracia", "Falcón", "Federación", "Jacura", "Los Taques", "Mauroa", "Miranda (Coro)", "Monseñor Iturriza", "Palmasola", "Petit", "Píritu", "San Francisco", "Silva (Tucacas)", "Sucre", "Tocópero", "Unión", "Urumaco", "Zamora"],
    "Guárico": ["Camaguán", "Chaguaramas", "El Socorro", "Francisco de Miranda (Calabozo)", "José Félix Ribas", "José Tadeo Monagas (Altagracia de Orituco)", "Juan Germán Roscio (San Juan de los Morros)", "Julián Mellado", "Las Mercedes", "Leonardo Infante (Valle de la Pascua)", "Pedro Zaraza", "Ortiz", "San Gerónimo de Guayabal", "San José de Guaribe", "Santa María de Ipire"],
    "La Guaira": ["Vargas (La Guaira / Maiquetía / Catia La Mar)"],
    "Lara": ["Andrés Eloy Blanco", "Crespo", "Iribarren (Barquisimeto)", "Jiménez (Quíbor)", "Morán (El Tocuyo)", "Palavecino (Cabudare)", "Simón Planas", "Torres (Carora)", "Urdaneta"],
    "Mérida": ["Alberto Adriani (El Vigía)", "Andrés Bello", "Antonio Pinto Salinas", "Aricagua", "Arzobispo Chacón", "Campo Elías (Ejido)", "Caracciolo Parra Olmedo", "Cardenal Quintero", "Guaraque", "Julio César Salas", "Justo Briceño", "Libertador (Mérida)", "Miranda", "Obispo Ramos de Lora", "Padre Noguera", "Pueblo Llano", "Rangel (Mucuchíes)", "Rivas Dávila", "Santos Marquina", "Sucre (Lagunillas)", "Tovar", "Tulio Febres Cordero", "Zea"],
    "Miranda": ["Acevedo (Caucagua)", "Andrés Bello (San José de Barlovento)", "Baruta", "Brión (Higuerote)", "Buroz (Mamporal)", "Carrizal", "Chacao", "Cristóbal Rojas (Charallave)", "El Hatillo", "Guaicaipuro (Los Teques)", "Independencia (Santa Teresa del Tuy)", "Lander (Ocumare del Tuy)", "Los Salias (San Antonio de Los Altos)", "Páez (Río Chico)", "Paz Castillo (Santa Lucía)", "Pedro Gual (Cúpira)", "Plaza (Guarenas)", "Simón Bolívar (San Francisco de Yare)", "Sucre (Petare)", "Urdaneta (Cúa)", "Zamora (Guatire)"],
    "Monagas": ["Acosta", "Aguasay", "Bolívar", "Caripe", "Cedeño", "Ezequiel Zamora (Punta de Mata)", "Libertador", "Maturín", "Piar", "Punceres", "Santa Bárbara", "Sotillo", "Uracoa"],
    "Nueva Esparta": ["Antolín del Campo", "Arismendi (La Asunción)", "Díaz", "García", "Gómez", "Maneiro (Pampatar)", "Marcano (Juan Griego)", "Mariño (Porlamar)", "Península de Macanao", "Tubores", "Villalba (Isla de Coche)"],
    "Portuguesa": ["Agua Blanca", "Araure", "Esteller", "Guanare", "Guanarito", "Monseñor José Vicente de Unda", "Ospino", "Páez (Acarigua)", "Papelón", "San Genaro de Boconoíto", "San Rafael de Onoto", "Santa Rosalía", "Sucre (Biscucuy)", "Turén"],
    "Sucre": ["Andrés Eloy Blanco", "Andrés Mata", "Arismendi (Carúpano)", "Benítez", "Bermúdez", "Bolívar", "Cajigal", "Cruz Salmerón Acosta", "Libertador", "Mariño", "Mejía", "Montes (Cumanacoa)", "Ribero (Cariaco)", "Sucre (Cumaná)", "Valdez (Güiria)"],
    "Táchira": ["Andrés Bello", "Antonio Rómulo Costa", "Ayacucho (Colón)", "Bolívar (San Antonio del Táchira)", "Cárdenas (Táriba)", "Córdoba", "Fernández Feo", "Francisco de Miranda", "García de Hevia (La Fría)", "Guásimos", "Independencia (Capacho Nuevo)", "Jáuregui (La Grita)", "José María Vargas", "Junín (Rubio)", "Libertad (Capacho Viejo)", "Libertador", "Lobatera", "Michelena", "Panamericano", "Pedro María Ureña", "Rafael Urdaneta", "Samuel Darío Maldonado", "San Cristóbal", "San Judas Tadeo", "Seboruco", "Simón Rodríguez", "Sucre", "Torbes", "Uribante"],
    "Trujillo": ["Andrés Bello", "Boconó", "Bolívar", "Candelaria", "Carache", "Carvajal", "Escuque", "José Felipe Márquez Cañizalez", "Juan Vicente Campos Elías", "La Ceiba", "Miranda", "Monte Carmelo", "Motatán", "Pampán", "Pampanito", "Rafael Rangel", "Sucre", "Trujillo", "Urdaneta", "Valera"],
    "Yaracuy": ["Aristides Bastidas", "Bolívar", "Bruzual (Chivacoa)", "Cocorote", "Independencia", "José Antonio Páez", "La Trinidad", "Manuel Monge", "Nirgua", "Peña (Yaritagua)", "San Felipe", "Sucre", "Urachiche", "Veroes"],
    "Zulia": ["Almirante Padilla", "Baralt", "Cabimas", "Catatumbo", "Colón (San Carlos del Zulia)", "Francisco Javier Pulgar", "Jesús Enrique Lossada", "Jesús María Semprún", "La Cañada de Urdaneta", "Lagunillas (Ciudad Ojeda)", "Machiques de Perijá", "Mara", "Maracaibo", "Miranda", "Rosario de Perijá", "San Francisco", "Santa Rita", "Simón Bolívar", "Sucre", "Valmore Rodríguez"]
}


def _get_setting(db: Session, key: str, default: str = None) -> str:
    """Obtiene un parámetro de configuración desde la base de datos con fallback a default."""
    cfg = db.query(models.ConfigZonaPower).filter(models.ConfigZonaPower.clave == key).first()
    if cfg and cfg.valor is not None:
        return cfg.valor
    return DEFAULTS_CONFIG.get(key, default or "")


def _set_setting(db: Session, key: str, value: str, descripcion: str = ""):
    """Guarda o actualiza un parámetro de configuración."""
    cfg = db.query(models.ConfigZonaPower).filter(models.ConfigZonaPower.clave == key).first()
    if cfg:
        cfg.valor = value
        if descripcion:
            cfg.descripcion = descripcion
    else:
        cfg = models.ConfigZonaPower(clave=key, valor=value, descripcion=descripcion)
        db.add(cfg)
    db.commit()


def _normalize_cedula(cedula: str) -> str:
    """Extrae solo dígitos de la cédula para búsqueda confiable."""
    if not cedula:
        return ""
    clean = re.sub(r"[^0-9]", "", str(cedula))
    return clean.lstrip("0") or "0"


def _verificar_horario_operativo(db: Session) -> tuple:
    """
    Verifica si el servicio se encuentra dentro del horario operativo permitido.
    Retorna (esta_abierto: bool, mensaje: str).
    Usa la hora local de Venezuela (UTC-4).
    """
    habilitado = _get_setting(db, "horario_habilitado", "false").lower() == "true"
    if not habilitado:
        return True, ""

    hora_ini_str = _get_setting(db, "horario_inicio", "06:00")
    hora_fin_str = _get_setting(db, "horario_fin", "22:00")

    try:
        # Hora local Venezuela (UTC-4)
        ahora_ve = datetime.utcnow() - timedelta(hours=4)
        hora_actual = ahora_ve.time()

        h_ini = datetime.strptime(hora_ini_str.strip(), "%H:%M").time()
        h_fin = datetime.strptime(hora_fin_str.strip(), "%H:%M").time()

        if h_ini <= h_fin:
            en_horario = h_ini <= hora_actual <= h_fin
        else:
            en_horario = hora_actual >= h_ini or hora_actual <= h_fin

        if not en_horario:
            return False, f"Servicio fuera de horario operativo. Zona Power está disponible de {hora_ini_str} a {hora_fin_str}."
        return True, ""
    except Exception as e:
        print(f"[ZONA POWER] Error evaluando horario operativo: {e}")
        return True, ""


def _ensure_clients_cache_loaded():
    """Carga los clientes del último snapshot a memoria si aún no están indexados (optimizado)."""
    global _clients_cache, _cache_loaded
    if _cache_loaded:
        return

    snapshot_path = os.path.join(UPLOAD_DIR, "last_snapshot.json")
    if not os.path.exists(snapshot_path):
        _cache_loaded = True
        return

    try:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            clients_list = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for c in clients_list:
                ced = _normalize_cedula(c.get("doc") or c.get("cedula") or c.get("identification") or c.get("dni") or "")
                if ced:
                    email_raw = (c.get("email") or c.get("mail") or "").strip().lower()
                    if ced not in _clients_cache:
                        _clients_cache[ced] = {
                            "name": c.get("name") or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or "Abonado Power Link",
                            "status": str(c.get("service_status") or c.get("status") or "ACTIVO").upper(),
                            "email": email_raw,
                            "emails": {email_raw} if email_raw else set(),
                            "phone": c.get("phone", ""),
                            "address": c.get("address", ""),
                            "service": c.get("service_type") or c.get("service", "Fibra Óptica")
                        }
                    else:
                        if email_raw:
                            _clients_cache[ced]["emails"].add(email_raw)
                            if not _clients_cache[ced]["email"]:
                                _clients_cache[ced]["email"] = email_raw
        _cache_loaded = True
        print(f"[ZONA POWER] Caché de clientes cargada exitosamente: {len(_clients_cache)} registros en memoria")
    except Exception as e:
        print(f"[ZONA POWER] Error cargando caché de clientes: {e}")
        _cache_loaded = True


def _ruijie_authorize_mac(mac: str, gw_ip: str = "192.168.110.1"):
    """Autoriza la MAC del cliente directamente en el gateway Ruijie vía direct_mac."""
    if not mac or mac in ("00:00:00:00:00:00", ""):
        return
    try:
        script_path = r"C:\Users\bcarrero\Documents\Zona Power\authorize_mac.js"
        if os.path.exists(script_path):
            env = {**os.environ, "RUIJIE_GATEWAY_IP": gw_ip}
            subprocess.run(["node", script_path, mac], capture_output=True, timeout=5, env=env)
            print(f"[ZONA POWER] MAC {mac} autorizada exitosamente en Ruijie Gateway ({gw_ip}).")
    except Exception as e:
        print(f"[ZONA POWER] Error autorizando MAC {mac} en Ruijie: {e}")


def _ruijie_deauthorize_mac(mac: str, gw_ip: str = "192.168.110.1"):
    """Revoca la autorización de la MAC en el gateway Ruijie."""
    if not mac or mac in ("00:00:00:00:00:00", ""):
        return
    try:
        script_path = r"C:\Users\bcarrero\Documents\Zona Power\deauthorize_mac.js"
        if os.path.exists(script_path):
            env = {**os.environ, "RUIJIE_GATEWAY_IP": gw_ip}
            subprocess.run(["node", script_path, mac], capture_output=True, timeout=5, env=env)
            print(f"[ZONA POWER] MAC {mac} revocada en Ruijie Gateway ({gw_ip}).")
    except Exception as e:
        print(f"[ZONA POWER] Error revocando MAC {mac} en Ruijie: {e}")


def _ruijie_apply_traffic_policy(mode: str = "dinamico", total_mbps: str = "1000", floor_mbps: str = "5", down_mbps: str = "5", up_mbps: str = "3", gw_ip: str = "192.168.110.1"):
    """Aplica la política de tráfico (reparto dinámico equitativo o límite fijo) al router y antenas Ruijie."""
    try:
        script_path = r"C:\Users\bcarrero\Documents\Zona Power\set_traffic_policy.js"
        if os.path.exists(script_path):
            env = {**os.environ, "RUIJIE_GATEWAY_IP": gw_ip}
            subprocess.run(["node", script_path, str(mode), str(total_mbps), str(floor_mbps), str(down_mbps), str(up_mbps)], capture_output=True, timeout=10, env=env)
            print(f"[ZONA POWER] Política de tráfico Ruijie aplicada en {gw_ip}: Modo={mode}, Total={total_mbps}M, Piso={floor_mbps}M, FijoDown={down_mbps}M, FijoUp={up_mbps}M")
    except Exception as e:
        print(f"[ZONA POWER] Error aplicando política de tráfico en Ruijie: {e}")


def _ruijie_apply_bandwidth_limit(down_mbps: str, up_mbps: str):
    """Compatibilidad: Llama a la política de tráfico en modo fijo."""
    _ruijie_apply_traffic_policy("fijo", "1000", "5", down_mbps, up_mbps)


def _limpiar_sesiones_inactivas(db: Session):
    """Marca como inactivas las sesiones que han superado el tiempo de inactividad y revoca en Ruijie."""
    try:
        t_inact = int(_get_setting(db, "tiempo_inactividad_min", "30"))
        limite = datetime.utcnow() - timedelta(minutes=t_inact)
        expiradas = db.query(models.SesionZonaPower).filter(
            models.SesionZonaPower.is_active == True,
            models.SesionZonaPower.last_seen < limite
        ).all()
        for s in expiradas:
            s.is_active = False
            _ruijie_deauthorize_mac(s.mac_address)
        db.commit()
    except Exception as e:
        print(f"[ZONA POWER] Error en barrido de inactividad: {e}")


# ==========================================
# RUTAS DEL PORTAL CAUTIVO
# ==========================================

@router.get("/zonapower/portal/ping", response_class=PlainTextResponse)
@router.get("/zonapower/portal/ping/", response_class=PlainTextResponse)
@router.get("/ping", response_class=PlainTextResponse)
@router.get("/ping/", response_class=PlainTextResponse)
def wifidog_ping(request: Request):
    return PlainTextResponse("Pong\n")

@router.get("/zonapower/portal/auth", response_class=PlainTextResponse)
@router.get("/zonapower/portal/auth/", response_class=PlainTextResponse)
@router.get("/auth", response_class=PlainTextResponse)
@router.get("/auth/", response_class=PlainTextResponse)
def wifidog_auth(request: Request):
    return PlainTextResponse("Auth: 1\n")


# Sondas de detección de conectividad de sistemas operativos móviles (CNA)
@router.get("/generate_204")
@router.get("/gen_204")
def mobile_generate_204():
    """Responde con HTTP 204 No Content para indicar conectividad exitosa a dispositivos Android."""
    from fastapi import Response
    return Response(status_code=204)


@router.get("/hotspot-detect.html", response_class=HTMLResponse)
@router.get("/canonical.html", response_class=HTMLResponse)
def mobile_apple_detect():
    """Responde con Success para indicar conectividad exitosa a dispositivos Apple (iOS/macOS)."""
    return "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>"


@router.get("/ncsi.txt", response_class=PlainTextResponse)
@router.get("/connecttest.txt", response_class=PlainTextResponse)
def mobile_windows_detect():
    """Responde con señal de conectividad para Windows."""
    return "Microsoft Connect Test"

@router.get("/zonapower/portal", response_class=HTMLResponse)
def portal_cautivo_page(request: Request, db: Session = Depends(get_db)):
    """Página de bienvenida responsiva y 100% autocontenida del Portal Cautivo Zona Power."""
    mac = request.query_params.get("mac", request.query_params.get("client_mac", request.query_params.get("usermac", "00:00:00:00:00:00")))
    ip = request.query_params.get("ip", request.query_params.get("userip", request.client.host if request.client else "10.90.0.51"))
    gw_address = request.query_params.get("gw_address", request.query_params.get("nas_ip", "192.168.110.1"))
    target_url = request.query_params.get("target_url", request.query_params.get("url", "https://google.com"))

    tiempo_cortesia = _get_setting(db, "tiempo_cortesia_min", "30")
    tiempo_inactividad = _get_setting(db, "tiempo_inactividad_min", "30")
    limite_disp = _get_setting(db, "limite_dispositivos", "2")
    wa_url = _get_setting(db, "whatsapp_url", "https://wa.link/xow3um")
    tlf_soporte = _get_setting(db, "telefono_soporte", "+582127203500")
    dias_reintento = _get_setting(db, "dias_reintento_cortesia", "7")
    dias_abonado = _get_setting(db, "dias_recordar_mac_abonado", "7")
    nombre_estacion = _get_setting(db, "nombre_estacion", "CC La Colina")
    url_destino = _get_setting(db, "url_redireccion_destino", "https://powerlink.com.ve")
    horario_hab = _get_setting(db, "horario_habilitado", "false").lower() == "true"
    horario_ini = _get_setting(db, "horario_inicio", "06:00")
    horario_fin = _get_setting(db, "horario_fin", "22:00")
    banner_activo = _get_setting(db, "banner_activo", "false").lower() == "true"
    banner_tipo = _get_setting(db, "banner_tipo", "promocion")
    banner_texto = _get_setting(db, "banner_texto", "¡Conéctate con la fibra óptica de Power Link!")
    banner_url = _get_setting(db, "banner_url", "https://powerlink.com.ve")

    esta_abierto, msg_horario = _verificar_horario_operativo(db)

    # Si target_url es default google.com, redirigir a url_destino corporativo
    if not target_url or target_url == "https://google.com":
        target_url = url_destino

    banner_html = ""
    if banner_activo and esta_abierto:
        if banner_tipo == "alerta":
            b_bg = "radial-gradient(ellipse at top, rgba(249, 115, 22, 0.22) 0%, rgba(15, 23, 42, 0.95) 100%)"
            b_border = "rgba(249, 115, 22, 0.45)"
            b_icon = "⚠️"
            b_title = "Aviso Operativo"
            b_color = "#FDBA74"
        elif banner_tipo == "info":
            b_bg = "radial-gradient(ellipse at top, rgba(59, 130, 246, 0.22) 0%, rgba(15, 23, 42, 0.95) 100%)"
            b_border = "rgba(59, 130, 246, 0.45)"
            b_icon = "ℹ️"
            b_title = "Información Oficial"
            b_color = "#93C5FD"
        else:
            b_bg = "radial-gradient(ellipse at top, rgba(234, 179, 8, 0.22) 0%, rgba(15, 23, 42, 0.95) 100%)"
            b_border = "rgba(234, 179, 8, 0.45)"
            b_icon = "🚀"
            b_title = "¡Novedad Power Link!"
            b_color = "#FDE047"

        b_btn = f'<a href="{banner_url}" target="_blank" style="display: inline-flex; align-items: center; gap: 4px; margin-top: 6px; padding: 4px 10px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 6px; color: #FFFFFF; font-size: 11px; font-weight: 700; text-decoration: none;">Más Información &rarr;</a>' if banner_url else ""

        banner_html = f'''
        <div style="width: 100%; max-width: 440px; margin: 0 auto 12px; padding: 10px 14px; background: {b_bg}; border: 1px solid {b_border}; border-radius: 14px; text-align: left; box-shadow: 0 4px 16px rgba(0,0,0,0.4);">
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 3px;">
                <span style="font-size: 14px;">{b_icon}</span>
                <strong style="color: {b_color}; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;">{b_title}</strong>
            </div>
            <p style="font-size: 11px; color: #E2E8F0; line-height: 1.4; margin: 0;">{banner_texto}</p>
            {b_btn}
        </div>'''

    estados_json = json.dumps(MUNICIPIOS_VENEZUELA, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Zona Power | Power Link</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        html, body, button, input, select, textarea, span, p, h1, h2, h3, strong, a {{
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        html, body {{
            min-height: 100vh;
            background-color: #09090B;
            background-image: radial-gradient(circle at 50% 0%, rgba(212, 175, 55, 0.12) 0%, #09090B 75%);
            color: #F8FAFC;
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
            font-size: 14px;
            line-height: 1.5;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: space-between;
            padding: 16px 12px;
        }}
        .hidden {{
            display: none !important;
        }}
        .portal-header {{
            width: 100%;
            max-width: 440px;
            text-align: center;
            padding: 6px 0 10px;
        }}
        .logo-wrap {{
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 8px;
        }}
        .logo-img {{
            max-height: 48px;
            max-width: 175px;
            width: auto;
            height: auto;
            object-fit: contain;
            display: block;
            margin: 0 auto;
            filter: drop-shadow(0 4px 10px rgba(0, 0, 0, 0.5));
        }}
        .badge-wifi {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 14px;
            border-radius: 999px;
            background: rgba(212, 175, 55, 0.12);
            border: 1px solid rgba(212, 175, 55, 0.35);
            color: #D4AF37;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }}
        .btn-browser-pill {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 14px;
            border-radius: 999px;
            background: #18181B;
            border: 1px solid rgba(212, 175, 55, 0.3);
            color: #E4E4E7;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            margin-top: 6px;
        }}
        .btn-browser-pill:hover, .btn-browser-pill:active {{
            background: #27272A;
            color: #FFFFFF;
            border-color: #D4AF37;
        }}
        .pulse-dot {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: #D4AF37;
            box-shadow: 0 0 8px #D4AF37;
            animation: pulse-glow 2s infinite;
        }}
        @keyframes pulse-glow {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(0.85); }}
        }}
        .title-brand {{
            font-size: 24px;
            font-weight: 900;
            letter-spacing: -0.02em;
            margin: 4px 0 2px;
        }}
        .color-gold {{
            color: #D4AF37;
        }}
        .color-blue {{
            color: #FFFFFF;
        }}
        .subtitle-brand {{
            color: #A1A1AA;
            font-size: 12px;
            font-weight: 500;
        }}
        .card-main {{
            width: 100%;
            max-width: 440px;
            background: #101014;
            border: 1px solid rgba(212, 175, 55, 0.22);
            border-radius: 20px;
            padding: 22px 20px;
            box-shadow: 0 16px 40px rgba(0, 0, 0, 0.8), 0 0 25px rgba(212, 175, 55, 0.08);
            margin: auto 0;
            position: relative;
        }}
        .step-container {{
            width: 100%;
        }}
        .text-center {{
            text-align: center;
        }}
        .choice-card {{
            background: #16161C;
            border: 1.5px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: left;
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .choice-card:hover, .choice-card:active {{
            border-color: #D4AF37;
            background: #1C1C24;
            transform: translateY(-1px);
        }}
        .choice-icon {{
            width: 44px;
            height: 44px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }}
        .choice-title {{
            font-size: 14px;
            font-weight: 800;
            color: #FFFFFF;
            margin-bottom: 2px;
        }}
        .choice-desc {{
            font-size: 11px;
            color: #A1A1AA;
            line-height: 1.3;
        }}
        .form-group {{
            margin-bottom: 14px;
            text-align: left;
        }}
        .form-label {{
            display: block;
            font-size: 11px;
            font-weight: 700;
            color: #E4E4E7;
            margin-bottom: 5px;
        }}
        .form-hint {{
            display: block;
            font-size: 11px;
            color: #71717A;
            margin-top: 4px;
            line-height: 1.3;
        }}
        .input-wrap {{
            position: relative;
            display: flex;
            align-items: center;
        }}
        .input-control {{
            width: 100%;
            padding: 11px 13px;
            background: #16161C;
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 12px;
            color: #FFFFFF;
            font-size: 15px;
            font-weight: 500;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}
        .input-control:focus {{
            border-color: #D4AF37;
            box-shadow: 0 0 0 3px rgba(212, 175, 55, 0.25);
        }}
        .input-toggle-btn {{
            position: absolute;
            right: 10px;
            background: none;
            border: none;
            color: #71717A;
            cursor: pointer;
            padding: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .checkbox-label {{
            display: flex;
            align-items: flex-start;
            gap: 8px;
            font-size: 12px;
            color: #E4E4E7;
            cursor: pointer;
            margin-bottom: 14px;
            user-select: none;
            line-height: 1.3;
        }}
        .checkbox-label input[type="checkbox"] {{
            margin-top: 2px;
            accent-color: #D4AF37;
            cursor: pointer;
        }}
        .select-control {{
            width: 100%;
            padding: 10px 12px;
            background: #16161C;
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 10px;
            color: #FFFFFF;
            font-size: 13px;
            outline: none;
            cursor: pointer;
        }}
        .select-control:focus {{
            border-color: #D4AF37;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }}
        .btn {{
            width: 100%;
            padding: 12px 16px;
            border: none;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 800;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            text-decoration: none;
            transition: all 0.2s ease;
        }}
        .btn:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
        }}
        .btn-power {{
            background: #D4AF37;
            color: #000000 !important;
            font-weight: 900;
            box-shadow: 0 4px 16px rgba(212, 175, 55, 0.35);
            border: none;
        }}
        .btn-power:hover, .btn-power:active {{
            background: #B89324;
            color: #000000 !important;
        }}
        .btn-gold {{
            background: #D4AF37;
            color: #000000 !important;
            font-weight: 900;
            box-shadow: 0 4px 16px rgba(212, 175, 55, 0.35);
            border: none;
        }}
        .btn-gold:hover {{
            background: #B89324;
            color: #000000 !important;
        }}
        .btn-emerald {{
            background: linear-gradient(135deg, #059669 0%, #047857 100%);
            color: #FFFFFF;
            box-shadow: 0 4px 16px rgba(5, 150, 105, 0.4);
        }}
        .btn-outline {{
            background: #18181B;
            border: 1px solid rgba(255, 255, 255, 0.14);
            color: #E2E8F0;
            font-size: 12px;
            padding: 10px 14px;
        }}
        .btn-outline:hover {{
            background: #27272A;
            color: #FFFFFF;
            border-color: #D4AF37;
        }}
        .btn-danger-outline {{
            background: rgba(239, 68, 68, 0.08);
            border: 1px solid rgba(239, 68, 68, 0.35);
            color: #F87171;
            font-size: 12px;
            padding: 10px 14px;
        }}
        .btn-danger-outline:hover {{
            background: rgba(239, 68, 68, 0.18);
            color: #FFFFFF;
        }}
        .status-icon-wrap {{
            width: 54px;
            height: 54px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 10px;
        }}
        .status-icon-wrap svg {{
            width: 26px;
            height: 26px;
        }}
        .icon-emerald {{
            background: rgba(16, 185, 129, 0.16);
            border: 1px solid rgba(16, 185, 129, 0.4);
            color: #34D399;
        }}
        .icon-amber {{
            background: rgba(245, 158, 11, 0.16);
            border: 1px solid rgba(245, 158, 11, 0.4);
            color: #FBBF24;
        }}
        .icon-rose {{
            background: rgba(244, 63, 94, 0.16);
            border: 1px solid rgba(244, 63, 94, 0.4);
            color: #FB7185;
        }}
        .icon-blue {{
            background: rgba(37, 99, 235, 0.16);
            border: 1px solid rgba(37, 99, 235, 0.4);
            color: #60A5FA;
        }}
        .badge-pill {{
            display: inline-block;
            padding: 3px 12px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-top: 4px;
        }}
        .badge-emerald {{
            background: rgba(16, 185, 129, 0.18);
            border: 1px solid rgba(16, 185, 129, 0.45);
            color: #6EE7B7;
        }}
        .badge-blue {{
            background: rgba(37, 99, 235, 0.18);
            border: 1px solid rgba(37, 99, 235, 0.45);
            color: #93C5FD;
        }}
        .info-box {{
            background: #16161C;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 12px 14px;
            margin: 14px 0;
            text-align: left;
            font-size: 12px;
            color: #CBD5E1;
            line-height: 1.6;
        }}
        .info-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 5px;
        }}
        .info-row:last-child {{
            margin-bottom: 0;
        }}
        .banner-prospecto {{
            background: linear-gradient(135deg, rgba(37, 99, 235, 0.22) 0%, rgba(255, 204, 0, 0.12) 100%);
            border: 1px solid rgba(59, 130, 246, 0.35);
            border-radius: 14px;
            padding: 12px;
            text-align: center;
            margin-bottom: 14px;
        }}
        .banner-prospecto h4 {{
            font-size: 13px;
            font-weight: 800;
            color: #93C5FD;
            margin-bottom: 4px;
        }}
        .banner-prospecto p {{
            font-size: 11px;
            color: #CBD5E1;
            line-height: 1.4;
        }}
        .link-accent {{
            color: #D4AF37;
            text-decoration: underline;
            font-weight: 600;
            cursor: pointer;
        }}
        .link-accent:hover {{
            color: #FFC107;
        }}
        .btn-help-inline {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: rgba(212, 175, 55, 0.15);
            color: #D4AF37;
            font-size: 10px;
            font-weight: bold;
            border: 1px solid rgba(212, 175, 55, 0.4);
            cursor: pointer;
            vertical-align: middle;
            margin-left: 3px;
        }}
        .portal-footer {{
            width: 100%;
            max-width: 440px;
            text-align: center;
            padding: 10px 0 4px;
            font-size: 11px;
            color: #64748B;
        }}
        .portal-footer p {{
            margin-bottom: 2px;
        }}
        .portal-footer-meta {{
            font-family: monospace;
            font-size: 10px;
            color: #475569;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        .spinner {{
            animation: spin 1s linear infinite;
            display: inline-block;
            width: 16px;
            height: 16px;
        }}
        /* MODAL DE AYUDA */
        .modal-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.85);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 16px;
            z-index: 9999;
        }}
        .modal-card {{
            width: 100%;
            max-width: 400px;
            background: #101014;
            border: 1px solid rgba(212, 175, 55, 0.35);
            border-radius: 20px;
            padding: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.85);
            position: relative;
            max-height: 90vh;
            overflow-y: auto;
        }}
        .modal-close {{
            position: absolute;
            top: 14px;
            right: 14px;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #18181B;
            border: 1px solid rgba(255, 255, 255, 0.12);
            color: #A1A1AA;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
        }}
        .help-step {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .help-step:last-child {{
            border-bottom: none;
        }}
        .help-step-num {{
            width: 26px;
            height: 26px;
            border-radius: 50%;
            background: #D4AF37;
            color: #000000;
            font-weight: 800;
            font-size: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }}
        .help-step-content {{
            font-size: 12px;
            color: #CBD5E1;
            line-height: 1.4;
        }}
        .help-step-content strong {{
            color: #FFFFFF;
            display: block;
            margin-bottom: 2px;
        }}
    </style>
</head>
<body>

    <header class="portal-header">
        <div class="logo-wrap">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" style="width: 58px; height: 58px; filter: drop-shadow(0 4px 14px rgba(212, 175, 55, 0.35));">
                <rect width="100" height="100" rx="22" fill="#000000" />
                <circle cx="50" cy="50" r="42" fill="#D4AF37" />
                <circle cx="50" cy="50" r="9" fill="#000000" />
                <path d="M64 50 A14 14 0 0 0 50 36" fill="none" stroke="#000000" stroke-width="4.5" stroke-linecap="round" />
                <path d="M74 50 A24 24 0 0 0 50 26" fill="none" stroke="#000000" stroke-width="4.5" stroke-linecap="round" />
                <path d="M84 50 A34 34 0 0 0 50 16" fill="none" stroke="#000000" stroke-width="4.5" stroke-linecap="round" />
            </svg>
        </div>
        <div>
            <span class="badge-wifi">
                <span class="pulse-dot"></span>
                <span>Zona Power • {nombre_estacion}</span>
            </span>
        </div>
        <div>
            <button type="button" onclick="abrirEnNavegadorExterno()" class="btn-browser-pill">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                <span>Abrir en Navegador (Chrome / Safari)</span>
            </button>
        </div>
        <h1 class="title-brand">
            <span class="color-gold">⚡ ZONA</span> <span class="color-blue">POWER</span>
        </h1>
        <p class="subtitle-brand">Red de Acceso Público Oficial de Power Link</p>
    </header>

    {banner_html}

    <main class="card-main">
        <input type="hidden" id="macAddress" value="{mac}">
        <input type="hidden" id="ipAddress" value="{ip}">
        <input type="hidden" id="gwAddress" value="{gw_address}">
        <input type="hidden" id="targetUrl" value="{target_url}">

        <!-- PASO 0: Fuera de Horario Operativo -->
        <div id="stepFueraDeHorario" class="step-container text-center" style="display: {'block' if not esta_abierto else 'none'};">
            <div class="status-icon-wrap icon-amber">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            </div>
            <h3 style="font-size: 17px; font-weight: 800; color: #FFFFFF; margin-bottom: 4px;">Servicio Fuera de Horario</h3>
            <span class="badge-pill badge-amber" style="margin-bottom: 10px;">Horario de Operación: {horario_ini} a {horario_fin}</span>
            <p style="font-size: 12px; color: #CBD5E1; margin: 10px 0 14px; line-height: 1.5;">
                El servicio de Wi-Fi gratuito de <strong style="color: #FFCC00;">Zona Power ({nombre_estacion})</strong> se encuentra temporalmente apagado durante la noche por motivos de mantenimiento preventivo y seguridad comunitaria.
            </p>

            <div class="info-box" style="border-color: rgba(245, 158, 11, 0.35); background: rgba(245, 158, 11, 0.08); color: #FDE68A; text-align: center;">
                ¡Te esperamos a partir de las <strong>{horario_ini}</strong>! Gracias por preferir a Power Link.
            </div>

            <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 14px;">
                <a href="{wa_url}" target="_blank" class="btn btn-emerald" style="font-size: 12px;">
                    <span>📲 Contactar a Soporte por WhatsApp</span>
                </a>
            </div>
        </div>

        <!-- PASO 1: Bienvenida Bifurcada (Elección de perfil) -->
        <div id="stepWelcome" class="step-container" style="display: {'block' if esta_abierto else 'none'};">
            <div class="text-center" style="margin-bottom: 16px;">
                <h2 style="font-size: 16px; font-weight: 800; color: #FFFFFF;">¿Eres cliente de Power Link?</h2>
                <p style="font-size: 12px; color: #94A3B8; margin-top: 3px;">Selecciona tu modalidad de acceso a la red</p>
            </div>

            <div class="choice-card" onclick="irALogin()">
                <div class="choice-icon" style="background: rgba(212, 175, 55, 0.15); border: 1px solid rgba(212, 175, 55, 0.4); color: #D4AF37;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                </div>
                <div style="flex: 1;">
                    <div class="choice-title" style="color: #D4AF37;">Soy Cliente Abonado ⚡</div>
                    <div class="choice-desc">Navegación ilimitada de alta velocidad con tu cuenta de Power Link.</div>
                </div>
                <div style="color: #D4AF37; font-size: 18px;">➜</div>
            </div>

            <div class="choice-card" onclick="irAProspecto()">
                <div class="choice-icon" style="background: rgba(16, 185, 129, 0.2); border: 1px solid rgba(16, 185, 129, 0.4); color: #34D399;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 12 20 22 4 22 4 12"/><rect width="20" height="5" x="2" y="7"/><line x1="12" x2="12" y1="22" y2="7"/><path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"/><path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"/></svg>
                </div>
                <div style="flex: 1;">
                    <div class="choice-title" style="color: #6EE7B7;">No soy Cliente / Prueba 🎁</div>
                    <div class="choice-desc">Prueba de cortesía gratuita de {tiempo_cortesia} minutos por dispositivo.</div>
                </div>
                <div style="color: #10B981; font-size: 18px;">➜</div>
            </div>

            <div class="text-center" style="margin-top: 14px;">
                <button type="button" onclick="abrirAyuda()" style="background: none; border: none; color: #94A3B8; font-size: 12px; cursor: pointer; display: inline-flex; align-items: center; gap: 5px;">
                    <span class="btn-help-inline">?</span>
                    <span>¿Cómo activar mi acceso o crear mi cuenta?</span>
                </button>
            </div>
        </div>

        <!-- PASO 1: Iniciar Sesión Abonado -->
        <div id="stepLogin" class="step-container hidden" style="display: none;">
            <div class="text-center" style="margin-bottom: 14px;">
                <h2 style="font-size: 17px; font-weight: 800; color: #FFFFFF;">Iniciar Sesión</h2>
                <div style="font-size: 12px; color: #94A3B8; margin-top: 4px;">
                    ¿No tienes cuenta? <span class="link-accent" onclick="irARegistro()">Regístrate Aquí</span>
                    <button type="button" onclick="abrirAyuda()" class="btn-help-inline" title="Ayuda de registro">?</button>
                </div>
            </div>

            <div class="form-group">
                <label class="form-label" for="loginUsuarioInput">Cédula o Correo Electrónico</label>
                <div class="input-wrap">
                    <input type="text" id="loginUsuarioInput" placeholder="Ej. 15871667 o micorreo@gmail.com" class="input-control" autocomplete="username">
                </div>
                <span class="form-hint">Ingresa tu número de cédula o el correo de tu contrato.</span>
            </div>

            <div class="form-group">
                <label class="form-label" for="loginPasswordInput">Contraseña</label>
                <div class="input-wrap">
                    <input type="password" id="loginPasswordInput" placeholder="••••••••" class="input-control" autocomplete="current-password">
                    <button type="button" class="input-toggle-btn" onclick="togglePassword('loginPasswordInput', 'iconEyeLogin')">
                        <span id="iconEyeLogin">👁</span>
                    </button>
                </div>
            </div>

            <label class="checkbox-label">
                <input type="checkbox" id="loginRecordarMac" checked>
                <span>Recordar este equipo por {dias_abonado} días (inicio automático)</span>
            </label>

            <button type="button" id="btnLogin" onclick="ejecutarLogin()" class="btn btn-power">
                <span>Iniciar Sesión y Conectar</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            </button>

            <div class="text-center" style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center;">
                <button type="button" onclick="irARecuperar()" style="background: none; border: none; color: #F59E0B; text-decoration: underline; font-size: 11px; cursor: pointer;">
                    ¿Olvidaste tu Contraseña?
                </button>
                <button type="button" onclick="irAWelcome()" style="background: none; border: none; color: #94A3B8; font-size: 11px; cursor: pointer;">
                    ⬅ Volver
                </button>
            </div>
        </div>

        <!-- PASO 2A: Registro Abonado - Paso 1 (Cédula y Correo) -->
        <div id="stepRegistroPaso1" class="step-container hidden" style="display: none;">
            <div class="text-center" style="margin-bottom: 14px;">
                <h2 style="font-size: 17px; font-weight: 800; color: #FFFFFF;">Crear Cuenta de Zona Power</h2>
                <p style="font-size: 12px; color: #94A3B8; margin-top: 3px;">Paso 1 de 2: Validación de Identidad</p>
            </div>

            <div class="info-box" style="margin-top: 0; margin-bottom: 14px; border-color: rgba(59, 130, 246, 0.35); background: rgba(59, 130, 246, 0.08);">
                Valida tu cédula y correo registrado en tu contrato con Power Link para crear tu contraseña.
            </div>

            <div class="form-group">
                <label class="form-label" for="regCedulaInput">Cédula de Identidad</label>
                <input type="text" id="regCedulaInput" placeholder="Ej. 15871667" class="input-control" inputmode="numeric">
                <span class="form-hint">Ingresa los números sin letras ni puntos.</span>
            </div>

            <div class="form-group">
                <label class="form-label" for="regEmailInput">Correo Electrónico Registrado</label>
                <input type="email" id="regEmailInput" placeholder="micorreo@gmail.com" class="input-control">
                <span class="form-hint">
                    Debe coincidir con el correo de tu contrato. 
                    <a href="javascript:void(0)" onclick="abrirAyuda()" class="link-accent">¿No lo recuerdas?</a>
                </span>
            </div>

            <button type="button" id="btnValidarRegistro" onclick="validarDatosRegistro()" class="btn btn-power">
                <span>Continuar y Validar Datos</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            </button>

            <div class="text-center" style="margin-top: 12px;">
                <button type="button" onclick="irALogin()" style="background: none; border: none; color: #94A3B8; font-size: 11px; cursor: pointer;">
                    ⬅ Ya tengo cuenta / Volver
                </button>
            </div>
        </div>

        <!-- PASO 2B: Registro Abonado - Paso 2 (Definir Contraseña) -->
        <div id="stepRegistroPaso2" class="step-container hidden" style="display: none;">
            <div class="text-center" style="margin-bottom: 14px;">
                <h2 style="font-size: 17px; font-weight: 800; color: #FFFFFF;">Definir Contraseña</h2>
                <p style="font-size: 12px; color: #94A3B8; margin-top: 3px;">Paso 2 de 2: Seguridad de tu cuenta</p>
            </div>

            <div class="info-box" style="margin-top: 0; margin-bottom: 14px; border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.08);">
                ¡Hola <strong style="color: #6EE7B7;" id="regNombreDisplay">Abonado</strong>! Crea tu contraseña para conectar este y tus otros dispositivos a Zona Power.
            </div>

            <div class="form-group">
                <label class="form-label" for="regPasswordInput">Nueva Contraseña (mínimo 6 caracteres)</label>
                <div class="input-wrap">
                    <input type="password" id="regPasswordInput" placeholder="••••••••" class="input-control">
                    <button type="button" class="input-toggle-btn" onclick="togglePassword('regPasswordInput', 'iconEyeReg1')">
                        <span id="iconEyeReg1">👁</span>
                    </button>
                </div>
            </div>

            <div class="form-group">
                <label class="form-label" for="regPasswordConfirmInput">Confirmar Contraseña</label>
                <div class="input-wrap">
                    <input type="password" id="regPasswordConfirmInput" placeholder="••••••••" class="input-control">
                    <button type="button" class="input-toggle-btn" onclick="togglePassword('regPasswordConfirmInput', 'iconEyeReg2')">
                        <span id="iconEyeReg2">👁</span>
                    </button>
                </div>
            </div>

            <label class="checkbox-label">
                <input type="checkbox" id="regRecordarMac" checked>
                <span>Recordar este equipo por {dias_abonado} días (inicio automático)</span>
            </label>

            <button type="button" id="btnCompletarRegistro" onclick="completarRegistro()" class="btn btn-power">
                <span>Completar Registro y Navegar</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            </button>

            <div class="text-center" style="margin-top: 12px;">
                <button type="button" onclick="mostrarPaso('stepRegistroPaso1')" style="background: none; border: none; color: #94A3B8; font-size: 11px; cursor: pointer;">
                    ⬅ Modificar cédula o correo
                </button>
            </div>
        </div>

        <!-- PASO 3: Recuperar Contraseña -->
        <div id="stepRecuperar" class="step-container hidden" style="display: none;">
            <div class="text-center" style="margin-bottom: 14px;">
                <h2 style="font-size: 17px; font-weight: 800; color: #FFFFFF;">Recuperar Contraseña</h2>
                <p style="font-size: 12px; color: #94A3B8; margin-top: 3px;">Ingresa tus datos para restablecer tu clave</p>
            </div>

            <div class="form-group">
                <label class="form-label" for="recCedulaInput">Cédula de Identidad</label>
                <input type="text" id="recCedulaInput" placeholder="Ej. 15871667" class="input-control" inputmode="numeric">
            </div>

            <div class="form-group">
                <label class="form-label" for="recEmailInput">Correo Electrónico Registrado</label>
                <input type="email" id="recEmailInput" placeholder="micorreo@gmail.com" class="input-control">
            </div>

            <div class="form-group">
                <label class="form-label" for="recPasswordInput">Nueva Contraseña (mínimo 6 caracteres)</label>
                <div class="input-wrap">
                    <input type="password" id="recPasswordInput" placeholder="••••••••" class="input-control">
                    <button type="button" class="input-toggle-btn" onclick="togglePassword('recPasswordInput', 'iconEyeRec')">
                        <span id="iconEyeRec">👁</span>
                    </button>
                </div>
            </div>

            <button type="button" id="btnEjecutarRecuperacion" onclick="ejecutarRecuperacion()" class="btn btn-gold">
                <span>Guardar Nueva Contraseña</span>
            </button>

            <div class="text-center" style="margin-top: 12px;">
                <button type="button" onclick="irALogin()" style="background: none; border: none; color: #94A3B8; font-size: 11px; cursor: pointer;">
                    ⬅ Volver al inicio de sesión
                </button>
            </div>
        </div>

        <!-- PASO 4: Solvente (Sesión Activa de Abonado) -->
        <div id="stepSolvente" class="step-container text-center hidden" style="display: none;">
            <div class="status-icon-wrap icon-emerald">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            </div>
            <h3 style="font-size: 18px; font-weight: 800; color: #FFFFFF;" id="solventeNombre">¡Bienvenido!</h3>
            <span class="badge-pill badge-emerald">CLIENTE SOLVENTE</span>
            <p style="font-size: 12px; color: #CBD5E1; margin: 8px 0 12px;">Tu dispositivo ha sido autorizado con navegación de alta velocidad.</p>

            <div class="info-box">
                <div class="info-row">
                    <span style="color: #60A5FA;">💻</span>
                    <span>Dispositivos conectados: <strong style="color: #FFFFFF;" id="dispActivos">1 de {limite_disp}</strong></span>
                </div>
                <div class="info-row">
                    <span style="color: #FFCC00;">⚡</span>
                    <span>Conexión continua mientras tu cuenta permanezca solvente.</span>
                </div>
                <div class="info-row">
                    <span style="color: #F59E0B;">⏱</span>
                    <span>Desconexión automática tras {tiempo_inactividad} min de inactividad.</span>
                </div>
            </div>

            <!-- ADVERTENCIA DE VELOCIDAD Y SPEEDTEST -->
            <div class="info-box" style="margin: 10px 0 14px; border-color: rgba(212, 175, 55, 0.35); background: rgba(212, 175, 55, 0.08); text-align: left;">
                <div style="display: flex; align-items: center; gap: 7px; margin-bottom: 4px;">
                    <span style="font-size: 15px;">⚡</span>
                    <strong style="color: #D4AF37; font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em;">Nota sobre Pruebas de Velocidad (Speedtest)</strong>
                </div>
                <p style="font-size: 11px; color: #CBD5E1; line-height: 1.45; margin: 0;">
                    Zona Power gestiona el ancho de banda dinámicamente para que todos los usuarios disfruten de navegación fluida. Las mediciones en Speedtest reflejan la asignación comunitaria compartida y no representan la velocidad de los planes residenciales o corporativos de fibra óptica dedicada de Power Link.
                </p>
            </div>

            <div style="display: flex; flex-direction: column; gap: 8px;">
                <button type="button" id="btnNavegar" onclick="iniciarNavegacionFinal()" class="btn btn-emerald">
                    <span>Empezar a Navegar</span>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                </button>
                <button type="button" onclick="desvincularDispositivo()" class="btn btn-danger-outline">
                    <span>🚫 Desvincular este dispositivo</span>
                </button>
            </div>
        </div>

        <!-- PASO 5: Límite de Dispositivos Concurrente (2 por abonado) -->
        <div id="stepLimite" class="step-container text-center hidden" style="display: none;">
            <div class="status-icon-wrap icon-amber">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            </div>
            <h3 style="font-size: 16px; font-weight: 800; color: #FFFFFF;">Límite de Dispositivos Alcanzado</h3>
            <p style="font-size: 12px; color: #CBD5E1; margin: 8px 0 14px;">Ya tienes <strong style="color: #FFCC00;">{limite_disp} dispositivos simultáneos</strong> navegando en Zona Power con esta cuenta.</p>

            <div class="info-box" style="border-color: rgba(245, 158, 11, 0.35); background: rgba(245, 158, 11, 0.08); color: #FDE68A;">
                Desconecta o desvincula uno de tus otros equipos para que este dispositivo pueda navegar.
            </div>

            <button type="button" onclick="irALogin()" class="btn btn-outline">
                Volver al inicio de sesión
            </button>
        </div>

        <!-- PASO 6: Insolvente (Aviso de cobro y WhatsApp) -->
        <div id="stepInsolvente" class="step-container text-center hidden" style="display: none;">
            <div class="status-icon-wrap icon-rose">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
            </div>
            <h3 style="font-size: 16px; font-weight: 800; color: #FFFFFF;">Aviso de Cuenta — Power Link</h3>
            <p style="font-size: 12px; color: #CBD5E1; margin: 8px 0 12px;">Estimado cliente, tu servicio presenta saldo pendiente. Por favor comunícate con nosotros para regularizar tu estatus y disfrutar de Zona Power sin límites.</p>

            <div class="info-box" style="border-color: rgba(244, 63, 94, 0.35); background: rgba(244, 63, 94, 0.08); color: #FECDD3; text-align: center;">
                Ponte al día con tu factura o reporta tu pago de forma instantánea a través de nuestra central:
            </div>

            <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 10px;">
                <a href="{wa_url}" target="_blank" class="btn btn-emerald" style="font-size: 13px;">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L0 24l6.335-1.662c1.746.953 3.71 1.456 5.711 1.457h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/></svg>
                    <span>Reportar Pago por WhatsApp</span>
                </a>
                <a href="tel:{tlf_soporte.replace(' ', '')}" class="btn btn-outline" style="font-size: 12px;">
                    <span>📞 Llamar al {tlf_soporte}</span>
                </a>
            </div>

            <button type="button" onclick="irAWelcome()" style="background: none; border: none; color: #94A3B8; text-decoration: underline; font-size: 11px; margin-top: 14px; cursor: pointer;">
                Volver al menú principal
            </button>
        </div>

        <!-- PASO 7: Formulario Prospectos (Cortesía de 30 min) -->
        <div id="stepProspecto" class="step-container hidden" style="display: none;">
            <div class="banner-prospecto">
                <div style="font-size: 22px; margin-bottom: 4px;">🎁</div>
                <h4>¡Prueba de Navegación Gratuita de {tiempo_cortesia} Minutos!</h4>
                <p>Completa este breve formulario y obtendrás <strong style="color: #FFCC00;">{tiempo_cortesia} minutos</strong> de acceso inmediato de cortesía en Zona Power (1 prueba por dispositivo cada {dias_reintento} días).</p>
            </div>

            <form id="formProspecto" onsubmit="enviarProspecto(event)">
                <div class="form-group">
                    <label class="form-label" for="prosCedula">Cédula de Identidad</label>
                    <input type="text" id="prosCedula" required placeholder="Ej. 15871667" class="input-control" inputmode="numeric" style="font-size: 14px; padding: 10px 12px;">
                </div>

                <div class="grid-2">
                    <div class="form-group">
                        <label class="form-label" for="prosNombre">Nombre</label>
                        <input type="text" id="prosNombre" required placeholder="Tu Nombre" class="input-control" style="font-size: 14px; padding: 10px 12px;">
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="prosApellido">Apellido</label>
                        <input type="text" id="prosApellido" required placeholder="Tu Apellido" class="input-control" style="font-size: 14px; padding: 10px 12px;">
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label" for="prosTelefono">Teléfono (WhatsApp)</label>
                    <input type="tel" id="prosTelefono" required placeholder="0412-1234567" class="input-control" style="font-size: 14px; padding: 10px 12px;">
                </div>

                <div class="grid-2">
                    <div class="form-group">
                        <label class="form-label" for="prosEstado">Estado</label>
                        <select id="prosEstado" onchange="actualizarMunicipios()" class="select-control"></select>
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="prosMunicipio">Municipio</label>
                        <select id="prosMunicipio" class="select-control"></select>
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label" for="prosZona">Zona / Urbanización / Sector</label>
                    <input type="text" id="prosZona" required placeholder="Ej. La Matica, Casco Central, El Cabotaje" class="input-control" style="font-size: 14px; padding: 10px 12px;">
                </div>

                <button type="submit" id="btnEnviarProspecto" class="btn btn-power" style="margin-top: 6px;">
                    <span>🎁 Activar mi Prueba de Navegación ({tiempo_cortesia} Min)</span>
                </button>
            </form>

            <div style="font-size: 11px; color: #94A3B8; text-align: center; margin-top: 10px; line-height: 1.35; padding: 6px 10px; background: rgba(15, 23, 42, 0.6); border-radius: 8px;">
                ℹ️ <em>Navegación de cortesía comunitaria con reparto inteligente optimizado para mensajería, redes sociales y navegación web.</em>
            </div>

            <div class="text-center" style="margin-top: 12px;">
                <button type="button" onclick="irAWelcome()" style="background: none; border: none; color: #94A3B8; text-decoration: underline; font-size: 11px; cursor: pointer;">
                    ⬅ Volver al inicio
                </button>
            </div>
        </div>

        <!-- PASO 8: Prospecto Cortesía Activada con Éxito -->
        <div id="stepProspectoExito" class="step-container text-center hidden" style="display: none;">
            <div class="status-icon-wrap icon-blue">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </div>
            <h3 style="font-size: 18px; font-weight: 800; color: #FFFFFF;">¡Prueba Activada!</h3>
            <span class="badge-pill badge-blue">{tiempo_cortesia} Minutos de Navegación</span>
            <p style="font-size: 12px; color: #CBD5E1; margin: 10px 0 14px;">Hemos guardado tu solicitud para nuevos despliegues de fibra óptica. Un asesor de Power Link te contactará pronto.</p>

            <div class="info-box" style="text-align: center; font-size: 13px;">
                <span>Tiempo de prueba restante: <strong id="timerDisplay" style="color: #FFCC00; font-family: monospace; font-size: 15px;">{tiempo_cortesia}:00</strong></span>
            </div>

            <button type="button" onclick="iniciarNavegacionFinal()" class="btn btn-power">
                <span>Disfrutar de mi Cortesía</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            </button>
        </div>

        <!-- PASO 9: Prospecto Cortesía Bloqueada por 7 días -->
        <div id="stepProspectoBloqueado" class="step-container text-center hidden" style="display: none;">
            <div class="status-icon-wrap icon-amber">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="6" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            </div>
            <h3 style="font-size: 16px; font-weight: 800; color: #FFFFFF;">Prueba Semanal ya Utilizada</h3>
            <p style="font-size: 12px; color: #CBD5E1; margin: 8px 0 12px;" id="msgBloqueo7Dias">Este dispositivo ya disfrutó de la prueba gratuita semanal. Podrás solicitar otra en unos días (ciclo de {dias_reintento} días).</p>

            <div class="info-box" style="border-color: rgba(245, 158, 11, 0.35); background: rgba(245, 158, 11, 0.08); color: #FDE68A;">
                ¿Deseas navegación ilimitada sin cortes? ¡Contrata tu servicio de fibra óptica Power Link de ultra alta velocidad!
            </div>

            <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 10px;">
                <a href="{wa_url}" target="_blank" class="btn btn-emerald" style="font-size: 13px;">
                    <span>📲 Solicitar Plan de Internet por WhatsApp</span>
                </a>
                <button type="button" onclick="irAWelcome()" class="btn btn-outline" style="font-size: 12px;">
                    Volver al inicio
                </button>
            </div>
        </div>

    </main>

    <!-- MODAL DE AYUDA (INTERACTIVO & AUTOCONTENIDO) -->
    <div id="modalAyuda" class="modal-overlay hidden" style="display: none;">
        <div class="modal-card">
            <button type="button" class="modal-close" onclick="cerrarAyuda()">✕</button>
            <div class="text-center" style="margin-bottom: 14px;">
                <span style="font-size: 24px;">💡</span>
                <h3 style="font-size: 16px; font-weight: 800; color: #FFFFFF; margin-top: 4px;">Guía de Acceso Zona Power</h3>
                <p style="font-size: 11px; color: #94A3B8;">Accede a tu cuenta en cuatro sencillos pasos</p>
            </div>

            <div style="margin-bottom: 14px;">
                <div class="help-step">
                    <div class="help-step-num">1</div>
                    <div class="help-step-content">
                        <strong>Actualiza tus datos o revisa tu correo</strong>
                        Verifica el correo registrado en tu contrato con Power Link o en tu Oficina Virtual en <span style="color: #60A5FA;">portal.powerlink.com.ve</span>.
                    </div>
                </div>
                <div class="help-step">
                    <div class="help-step-num">2</div>
                    <div class="help-step-content">
                        <strong>Inicia Sesión o Regístrate</strong>
                        Si es tu primera vez en Zona Power, pulsa en <em>"Regístrate Aquí"</em> en la pantalla de inicio de sesión.
                    </div>
                </div>
                <div class="help-step">
                    <div class="help-step-num">3</div>
                    <div class="help-step-content">
                        <strong>Valida Cédula y Correo</strong>
                        Ingresa tu número de cédula y el correo registrado para confirmar que eres el titular del servicio.
                    </div>
                </div>
                <div class="help-step">
                    <div class="help-step-num">4</div>
                    <div class="help-step-content">
                        <strong>Crea tu Contraseña y Conecta</strong>
                        Define tu contraseña de acceso para navegar sin límites con hasta 2 dispositivos simultáneos.
                    </div>
                </div>
            </div>

            <!-- FAQ SPEEDTEST -->
            <div style="border-top: 1px solid #1E293B; padding-top: 12px; margin-top: 10px; text-align: left;">
                <strong style="color: #FFCC00; font-size: 12px; display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                    <span>🚀</span> ¿Por qué mi test de velocidad muestra valores administrados?
                </strong>
                <p style="font-size: 11px; color: #94A3B8; line-height: 1.4; margin: 0;">
                    Para que todos los usuarios disfruten de una conexión fluida y sin caídas, cada estación de Zona Power distribuye el tráfico equitativamente entre los concurrentes (hasta la máxima capacidad de la estación y con un piso mínimo garantizado). Si deseas velocidades dedicadas ultra rápidas para tu hogar o empresa, contrata un plan de fibra óptica Power Link.
                </p>
            </div>

            <div class="info-box" style="margin: 12px 0 8px; background: rgba(37, 99, 235, 0.1); border-color: rgba(59, 130, 246, 0.3); text-align: center;">
                <div style="font-size: 11px; color: #93C5FD; font-weight: 600;">¿Problemas con tu correo o contraseña?</div>
                <div style="font-size: 12px; color: #FFFFFF; margin-top: 3px;">WhatsApp Soporte: <strong>0212 7203500</strong></div>
            </div>

            <button type="button" class="btn btn-power" onclick="cerrarAyuda()" style="margin-top: 6px;">
                <span>¡Entendido!</span>
            </button>
        </div>
    </div>

    <footer class="portal-footer">
        <p>© 2026 Power Link C.A. — Todos los derechos reservados.</p>
        <p class="portal-footer-meta">IP: {ip} | MAC: {mac}</p>
    </footer>

    <script>
        const municipiosPorEstado = {estados_json};

        function inicializarEstados() {{
            const edoSelect = document.getElementById("prosEstado");
            if (!edoSelect) return;
            edoSelect.innerHTML = "";
            const estados = Object.keys(municipiosPorEstado).sort();
            estados.forEach(e => {{
                const opt = document.createElement("option");
                opt.value = e;
                opt.textContent = e;
                if (e === "Miranda") opt.selected = true;
                edoSelect.appendChild(opt);
            }});
            actualizarMunicipios();
        }}

        function actualizarMunicipios() {{
            const edo = document.getElementById("prosEstado").value;
            const munSelect = document.getElementById("prosMunicipio");
            if (!munSelect) return;
            munSelect.innerHTML = "";
            const list = municipiosPorEstado[edo] || ["Otro"];
            list.forEach(m => {{
                const opt = document.createElement("option");
                opt.value = m;
                opt.textContent = m;
                munSelect.appendChild(opt);
            }});
        }}

        function ocultarTodos() {{
            const steps = [
                "stepWelcome", "stepLogin", "stepRegistroPaso1", "stepRegistroPaso2",
                "stepRecuperar", "stepSolvente", "stepLimite", "stepInsolvente",
                "stepProspecto", "stepProspectoExito", "stepProspectoBloqueado"
            ];
            steps.forEach(id => {{
                const el = document.getElementById(id);
                if (el) {{
                    el.classList.add("hidden");
                    el.style.display = "none";
                }}
            }});
        }}

        function mostrarPaso(stepId) {{
            ocultarTodos();
            const target = document.getElementById(stepId);
            if (target) {{
                target.classList.remove("hidden");
                target.style.display = "block";
            }}
        }}

        function irAWelcome() {{
            mostrarPaso("stepWelcome");
        }}

        function irALogin() {{
            mostrarPaso("stepLogin");
            const inp = document.getElementById("loginUsuarioInput");
            if (inp) inp.focus();
        }}

        function irARegistro() {{
            mostrarPaso("stepRegistroPaso1");
            const inp = document.getElementById("regCedulaInput");
            if (inp) inp.focus();
        }}

        function irARecuperar() {{
            mostrarPaso("stepRecuperar");
            const inp = document.getElementById("recCedulaInput");
            if (inp) inp.focus();
        }}

        function irAProspecto() {{
            mostrarPaso("stepProspecto");
            const inp = document.getElementById("prosCedula");
            if (inp) inp.focus();
        }}

        function abrirAyuda() {{
            const m = document.getElementById("modalAyuda");
            if (m) {{
                m.classList.remove("hidden");
                m.style.display = "flex";
            }}
        }}

        function cerrarAyuda() {{
            const m = document.getElementById("modalAyuda");
            if (m) {{
                m.classList.add("hidden");
                m.style.display = "none";
            }}
        }}

        function togglePassword(inputId, iconId) {{
            const inp = document.getElementById(inputId);
            const ic = document.getElementById(iconId);
            if (!inp) return;
            if (inp.type === "password") {{
                inp.type = "text";
                if (ic) ic.textContent = "🙈";
            }} else {{
                inp.type = "password";
                if (ic) ic.textContent = "👁";
            }}
        }}

        // APERTURA DIRECTA EN EL NAVEGADOR COMPLETO (ANDROID INTENT / IOS SYSTEM)
        function abrirEnNavegadorExterno() {{
            const curUrl = window.location.href;
            const isAndroid = /Android/i.test(navigator.userAgent);
            const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);

            if (isAndroid) {{
                const host = window.location.host;
                const path = window.location.pathname + window.location.search;
                const intent = "intent://" + host + path + "#Intent;scheme=http;action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;end;";
                window.location.href = intent;
            }} else if (isIOS) {{
                window.open(curUrl, "_system");
            }} else {{
                window.open(curUrl, "_blank");
            }}
        }}

        // FINALIZAR NAVEGACIÓN Y ABRIR DESTINO EN NAVEGADOR
        function iniciarNavegacionFinal(url) {{
            const dest = url || document.getElementById("targetUrl").value || "https://google.com";
            // Notificar sondas de conectividad del SO (Android/iOS) para liberar el asistente cautivo de inmediato
            fetch("/generate_204").catch(function() {{}});
            fetch("/zonapower/portal/ping").catch(function() {{}});

            const isAndroid = /Android/i.test(navigator.userAgent);
            if (isAndroid) {{
                const cleanUrl = dest.replace(/^https?:\\/\\//, "");
                const scheme = dest.startsWith("https") ? "https" : "http";
                const intent = "intent://" + cleanUrl + "#Intent;scheme=" + scheme + ";action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;end;";
                window.location.href = intent;
            }} else {{
                window.location.href = dest;
            }}
        }}

        // AUTO-CHECK MAC AL CARGAR (CICLO DE 7 DÍAS)
        async function checkMacAuto() {{
            const mac = document.getElementById("macAddress").value;
            const ip = document.getElementById("ipAddress").value;
            if (!mac || mac === "00:00:00:00:00:00") return;

            try {{
                const resp = await fetch("/zonapower/api/check-mac-auto", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ mac_address: mac, ip_address: ip }})
                }});
                const data = await resp.json();

                if (data.status === "ok" && data.action === "allow") {{
                    document.getElementById("solventeNombre").textContent = "¡Bienvenido, " + (data.cliente?.name || "Abonado") + "!";
                    document.getElementById("dispActivos").textContent = (data.dispositivos_activos || 1) + " de {limite_disp}";
                    mostrarPaso("stepSolvente");
                }} else if (data.status === "cortesia_activa") {{
                    mostrarPaso("stepProspectoExito");
                    iniciarContadorSegundos(data.segundos_restantes);
                }} else if (data.status === "insolvente") {{
                    mostrarPaso("stepInsolvente");
                }} else if (data.status === "expired") {{
                    mostrarPaso("stepLogin");
                    alert(data.message || "Tu sesión recordada de ' + (data.dias_abonado || {dias_abonado}) + ' días ha finalizado por seguridad. Por favor ingresa tu contraseña.");
                }}
            }} catch (e) {{
                console.log("[Portal] Check MAC auto omitido:", e);
            }}
        }}

        // LOGIN DE ABONADO
        async function ejecutarLogin() {{
            const ident = document.getElementById("loginUsuarioInput").value.trim();
            const pass = document.getElementById("loginPasswordInput").value;
            const recordar = document.getElementById("loginRecordarMac").checked;

            if (!ident || !pass) {{
                alert("Por favor ingresa tu cédula o correo y contraseña.");
                return;
            }}

            const btn = document.getElementById("btnLogin");
            const orig = btn.innerHTML;
            btn.innerHTML = '<span class="spinner">⏳</span><span>Verificando...</span>';
            btn.disabled = true;

            const payload = {{
                usuario: ident,
                password: pass,
                mac_address: document.getElementById("macAddress").value,
                ip_address: document.getElementById("ipAddress").value,
                recordar_mac: recordar
            }};

            try {{
                const resp = await fetch("/zonapower/api/login", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify(payload)
                }});
                const data = await resp.json();

                if (data.status === "ok" && data.action === "allow") {{
                    document.getElementById("solventeNombre").textContent = "¡Bienvenido, " + (data.cliente?.name || "Abonado") + "!";
                    document.getElementById("dispActivos").textContent = (data.dispositivos_activos || 1) + " de {limite_disp}";
                    mostrarPaso("stepSolvente");
                }} else if (data.action === "limit_reached") {{
                    mostrarPaso("stepLimite");
                }} else if (data.action === "debt") {{
                    mostrarPaso("stepInsolvente");
                }} else if (data.status === "not_registered") {{
                    if (confirm(data.message + "\\n\\n¿Deseas ir al registro de abonados ahora?")) {{
                        document.getElementById("regCedulaInput").value = ident;
                        irARegistro();
                    }}
                }} else {{
                    alert(data.message || "Error al iniciar sesión.");
                }}
            }} catch (e) {{
                alert("Error de conexión: " + e.message);
            }} finally {{
                btn.innerHTML = orig;
                btn.disabled = false;
            }}
        }}

        // PASO 1 DE REGISTRO: VALIDAR CÉDULA Y CORREO
        let _tempCedula = "";
        let _tempEmail = "";
        async function validarDatosRegistro() {{
            const ced = document.getElementById("regCedulaInput").value.trim();
            const email = document.getElementById("regEmailInput").value.trim();

            if (!ced) {{
                alert("Por favor ingresa tu número de cédula.");
                return;
            }}
            if (!email || !email.includes("@")) {{
                alert("Por favor ingresa un correo electrónico válido.");
                return;
            }}

            const btn = document.getElementById("btnValidarRegistro");
            const orig = btn.innerHTML;
            btn.innerHTML = '<span class="spinner">⏳</span><span>Validando con sistema...</span>';
            btn.disabled = true;

            try {{
                const resp = await fetch("/zonapower/api/verificar-datos-cliente", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ cedula: ced, email: email }})
                }});
                const data = await resp.json();

                if (data.status === "ok") {{
                    _tempCedula = ced;
                    _tempEmail = email;
                    document.getElementById("regNombreDisplay").textContent = data.nombre || "Abonado";
                    mostrarPaso("stepRegistroPaso2");
                    document.getElementById("regPasswordInput").focus();
                }} else if (data.status === "already_registered") {{
                    alert(data.message);
                    document.getElementById("loginUsuarioInput").value = ced;
                    irALogin();
                }} else if (data.status === "email_mismatch") {{
                    alert(data.message);
                }} else if (data.status === "not_found") {{
                    if (confirm(data.message + "\\n\\n¿Deseas solicitar una prueba gratuita de cortesía?")) {{
                        document.getElementById("prosCedula").value = ced;
                        irAProspecto();
                    }}
                }} else {{
                    alert(data.message || "Error validando datos.");
                }}
            }} catch (e) {{
                alert("Error de conexión con el sistema: " + e.message);
            }} finally {{
                btn.innerHTML = orig;
                btn.disabled = false;
            }}
        }}

        // PASO 2 DE REGISTRO: DEFINIR CONTRASEÑA Y CONECTAR
        async function completarRegistro() {{
            const p1 = document.getElementById("regPasswordInput").value;
            const p2 = document.getElementById("regPasswordConfirmInput").value;
            const recordar = document.getElementById("regRecordarMac").checked;

            if (p1.length < 6) {{
                alert("La contraseña debe tener al menos 6 caracteres.");
                return;
            }}
            if (p1 !== p2) {{
                alert("Las contraseñas no coinciden. Por favor verifícalas.");
                return;
            }}

            const btn = document.getElementById("btnCompletarRegistro");
            const orig = btn.innerHTML;
            btn.innerHTML = '<span class="spinner">⏳</span><span>Registrando y autorizando...</span>';
            btn.disabled = true;

            const payload = {{
                cedula: _tempCedula,
                email: _tempEmail,
                password: p1,
                mac_address: document.getElementById("macAddress").value,
                ip_address: document.getElementById("ipAddress").value,
                recordar_mac: recordar
            }};

            try {{
                const resp = await fetch("/zonapower/api/crear-cuenta", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify(payload)
                }});
                const data = await resp.json();

                if (data.status === "ok" && data.action === "allow") {{
                    alert("¡Cuenta creada exitosamente! Tu dispositivo ha sido conectado a Zona Power.");
                    document.getElementById("solventeNombre").textContent = "¡Bienvenido, " + (data.cliente?.name || "Abonado") + "!";
                    document.getElementById("dispActivos").textContent = (data.dispositivos_activos || 1) + " de {limite_disp}";
                    mostrarPaso("stepSolvente");
                }} else if (data.status === "limit_reached") {{
                    mostrarPaso("stepLimite");
                }} else if (data.status === "insolvente") {{
                    mostrarPaso("stepInsolvente");
                }} else {{
                    alert(data.message || "Error al completar registro.");
                }}
            }} catch (e) {{
                alert("Error de conexión: " + e.message);
            }} finally {{
                btn.innerHTML = orig;
                btn.disabled = false;
            }}
        }}

        // RECUPERAR CONTRASEÑA
        async function ejecutarRecuperacion() {{
            const ced = document.getElementById("recCedulaInput").value.trim();
            const email = document.getElementById("recEmailInput").value.trim();
            const p1 = document.getElementById("recPasswordInput").value;

            if (!ced || !email || p1.length < 6) {{
                alert("Por favor ingresa cédula, correo y una nueva contraseña de al menos 6 caracteres.");
                return;
            }}

            const btn = document.getElementById("btnEjecutarRecuperacion");
            const orig = btn.innerHTML;
            btn.innerHTML = '<span class="spinner">⏳</span><span>Actualizando...</span>';
            btn.disabled = true;

            try {{
                const resp = await fetch("/zonapower/api/recuperar-contrasena", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{
                        cedula: ced,
                        email: email,
                        nueva_contrasena: p1
                    }})
                }});
                const data = await resp.json();

                if (data.status === "ok") {{
                    alert(data.message);
                    document.getElementById("loginUsuarioInput").value = ced;
                    document.getElementById("loginPasswordInput").value = p1;
                    irALogin();
                }} else {{
                    alert(data.message || "Error al recuperar contraseña.");
                }}
            }} catch (e) {{
                alert("Error de comunicación: " + e.message);
            }} finally {{
                btn.innerHTML = orig;
                btn.disabled = false;
            }}
        }}

        // CLIENTE DESVINCULA SU DISPOSITIVO (BORRA MAC Y LIBERA CUPO)
        async function desvincularDispositivo() {{
            if (!confirm("¿Deseas desvincular este dispositivo? Tu sesión se cerrará y se liberará tu cupo para que puedas conectar otro equipo.")) {{
                return;
            }}

            const mac = document.getElementById("macAddress").value;
            try {{
                const resp = await fetch("/zonapower/api/desvincular-dispositivo", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ mac_address: mac }})
                }});
                const data = await resp.json();
                alert(data.message || "Dispositivo desvinculado con éxito.");
                irAWelcome();
            }} catch (e) {{
                alert("Error al desvincular: " + e.message);
            }}
        }}

        // FORMULARIO PROSPECTO (NO CLIENTES)
        async function enviarProspecto(e) {{
            e.preventDefault();
            const btn = document.getElementById("btnEnviarProspecto");
            const orig = btn.innerHTML;
            btn.innerHTML = '<span class="spinner">⏳</span><span>Registrando cortesía...</span>';
            btn.disabled = true;

            const payload = {{
                cedula: document.getElementById("prosCedula").value.trim(),
                nombre: document.getElementById("prosNombre").value.trim(),
                apellido: document.getElementById("prosApellido").value.trim(),
                telefono: document.getElementById("prosTelefono").value.trim(),
                estado: document.getElementById("prosEstado").value,
                municipio: document.getElementById("prosMunicipio").value,
                zona_sector: document.getElementById("prosZona").value.trim(),
                punto_origen: "Zona Power Wi-Fi 6",
                mac_address: document.getElementById("macAddress").value,
                ip_address: document.getElementById("ipAddress").value
            }};

            try {{
                const resp = await fetch("/zonapower/api/registrar-prospecto", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify(payload)
                }});
                const data = await resp.json();

                if (data.status === "ok") {{
                    mostrarPaso("stepProspectoExito");
                    iniciarContadorSegundos({tiempo_cortesia} * 60);
                }} else if (data.status === "already_used") {{
                    document.getElementById("msgBloqueo7Dias").textContent = data.message;
                    mostrarPaso("stepProspectoBloqueado");
                }} else if (data.status === "is_subscriber") {{
                    alert(data.message);
                    document.getElementById("loginUsuarioInput").value = payload.cedula;
                    irALogin();
                }} else {{
                    alert(data.message || "Error al procesar registro.");
                }}
            }} catch (err) {{
                alert("Error al enviar formulario: " + err.message);
            }} finally {{
                btn.innerHTML = orig;
                btn.disabled = false;
            }}
        }}

        function iniciarContadorSegundos(segundos) {{
            const display = document.getElementById("timerDisplay");
            if (!display) return;
            const intervalo = setInterval(() => {{
                segundos--;
                if (segundos <= 0) {{
                    clearInterval(intervalo);
                    display.textContent = "Expirado";
                    return;
                }}
                const m = Math.floor(segundos / 60);
                const s = segundos % 60;
                display.textContent = `${{m < 10 ? '0' : ''}}${{m}}:${{s < 10 ? '0' : ''}}${{s}}`;
            }}, 1000);
        }}

        document.addEventListener("DOMContentLoaded", () => {{
            inicializarEstados();
            checkMacAuto();

            const loginPass = document.getElementById("loginPasswordInput");
            if (loginPass) {{
                loginPass.addEventListener("keyup", (e) => {{
                    if (e.key === "Enter") ejecutarLogin();
                }});
            }}
            const regEmail = document.getElementById("regEmailInput");
            if (regEmail) {{
                regEmail.addEventListener("keyup", (e) => {{
                    if (e.key === "Enter") validarDatosRegistro();
                }});
            }}
            const regP2 = document.getElementById("regPasswordConfirmInput");
            if (regP2) {{
                regP2.addEventListener("keyup", (e) => {{
                    if (e.key === "Enter") completarRegistro();
                }});
            }}
        }});
    </script>
</body>
</html>
"""

    return HTMLResponse(content=html)



# ==========================================
# APIS DEL PORTAL CAUTIVO
# ==========================================

class CedulaCheckRequest(BaseModel):
    cedula: str
    mac_address: Optional[str] = "00:00:00:00:00:00"
    ip_address: Optional[str] = "10.90.0.X"
    punto_origen: Optional[str] = "CC La Colina"


class VerificarDatosClienteRequest(BaseModel):
    cedula: str
    email: Optional[str] = None


class CrearCuentaRequest(BaseModel):
    cedula: str
    email: str
    password: str
    mac_address: Optional[str] = "00:00:00:00:00:00"
    ip_address: Optional[str] = "10.90.0.X"
    recordar_mac: Optional[bool] = True


class LoginRequest(BaseModel):
    usuario: str
    password: str
    mac_address: Optional[str] = "00:00:00:00:00:00"
    ip_address: Optional[str] = "10.90.0.X"
    recordar_mac: Optional[bool] = True


class CheckMacAutoRequest(BaseModel):
    mac_address: str
    ip_address: Optional[str] = "10.90.0.X"


class RecuperarContrasenaRequest(BaseModel):
    cedula: str
    email: str
    nueva_contrasena: str


class DesvincularRequest(BaseModel):
    mac_address: str
    cedula: Optional[str] = None


class AdminResetPasswordRequest(BaseModel):
    nueva_clave: str


@router.post("/zonapower/api/verificar-datos-cliente")
def api_verificar_datos_cliente(req: VerificarDatosClienteRequest, db: Session = Depends(get_db)):
    """Verifica si la cédula y correo coinciden con un abonado real de Power Link."""
    _ensure_clients_cache_loaded()
    norm_ced = _normalize_cedula(req.cedula)
    if not norm_ced:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Por favor ingresa un número de cédula válido."})

    # 1. Verificar si ya tiene cuenta creada en UsuarioZonaPower
    existing_user = db.query(models.UsuarioZonaPower).filter(models.UsuarioZonaPower.cedula == norm_ced).first()
    if existing_user:
        return {
            "status": "already_registered",
            "message": "Ya posees un usuario registrado en Zona Power. Por favor inicia sesión con tu cédula/correo y contraseña.",
            "nombre": existing_user.nombre or "Abonado Power Link"
        }

    # 2. Verificar en caché de abonados de Power Link (Rubpi / Snapshot)
    client = _clients_cache.get(norm_ced)
    if not client:
        return {
            "status": "not_found",
            "message": "La cédula ingresada no coincide con ningún abonado registrado en Power Link. Si deseas probar el servicio, puedes solicitar una prueba de cortesía."
        }

    # 3. Si se proporcionó correo electrónico, validar coincidencia
    if req.email:
        input_email = req.email.strip().lower()
        cli_emails = client.get("emails", set())
        primary_email = client.get("email", "").lower()

        # Si el contrato no tenía correo registrado previamente, permitir asociar el nuevo
        if not primary_email and not cli_emails:
            return {
                "status": "ok",
                "message": "Cédula validada exitosamente. Define tu contraseña para completar tu registro.",
                "nombre": client.get("name")
            }

        if input_email == primary_email or input_email in cli_emails:
            return {
                "status": "ok",
                "message": "Datos de abonado validados exitosamente.",
                "nombre": client.get("name")
            }
        else:
            return {
                "status": "email_mismatch",
                "message": "El correo ingresado no coincide con el registrado en tu contrato de Power Link. Revisa tus datos o pulsa en Ayuda."
            }

    # Validación inicial de cédula (Paso 1)
    return {
        "status": "client_found",
        "message": f"¡Hola {client.get('name')}! Por favor ingresa el correo registrado en tu contrato para validar tu cuenta.",
        "nombre": client.get("name"),
        "has_registered_email": bool(client.get("email") or client.get("emails"))
    }


@router.post("/zonapower/api/crear-cuenta")
def api_crear_cuenta(req: CrearCuentaRequest, db: Session = Depends(get_db)):
    """Crea un nuevo usuario de Zona Power para un abonado tras validar cédula y correo."""
    _ensure_clients_cache_loaded()
    _limpiar_sesiones_inactivas(db)

    norm_ced = _normalize_cedula(req.cedula)
    if not norm_ced:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Cédula inválida."})

    input_email = req.email.strip().lower()
    if not input_email or "@" not in input_email:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Correo electrónico inválido."})

    pwd = req.password.strip()
    if len(pwd) < 6:
        return JSONResponse(status_code=400, content={"status": "error", "message": "La contraseña debe tener mínimo 6 caracteres."})

    # Verificar existencia previa
    existing_user = db.query(models.UsuarioZonaPower).filter(models.UsuarioZonaPower.cedula == norm_ced).first()
    if existing_user:
        return JSONResponse(status_code=400, content={"status": "already_registered", "message": "Ya tienes una cuenta creada. Por favor inicia sesión."})

    client = _clients_cache.get(norm_ced)
    if not client:
        return JSONResponse(status_code=404, content={"status": "not_found", "message": "Cédula no encontrada en el sistema de abonados de Power Link."})

    cli_emails = client.get("emails", set())
    primary_email = client.get("email", "").lower()
    if primary_email or cli_emails:
        if input_email != primary_email and input_email not in cli_emails:
            return JSONResponse(status_code=400, content={"status": "email_mismatch", "message": "El correo ingresado no coincide con el registrado en tu contrato."})

    now = datetime.utcnow()
    pwd_hash = security.get_password_hash(pwd)

    clean_mac = (req.mac_address or "").strip()
    remember_m = clean_mac if (req.recordar_mac and clean_mac not in ("00:00:00:00:00:00", "")) else None

    nuevo_usuario = models.UsuarioZonaPower(
        cedula=norm_ced,
        email=input_email,
        password_hash=pwd_hash,
        nombre=client.get("name"),
        is_active=True,
        remember_mac=remember_m,
        remember_mac_date=now if remember_m else None,
        created_at=now,
        last_login=now
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    # Transición transparente: Si esta MAC estuvo antes en cortesía, liberar la sesión previa
    if clean_mac and clean_mac != "00:00:00:00:00:00":
        db.query(models.SesionZonaPower).filter(
            models.SesionZonaPower.mac_address.ilike(clean_mac),
            models.SesionZonaPower.tipo_usuario == 'PROSPECTO_CORTESIA'
        ).update({"is_active": False})
        db.commit()

    # Verificar estatus de pago del abonado
    status_str = client.get("status", "").upper()
    if "SUSP" in status_str or "MOROS" in status_str or "INACT" in status_str or "CORTE" in status_str:
        return {
            "status": "insolvente",
            "action": "debt",
            "cliente": {"name": nuevo_usuario.nombre, "status": "SUSPENDIDO"},
            "whatsapp_url": _get_setting(db, "whatsapp_url", "https://wa.link/xow3um"),
            "telefono": _get_setting(db, "telefono_soporte", "+582127203500"),
            "message": "Cuenta creada con éxito, pero tu servicio presenta saldo pendiente. Regulariza tu estatus para navegar sin límites."
        }

    # Verificar límite de dispositivos concurrentes (2 por abonado)
    limite_disp = int(_get_setting(db, "limite_dispositivos", "2"))
    sesiones_activas = db.query(models.SesionZonaPower).filter(
        models.SesionZonaPower.cedula == norm_ced,
        models.SesionZonaPower.is_active == True
    ).all()

    if len(sesiones_activas) >= limite_disp:
        return {
            "status": "limit_reached",
            "action": "limit_reached",
            "dispositivos_activos": len(sesiones_activas),
            "limite_maximo": limite_disp,
            "message": f"Cuenta creada con éxito. Ya posees {limite_disp} dispositivos conectados con esta cédula."
        }

    # Crear sesión activa de abonado ilimitada
    nueva_sesion = models.SesionZonaPower(
        cedula=norm_ced,
        mac_address=clean_mac or "00:00:00:00:00:00",
        ip_address=req.ip_address or "10.90.0.X",
        tipo_usuario="ABONADO",
        is_active=True,
        login_time=now,
        last_seen=now,
        expiry_time=now + timedelta(days=365)
    )
    db.add(nueva_sesion)
    db.commit()
    _ruijie_authorize_mac(clean_mac)

    return {
        "status": "ok",
        "action": "allow",
        "cliente": {"name": nuevo_usuario.nombre},
        "dispositivos_activos": len(sesiones_activas) + 1,
        "message": "¡Cuenta creada exitosamente y conexión autorizada!"
    }


@router.post("/zonapower/api/login")
def api_login(req: LoginRequest, db: Session = Depends(get_db)):
    """Inicia sesión para un abonado con Cédula/Email y Contraseña."""
    abierto, msg_horario = _verificar_horario_operativo(db)
    if not abierto:
        return {"status": "out_of_hours", "message": msg_horario}

    _ensure_clients_cache_loaded()
    _limpiar_sesiones_inactivas(db)

    ident = req.usuario.strip()
    if not ident or not req.password:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Por favor ingresa usuario y contraseña."})

    norm_ced = _normalize_cedula(ident)
    user_acc = None
    if norm_ced:
        user_acc = db.query(models.UsuarioZonaPower).filter(models.UsuarioZonaPower.cedula == norm_ced).first()

    if not user_acc and "@" in ident:
        user_acc = db.query(models.UsuarioZonaPower).filter(models.UsuarioZonaPower.email.ilike(ident.lower())).first()

    if not user_acc:
        return {
            "status": "not_registered",
            "message": "Usuario no encontrado. Si eres cliente de Power Link, pulsa en 'Regístrate Aquí'."
        }

    if not security.verify_password(req.password, user_acc.password_hash):
        return {
            "status": "invalid_credentials",
            "message": "Contraseña incorrecta. Verifica tus datos o usa '¿Olvidaste tu Contraseña?'."
        }

    if not user_acc.is_active:
        return {
            "status": "inactive",
            "message": "Tu cuenta de Zona Power se encuentra desactivada. Contacta a soporte técnico."
        }

    now = datetime.utcnow()
    clean_mac = (req.mac_address or "").strip()

    # Actualizar recordatorio de MAC por 7 días si se seleccionó
    if req.recordar_mac and clean_mac and clean_mac != "00:00:00:00:00:00":
        user_acc.remember_mac = clean_mac
        user_acc.remember_mac_date = now
    user_acc.last_login = now
    db.commit()

    # Transición transparente: Si este MAC estuvo antes en cortesía, liberarlo
    if clean_mac and clean_mac != "00:00:00:00:00:00":
        db.query(models.SesionZonaPower).filter(
            models.SesionZonaPower.mac_address.ilike(clean_mac),
            models.SesionZonaPower.tipo_usuario == 'PROSPECTO_CORTESIA'
        ).update({"is_active": False})
        db.commit()

    # Verificar estatus en snapshot de Rubpi
    client = _clients_cache.get(user_acc.cedula, {})
    status_str = client.get("status", "").upper()
    if "SUSP" in status_str or "MOROS" in status_str or "INACT" in status_str or "CORTE" in status_str:
        return {
            "status": "insolvente",
            "action": "debt",
            "cliente": {"name": user_acc.nombre or client.get("name"), "status": "SUSPENDIDO"},
            "whatsapp_url": _get_setting(db, "whatsapp_url", "https://wa.link/xow3um"),
            "telefono": _get_setting(db, "telefono_soporte", "+582127203500"),
            "message": "Tu cuenta presenta saldo pendiente. Regulariza tu estatus para navegar sin límites."
        }

    # Verificar límite de 2 dispositivos concurrentes
    limite_disp = int(_get_setting(db, "limite_dispositivos", "2"))
    sesiones_activas = db.query(models.SesionZonaPower).filter(
        models.SesionZonaPower.cedula == user_acc.cedula,
        models.SesionZonaPower.is_active == True
    ).all()

    sesion_existente = next((s for s in sesiones_activas if clean_mac and s.mac_address.lower() == clean_mac.lower()), None)
    if sesion_existente:
        sesion_existente.last_seen = now
        sesion_existente.ip_address = req.ip_address or sesion_existente.ip_address
        db.commit()
        _ruijie_authorize_mac(clean_mac)
        return {
            "status": "ok",
            "action": "allow",
            "cliente": {"name": user_acc.nombre or client.get("name")},
            "dispositivos_activos": len(sesiones_activas),
            "message": "Sesión renovada con éxito."
        }

    if len(sesiones_activas) >= limite_disp:
        return {
            "status": "limit_reached",
            "action": "limit_reached",
            "dispositivos_activos": len(sesiones_activas),
            "limite_maximo": limite_disp,
            "message": f"Ya tienes {limite_disp} dispositivos conectados. Desconecta uno para acceder."
        }

    nueva_sesion = models.SesionZonaPower(
        cedula=user_acc.cedula,
        mac_address=clean_mac or "00:00:00:00:00:00",
        ip_address=req.ip_address or "10.90.0.X",
        tipo_usuario="ABONADO",
        is_active=True,
        login_time=now,
        last_seen=now,
        expiry_time=now + timedelta(days=365)
    )
    db.add(nueva_sesion)
    db.commit()
    _ruijie_authorize_mac(clean_mac)

    return {
        "status": "ok",
        "action": "allow",
        "cliente": {"name": user_acc.nombre or client.get("name")},
        "dispositivos_activos": len(sesiones_activas) + 1,
        "message": "¡Inicio de sesión exitoso! Bienvenido a Zona Power."
    }


@router.post("/zonapower/api/check-mac-auto")
def api_check_mac_auto(req: CheckMacAutoRequest, db: Session = Depends(get_db)):
    """Verifica si el dispositivo tiene MAC recordada o sesión activa."""
    abierto, msg_horario = _verificar_horario_operativo(db)
    if not abierto:
        return {"status": "out_of_hours", "message": msg_horario}

    _ensure_clients_cache_loaded()
    _limpiar_sesiones_inactivas(db)

    clean_mac = (req.mac_address or "").strip()
    if not clean_mac or clean_mac in ("00:00:00:00:00:00", ""):
        return {"status": "none"}

    now = datetime.utcnow()

    # 1. Buscar si la MAC está guardada en UsuarioZonaPower
    user_acc = db.query(models.UsuarioZonaPower).filter(
        models.UsuarioZonaPower.remember_mac.ilike(clean_mac),
        models.UsuarioZonaPower.is_active == True
    ).first()

    if user_acc:
        # Vencimiento configurable de la MAC guardada
        dias_abonado = int(_get_setting(db, "dias_recordar_mac_abonado", "7"))
        if user_acc.remember_mac_date and (now - user_acc.remember_mac_date).total_seconds() > (dias_abonado * 86400):
            user_acc.remember_mac = None
            user_acc.remember_mac_date = None
            db.commit()
            return {
                "status": "expired",
                "message": f"Tu sesión guardada de {dias_abonado} días ha finalizado por seguridad. Por favor ingresa tu contraseña."
            }

        # Verificar solvencia del cliente
        client = _clients_cache.get(user_acc.cedula, {})
        status_str = client.get("status", "").upper()
        if "SUSP" in status_str or "MOROS" in status_str or "INACT" in status_str or "CORTE" in status_str:
            return {
                "status": "insolvente",
                "action": "debt",
                "cliente": {"name": user_acc.nombre or client.get("name"), "status": "SUSPENDIDO"},
                "whatsapp_url": _get_setting(db, "whatsapp_url", "https://wa.link/xow3um"),
                "telefono": _get_setting(db, "telefono_soporte", "+582127203500")
            }

        limite_disp = int(_get_setting(db, "limite_dispositivos", "2"))
        sesiones_activas = db.query(models.SesionZonaPower).filter(
            models.SesionZonaPower.cedula == user_acc.cedula,
            models.SesionZonaPower.is_active == True
        ).all()

        sesion_existente = next((s for s in sesiones_activas if s.mac_address.lower() == clean_mac.lower()), None)
        if sesion_existente:
            sesion_existente.last_seen = now
            sesion_existente.ip_address = req.ip_address or sesion_existente.ip_address
            db.commit()
        elif len(sesiones_activas) < limite_disp:
            ns = models.SesionZonaPower(
                cedula=user_acc.cedula,
                mac_address=clean_mac,
                ip_address=req.ip_address or "10.90.0.X",
                tipo_usuario="ABONADO",
                is_active=True,
                login_time=now,
                last_seen=now,
                expiry_time=now + timedelta(days=365)
            )
            db.add(ns)
            db.commit()
            sesiones_activas.append(ns)

        _ruijie_authorize_mac(clean_mac)
        return {
            "status": "ok",
            "action": "allow",
            "cliente": {"name": user_acc.nombre or client.get("name"), "cedula": user_acc.cedula},
            "dispositivos_activos": len(sesiones_activas),
            "message": "Dispositivo reconocido automáticamente."
        }

    # 2. Verificar si tiene cortesía activa no expirada
    ses_cortesia = db.query(models.SesionZonaPower).filter(
        models.SesionZonaPower.mac_address.ilike(clean_mac),
        models.SesionZonaPower.tipo_usuario == 'PROSPECTO_CORTESIA',
        models.SesionZonaPower.is_active == True
    ).first()

    if ses_cortesia:
        if ses_cortesia.expiry_time and now > ses_cortesia.expiry_time:
            ses_cortesia.is_active = False
            db.commit()
            _ruijie_deauthorize_mac(clean_mac)
            return {"status": "none"}

        segundos_restantes = max(0, int((ses_cortesia.expiry_time - now).total_seconds())) if ses_cortesia.expiry_time else 0
        return {
            "status": "cortesia_activa",
            "segundos_restantes": segundos_restantes,
            "minutos_restantes": int(segundos_restantes / 60)
        }

    return {"status": "none"}


@router.post("/zonapower/api/desvincular-dispositivo")
def api_desvincular_dispositivo(req: DesvincularRequest, db: Session = Depends(get_db)):
    """El cliente desvincula y borra su dispositivo (libera MAC y cupo de conexión)."""
    clean_mac = (req.mac_address or "").strip()
    if not clean_mac or clean_mac in ("00:00:00:00:00:00", ""):
        return JSONResponse(status_code=400, content={"status": "error", "message": "Dirección MAC no válida."})

    # Borrar recordatorio en usuarios
    users = db.query(models.UsuarioZonaPower).filter(models.UsuarioZonaPower.remember_mac.ilike(clean_mac)).all()
    for u in users:
        u.remember_mac = None
        u.remember_mac_date = None

    # Desactivar sesiones activas para esta MAC
    db.query(models.SesionZonaPower).filter(models.SesionZonaPower.mac_address.ilike(clean_mac)).update({"is_active": False})
    db.commit()

    # Revocar de inmediato en el Gateway Ruijie
    _ruijie_deauthorize_mac(clean_mac)

    return {
        "status": "ok",
        "message": "Dispositivo desvinculado con éxito. Tu cupo de conexión ha sido liberado."
    }


@router.post("/zonapower/api/recuperar-contrasena")
def api_recuperar_contrasena(req: RecuperarContrasenaRequest, db: Session = Depends(get_db)):
    """Permite al abonado restablecer su contraseña validando Cédula y Correo."""
    _ensure_clients_cache_loaded()
    norm_ced = _normalize_cedula(req.cedula)
    if not norm_ced:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Cédula inválida."})

    input_email = req.email.strip().lower()
    if not input_email or "@" not in input_email:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Correo electrónico inválido."})

    if len(req.nueva_contrasena.strip()) < 6:
        return JSONResponse(status_code=400, content={"status": "error", "message": "La nueva contraseña debe tener mínimo 6 caracteres."})

    user_acc = db.query(models.UsuarioZonaPower).filter(models.UsuarioZonaPower.cedula == norm_ced).first()
    client = _clients_cache.get(norm_ced)

    valid = False
    if user_acc and user_acc.email.lower() == input_email:
        valid = True
    elif client:
        primary_email = client.get("email", "").lower()
        cli_emails = client.get("emails", set())
        if input_email == primary_email or input_email in cli_emails:
            valid = True

    if not valid:
        return {
            "status": "error",
            "message": "Los datos ingresados no coinciden con ningún abonado registrado con ese correo."
        }

    pwd_hash = security.get_password_hash(req.nueva_contrasena.strip())

    if user_acc:
        user_acc.password_hash = pwd_hash
        user_acc.email = input_email
        db.commit()
    else:
        user_acc = models.UsuarioZonaPower(
            cedula=norm_ced,
            email=input_email,
            password_hash=pwd_hash,
            nombre=client.get("name") if client else "Abonado Power Link",
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(user_acc)
        db.commit()

    return {
        "status": "ok",
        "message": "¡Contraseña actualizada con éxito! Ahora puedes iniciar sesión en Zona Power."
    }


@router.get("/zonapower/api/cuentas/buscar")
def api_buscar_cuentas(q: str = "", db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_user)):
    """Búsqueda de cuentas de abonados registradas en Zona Power."""
    query = db.query(models.UsuarioZonaPower)
    term = q.strip()
    if term:
        query = query.filter(
            (models.UsuarioZonaPower.cedula.ilike(f"%{term}%")) |
            (models.UsuarioZonaPower.email.ilike(f"%{term}%")) |
            (models.UsuarioZonaPower.nombre.ilike(f"%{term}%"))
        )
    cuentas = query.order_by(models.UsuarioZonaPower.created_at.desc()).limit(100).all()
    return [c.to_dict() for c in cuentas]


@router.post("/zonapower/api/cuentas/{cuenta_id}/reset-password")
def api_admin_reset_password(cuenta_id: int, req: AdminResetPasswordRequest, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_user)):
    """El operador restablece la contraseña de una cuenta de Zona Power."""
    cuenta = db.query(models.UsuarioZonaPower).filter(models.UsuarioZonaPower.id == cuenta_id).first()
    if not cuenta:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Cuenta no encontrada."})

    if len(req.nueva_clave.strip()) < 6:
        return JSONResponse(status_code=400, content={"status": "error", "message": "La nueva contraseña debe tener mínimo 6 caracteres."})

    cuenta.password_hash = security.get_password_hash(req.nueva_clave.strip())
    db.commit()
    return {"status": "ok", "message": f"Contraseña actualizada exitosamente para {cuenta.nombre or cuenta.cedula}."}


@router.post("/zonapower/api/cuentas/{cuenta_id}/desvincular-macs")
def api_admin_desvincular_macs(cuenta_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_user)):
    """El operador desvincula todos los dispositivos de una cuenta."""
    cuenta = db.query(models.UsuarioZonaPower).filter(models.UsuarioZonaPower.id == cuenta_id).first()
    if not cuenta:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Cuenta no encontrada."})

    old_mac = cuenta.remember_mac
    cuenta.remember_mac = None
    cuenta.remember_mac_date = None

    # Desconectar sesiones activas de esta cédula
    sesiones = db.query(models.SesionZonaPower).filter(
        models.SesionZonaPower.cedula == cuenta.cedula,
        models.SesionZonaPower.is_active == True
    ).all()
    for s in sesiones:
        s.is_active = False
        _ruijie_deauthorize_mac(s.mac_address)
    if old_mac:
        _ruijie_deauthorize_mac(old_mac)

    db.commit()
    return {"status": "ok", "message": f"Dispositivos desvinculados exitosamente para la cédula {cuenta.cedula}."}


@router.post("/zonapower/api/verificar-cedula")
def verificar_cedula(req: CedulaCheckRequest, db: Session = Depends(get_db)):
    """
    Verifica el estado del usuario en el snapshot de Rubpi/Intranet.
    Aplica políticas:
      - Solvente: Conexión indefinida, max 2 dispositivos, desconexión por inactividad a 30 min.
      - Insolvente: Redirección a WhatsApp y soporte.
      - No registrado: Formulario de prospecto para 30 min de cortesía.
    """
    _ensure_clients_cache_loaded()
    _limpiar_sesiones_inactivas(db)

    norm_ced = _normalize_cedula(req.cedula)
    if not norm_ced:
        return JSONResponse(status_code=400, content={"error": "Cédula inválida"})

    limite_disp = int(_get_setting(db, "limite_dispositivos", "2"))
    t_inact = int(_get_setting(db, "tiempo_inactividad_min", "30"))

    # Buscar en caché de clientes
    client = _clients_cache.get(norm_ced)

    if not client:
        return {
            "status": "not_found",
            "action": "register_prospect",
            "message": "Cédula no encontrada en el sistema de abonados. Ofrecer prueba de cortesía."
        }

    status_str = client.get("status", "").upper()

    # Si el cliente está SUSPENDIDO o MOROSO
    if "SUSP" in status_str or "MOROS" in status_str or "INACT" in status_str or "CORTE" in status_str:
        return {
            "status": "insolvente",
            "action": "debt",
            "cliente": {
                "name": client.get("name"),
                "status": "SUSPENDIDO"
            },
            "whatsapp_url": _get_setting(db, "whatsapp_url", "https://wa.link/xow3um"),
            "telefono": _get_setting(db, "telefono_soporte", "+582127203500"),
            "message": "Tu cuenta presenta saldo pendiente. Comunícate para regularizar tu estatus."
        }

    # Si el cliente está ACTIVO / SOLVENTE
    # Verificar concurrencia (máximo 2 dispositivos)
    sesiones_activas = db.query(models.SesionZonaPower).filter(
        models.SesionZonaPower.cedula == norm_ced,
        models.SesionZonaPower.is_active == True
    ).all()

    # Si la misma MAC ya tiene sesión activa, actualizar su timestamp
    sesion_existente = next((s for s in sesiones_activas if s.mac_address.lower() == req.mac_address.lower()), None)

    now = datetime.utcnow()
    if sesion_existente:
        sesion_existente.last_seen = now
        sesion_existente.ip_address = req.ip_address or sesion_existente.ip_address
        db.commit()
        _ruijie_authorize_mac(req.mac_address)
        return {
            "status": "solvente",
            "action": "allow",
            "cliente": client,
            "dispositivos_activos": len(sesiones_activas),
            "message": "Sesión renovada con éxito."
        }

    # Si es una MAC nueva y ya alcanzó el límite (2 dispositivos)
    if len(sesiones_activas) >= limite_disp:
        return {
            "status": "limit_reached",
            "action": "limit_reached",
            "dispositivos_activos": len(sesiones_activas),
            "limite_maximo": limite_disp,
            "message": f"Ya tienes {limite_disp} dispositivos conectados con esta cédula."
        }

    # Crear nueva sesión activa
    nueva_sesion = models.SesionZonaPower(
        cedula=norm_ced,
        mac_address=req.mac_address or "00:00:00:00:00:00",
        ip_address=req.ip_address or "10.90.0.X",
        tipo_usuario="ABONADO",
        is_active=True,
        login_time=now,
        last_seen=now,
        expiry_time=now + timedelta(days=365) # Conexión indefinida para solventes
    )
    db.add(nueva_sesion)
    db.commit()
    _ruijie_authorize_mac(req.mac_address)

    return {
        "status": "solvente",
        "action": "allow",
        "cliente": client,
        "dispositivos_activos": len(sesiones_activas) + 1,
        "message": "Acceso ilimitado concedido."
    }


class ProspectoRequest(BaseModel):
    cedula: str
    nombre: str
    apellido: str
    telefono: str
    estado: str
    municipio: str
    zona_sector: str
    punto_origen: Optional[str] = "CC La Colina"
    mac_address: Optional[str] = "00:00:00:00:00:00"
    ip_address: Optional[str] = "10.90.0.X"


@router.post("/zonapower/api/registrar-prospecto")
def registrar_prospecto(req: ProspectoRequest, db: Session = Depends(get_db)):
    """
    Registra los datos de un prospecto no abonado,
    le activa minutos de cortesía y envía correo a bcarrero@powerlink.com.ve.
    """
    abierto, msg_horario = _verificar_horario_operativo(db)
    if not abierto:
        return {"status": "out_of_hours", "message": msg_horario}

    norm_ced = _normalize_cedula(req.cedula)
    now = datetime.utcnow()
    t_cortesia = int(_get_setting(db, "tiempo_cortesia_min", "30"))

    # Verificar si es abonado en el sistema
    _ensure_clients_cache_loaded()
    if norm_ced in _clients_cache:
        cli = _clients_cache[norm_ced]
        return {
            "status": "is_subscriber",
            "message": f"¡Hola {cli.get('name')}! Tu cédula pertenece a un abonado de Power Link. Pulsa en 'Soy Cliente' para crear tu cuenta o iniciar sesión y disfrutar de navegación ilimitada sin restricción de tiempo."
        }

    # Regla de reconexión configurable para prospectos
    dias_reintento = int(_get_setting(db, "dias_reintento_cortesia", "7"))
    limite_dias_atras = now - timedelta(days=dias_reintento)
    clean_mac = (req.mac_address or "").strip()

    if clean_mac and clean_mac not in ("00:00:00:00:00:00", ""):
        sesion_previa = db.query(models.SesionZonaPower).filter(
            models.SesionZonaPower.mac_address.ilike(clean_mac),
            models.SesionZonaPower.tipo_usuario == 'PROSPECTO_CORTESIA',
            models.SesionZonaPower.login_time >= limite_dias_atras
        ).order_by(models.SesionZonaPower.login_time.desc()).first()

        if sesion_previa:
            segundos_pasados = (now - sesion_previa.login_time).total_seconds()
            segundos_restantes = max(0, (dias_reintento * 86400) - segundos_pasados)
            dias_restantes = max(1, int(segundos_restantes // 86400) + 1)
            return {
                "status": "already_used",
                "message": f"Este dispositivo ya disfrutó de la prueba gratuita. Podrás solicitar un nuevo acceso de cortesía en {dias_restantes} día(s).",
                "dias_restantes": dias_restantes,
                "whatsapp_url": _get_setting(db, "whatsapp_url", "https://wa.link/xow3um"),
                "telefono": _get_setting(db, "telefono_soporte", "+582127203500")
            }

    # 1. Guardar prospecto en Base de Datos con estación configurable
    estacion_actual = _get_setting(db, "nombre_estacion", "CC La Colina")
    prospecto = models.ProspectoZonaPower(
        cedula=norm_ced,
        nombre=req.nombre.strip(),
        apellido=req.apellido.strip(),
        telefono=req.telefono.strip(),
        estado=req.estado.strip(),
        municipio=req.municipio.strip(),
        zona_sector=req.zona_sector.strip(),
        punto_origen=req.punto_origen or estacion_actual,
        estatus="NUEVO",
        created_at=now
    )
    db.add(prospecto)
    db.commit()
    db.refresh(prospecto)

    # 2. Activar sesión de cortesía (30 min)
    exp_time = now + timedelta(minutes=t_cortesia)
    sesion_cortesia = models.SesionZonaPower(
        cedula=norm_ced,
        mac_address=req.mac_address or "00:00:00:00:00:00",
        ip_address=req.ip_address or "10.90.0.X",
        tipo_usuario="PROSPECTO_CORTESIA",
        is_active=True,
        login_time=now,
        last_seen=now,
        expiry_time=exp_time
    )
    db.add(sesion_cortesia)
    db.commit()
    _ruijie_authorize_mac(req.mac_address)

    # 3. Enviar correo de notificación a bcarrero@powerlink.com.ve
    email_dest = "bcarrero@powerlink.com.ve"
    cfg_email = _get_setting(db, "email_notificaciones", "")
    destinatarios = [email_dest]
    if cfg_email and cfg_email != email_dest and "@" in cfg_email:
        destinatarios.append(cfg_email)

    asunto = f"[ZONA POWER] Nuevo Prospecto - {req.nombre} {req.apellido} ({req.municipio}, {req.estado})"
    cuerpo_html = f"""
    <div style="font-family: Arial, sans-serif; background-color: #090D16; padding: 25px; color: #f8fafc;">
        <div style="max-width: 600px; margin: 0 auto; background: #0F172A; border-radius: 12px; border: 1px solid rgba(59, 130, 246, 0.3); overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
            <div style="background: linear-gradient(135deg, #1E3A8A 0%, #0F172A 100%); padding: 20px; border-bottom: 2px solid #FFCC00; text-align: center;">
                <h2 style="margin: 0; font-size: 20px; color: #FFFFFF;"><span style="color: #FFCC00;">⚡ ZONA POWER</span> — Nuevo Prospecto</h2>
                <p style="margin: 6px 0 0 0; font-size: 12px; color: #93C5FD;">Red de Acceso Público de Power Link C.A.</p>
            </div>
            <div style="padding: 24px; font-size: 14px; line-height: 1.6; color: #E2E8F0;">
                <p style="margin-top: 0;">Se ha captado un nuevo usuario interesado en el servicio de Internet de fibra óptica:</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                    <tr style="border-bottom: 1px solid #1E293B;">
                        <td style="padding: 10px 0; font-weight: bold; width: 140px; color: #94A3B8;">Cédula:</td>
                        <td style="padding: 10px 0; font-weight: bold; color: #FFFFFF;">{norm_ced}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E293B;">
                        <td style="padding: 10px 0; font-weight: bold; color: #94A3B8;">Nombre Completo:</td>
                        <td style="padding: 10px 0; color: #FFFFFF;">{req.nombre} {req.apellido}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E293B;">
                        <td style="padding: 10px 0; font-weight: bold; color: #94A3B8;">Teléfono (WhatsApp):</td>
                        <td style="padding: 10px 0;">
                            <a href="https://wa.me/58{req.telefono.replace('-', '').replace(' ', '').lstrip('0')}" style="color: #10B981; font-weight: bold; text-decoration: none;">
                                {req.telefono} (Abrir WhatsApp)
                            </a>
                        </td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E293B;">
                        <td style="padding: 10px 0; font-weight: bold; color: #94A3B8;">Estado:</td>
                        <td style="padding: 10px 0; color: #FFFFFF;">{req.estado}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E293B;">
                        <td style="padding: 10px 0; font-weight: bold; color: #94A3B8;">Municipio:</td>
                        <td style="padding: 10px 0; color: #FFFFFF;">{req.municipio}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E293B;">
                        <td style="padding: 10px 0; font-weight: bold; color: #94A3B8;">Zona / Sector:</td>
                        <td style="padding: 10px 0; color: #FFFFFF;">{req.zona_sector}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E293B;">
                        <td style="padding: 10px 0; font-weight: bold; color: #94A3B8;">Punto de Conexión:</td>
                        <td style="padding: 10px 0; color: #38BDF8;">{req.punto_origen or 'CC La Colina'}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E293B;">
                        <td style="padding: 10px 0; font-weight: bold; color: #94A3B8;">Cortesía Asignada:</td>
                        <td style="padding: 10px 0; color: #FCD34D;">{t_cortesia} Minutos</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold; color: #94A3B8;">Fecha y Hora:</td>
                        <td style="padding: 10px 0; color: #94A3B8;">{now.strftime('%d/%m/%Y %I:%M %p')} UTC</td>
                    </tr>
                </table>
            </div>
            <div style="background-color: #090D16; padding: 14px 20px; text-align: center; font-size: 11px; color: #64748B; border-top: 1px solid #1E293B;">
                Notificación generada automáticamente por el módulo Zona Power — Intranet Power Link C.A.
            </div>
        </div>
    </div>
    """

    for dest in destinatarios:
        try:
            send_email_message(to_email=dest, subject=asunto, html_content=cuerpo_html)
        except Exception as e:
            print(f"[ZONA POWER] Error despachando correo a {dest}: {e}")

    return {
        "status": "ok",
        "action": "allow",
        "minutos_cortesia": t_cortesia,
        "message": f"Prospecto registrado y cortesía de {t_cortesia} minutos activada"
    }


# ==========================================
# GESTIÓN DE CONFIGURACIÓN & SESIONES (ADMIN)
# ==========================================

class ConfigUpdateRequest(BaseModel):
    tiempo_cortesia_min: Optional[str] = None
    tiempo_inactividad_min: Optional[str] = None
    limite_dispositivos: Optional[str] = None
    whatsapp_url: Optional[str] = None
    telefono_soporte: Optional[str] = None
    email_notificaciones: Optional[str] = None
    ssid_nombre: Optional[str] = None
    portal_activo: Optional[str] = None
    limite_bajada_mbps: Optional[str] = None
    limite_subida_mbps: Optional[str] = None
    modo_qos: Optional[str] = None
    capacidad_estacion_mbps: Optional[str] = None
    piso_minimo_cliente_mbps: Optional[str] = None
    dias_reintento_cortesia: Optional[str] = None
    dias_recordar_mac_abonado: Optional[str] = None
    nombre_estacion: Optional[str] = None
    url_redireccion_destino: Optional[str] = None
    horario_habilitado: Optional[str] = None
    horario_inicio: Optional[str] = None
    horario_fin: Optional[str] = None
    banner_activo: Optional[str] = None
    banner_tipo: Optional[str] = None
    banner_texto: Optional[str] = None
    banner_url: Optional[str] = None
    gateway_ip: Optional[str] = None


@router.post("/zonapower/api/config")
def actualizar_configuracion(cfg: ConfigUpdateRequest, db: Session = Depends(get_db)):
    """Actualiza los parámetros dinámicos de Zona Power."""
    datos = cfg.dict(exclude_unset=True)
    for k, v in datos.items():
        if v is not None:
            _set_setting(db, k, str(v))

    gw = _get_setting(db, "gateway_ip", "192.168.110.1")
    # Si se modificó la política de tráfico o ancho de banda o la IP del gateway, sincronizar inmediatamente con Ruijie
    if any(k in datos for k in ["modo_qos", "capacidad_estacion_mbps", "piso_minimo_cliente_mbps", "limite_bajada_mbps", "limite_subida_mbps", "gateway_ip"]):
        modo = datos.get("modo_qos") or _get_setting(db, "modo_qos", "dinamico")
        cap = datos.get("capacidad_estacion_mbps") or _get_setting(db, "capacidad_estacion_mbps", "1000")
        piso = datos.get("piso_minimo_cliente_mbps") or _get_setting(db, "piso_minimo_cliente_mbps", "5")
        down = datos.get("limite_bajada_mbps") or _get_setting(db, "limite_bajada_mbps", "5")
        up = datos.get("limite_subida_mbps") or _get_setting(db, "limite_subida_mbps", "3")
        _ruijie_apply_traffic_policy(modo, cap, piso, down, up, gw)

    return {"status": "ok", "message": "Configuración y política de tráfico sincronizadas exitosamente con Ruijie"}


@router.post("/zonapower/api/sesiones/{sesion_id}/desconectar")
def desconectar_sesion_manual(sesion_id: int, db: Session = Depends(get_db)):
    """Desconecta y expulsa manualmente un dispositivo conectado."""
    sesion = db.query(models.SesionZonaPower).filter(models.SesionZonaPower.id == sesion_id).first()
    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    sesion.is_active = False
    db.commit()
    return {"status": "ok", "message": f"Sesión de {sesion.cedula} desconectada"}


class ProspectoStatusUpdate(BaseModel):
    estatus: str


@router.post("/zonapower/api/prospectos/{prospecto_id}/actualizar")
def actualizar_estatus_prospecto(prospecto_id: int, req: ProspectoStatusUpdate, db: Session = Depends(get_db)):
    """Actualiza el estatus comercial de un prospecto."""
    prosp = db.query(models.ProspectoZonaPower).filter(models.ProspectoZonaPower.id == prospecto_id).first()
    if not prosp:
        raise HTTPException(status_code=404, detail="Prospecto no encontrado")
    prosp.estatus = req.estatus.upper()
    db.commit()
    return {"status": "ok", "nuevo_estatus": prosp.estatus}


@router.get("/admin/zonapower/prospectos/export-csv")
def exportar_prospectos_csv(db: Session = Depends(get_db)):
    """Descarga la base de datos de prospectos captados en CSV."""
    prospectos = db.query(models.ProspectoZonaPower).order_by(models.ProspectoZonaPower.created_at.desc()).all()
    for p in prospectos:
        p.clean_phone = re.sub(r'[^0-9]', '', p.telefono or '').lstrip('0')

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Fecha_Captura", "Cedula", "Nombre", "Apellido", "Telefono",
        "Estado", "Municipio", "Zona_Sector", "Punto_Origen", "Estatus"
    ])

    for p in prospectos:
        writer.writerow([
            p.id,
            p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else "",
            p.cedula,
            p.nombre,
            p.apellido,
            p.telefono,
            p.estado,
            p.municipio,
            p.zona_sector,
            p.punto_origen,
            p.estatus
        ])

    output.seek(0)
    filename = f"prospectos_zona_power_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ==========================================
# VISTA INTEGRAL EN OPERACIONES (INTRANET)
# ==========================================

@router.get("/admin/zonapower", response_class=HTMLResponse)
@router.get("/admin/zonapower/prospectos", response_class=HTMLResponse)
def redirect_to_operaciones_zonapower():
    """Redirecciona al módulo oficial de Operaciones."""
    return RedirectResponse(url="/admin/operaciones/zonapower")


def get_zonapower_dashboard_context(request: Request, user: models.User, db: Session) -> dict:
    """Genera el contexto para la plantilla de Operaciones Zona Power (alta velocidad)."""
    _ensure_clients_cache_loaded()

    # Cargar configuraciones en una sola consulta
    all_configs = {c.clave: c.valor for c in db.query(models.ConfigZonaPower).all()}

    # Limpiar sesiones expiradas solo si hay registros caducados
    try:
        t_inact = int(all_configs.get("tiempo_inactividad_min", DEFAULTS_CONFIG["tiempo_inactividad_min"]))
        limite = datetime.utcnow() - timedelta(minutes=t_inact)
        expiradas = db.query(models.SesionZonaPower).filter(
            models.SesionZonaPower.is_active == True,
            models.SesionZonaPower.last_seen < limite
        ).update({"is_active": False})
        if expiradas > 0:
            db.commit()
    except Exception as e:
        print(f"[ZONA POWER] Error en barrido: {e}")

    prospectos = db.query(models.ProspectoZonaPower).order_by(models.ProspectoZonaPower.created_at.desc()).all()
    for p in prospectos:
        p.clean_phone = re.sub(r'[^0-9]', '', p.telefono or '').lstrip('0')

    sesiones_raw = db.query(models.SesionZonaPower).filter(models.SesionZonaPower.is_active == True).order_by(models.SesionZonaPower.last_seen.desc()).all()

    sesiones_activas = []
    for s in sesiones_raw:
        cli = _clients_cache.get(s.cedula, {})
        nombre = cli.get("name") or ("Cortesía Prospecto" if s.tipo_usuario == "PROSPECTO_CORTESIA" else "Abonado Power Link")
        sesiones_activas.append({
            "id": s.id,
            "cedula": s.cedula,
            "nombre_cliente": nombre,
            "mac_address": s.mac_address,
            "ip_address": s.ip_address,
            "tipo_usuario": s.tipo_usuario,
            "login_time": s.login_time,
            "last_seen": s.last_seen
        })

    cuentas = db.query(models.UsuarioZonaPower).order_by(models.UsuarioZonaPower.created_at.desc()).all()
    total_cuentas = len(cuentas)

    total_prospectos = len(prospectos)
    total_conectados = len(sesiones_activas)
    abonados_conectados = sum(1 for s in sesiones_activas if s["tipo_usuario"] == "ABONADO")
    cortesias_activas = total_conectados - abonados_conectados

    cfg_cortesia = all_configs.get("tiempo_cortesia_min", DEFAULTS_CONFIG["tiempo_cortesia_min"])
    cfg_inactividad = all_configs.get("tiempo_inactividad_min", DEFAULTS_CONFIG["tiempo_inactividad_min"])
    cfg_limite = all_configs.get("limite_dispositivos", DEFAULTS_CONFIG["limite_dispositivos"])
    cfg_wa = all_configs.get("whatsapp_url", DEFAULTS_CONFIG["whatsapp_url"])
    cfg_tlf = all_configs.get("telefono_soporte", DEFAULTS_CONFIG["telefono_soporte"])
    cfg_email = all_configs.get("email_notificaciones", DEFAULTS_CONFIG["email_notificaciones"])
    cfg_ssid = all_configs.get("ssid_nombre", DEFAULTS_CONFIG["ssid_nombre"])
    cfg_portal = all_configs.get("portal_activo", DEFAULTS_CONFIG["portal_activo"]) == "true"
    cfg_bajada_mbps = all_configs.get("limite_bajada_mbps", DEFAULTS_CONFIG["limite_bajada_mbps"])
    cfg_subida_mbps = all_configs.get("limite_subida_mbps", DEFAULTS_CONFIG["limite_subida_mbps"])
    cfg_modo_qos = all_configs.get("modo_qos", DEFAULTS_CONFIG["modo_qos"])
    cfg_capacidad = all_configs.get("capacidad_estacion_mbps", DEFAULTS_CONFIG["capacidad_estacion_mbps"])
    cfg_piso = all_configs.get("piso_minimo_cliente_mbps", DEFAULTS_CONFIG["piso_minimo_cliente_mbps"])
    cfg_dias_cortesia = all_configs.get("dias_reintento_cortesia", DEFAULTS_CONFIG["dias_reintento_cortesia"])
    cfg_dias_abonado = all_configs.get("dias_recordar_mac_abonado", DEFAULTS_CONFIG["dias_recordar_mac_abonado"])
    cfg_nombre_estacion = all_configs.get("nombre_estacion", DEFAULTS_CONFIG["nombre_estacion"])
    cfg_url_destino = all_configs.get("url_redireccion_destino", DEFAULTS_CONFIG["url_redireccion_destino"])
    cfg_horario_hab = all_configs.get("horario_habilitado", DEFAULTS_CONFIG["horario_habilitado"]) == "true"
    cfg_horario_ini = all_configs.get("horario_inicio", DEFAULTS_CONFIG["horario_inicio"])
    cfg_horario_fin = all_configs.get("horario_fin", DEFAULTS_CONFIG["horario_fin"])
    cfg_banner_act = all_configs.get("banner_activo", DEFAULTS_CONFIG["banner_activo"]) == "true"
    cfg_banner_tipo = all_configs.get("banner_tipo", DEFAULTS_CONFIG["banner_tipo"])
    cfg_banner_texto = all_configs.get("banner_texto", DEFAULTS_CONFIG["banner_texto"])
    cfg_banner_url = all_configs.get("banner_url", DEFAULTS_CONFIG["banner_url"])
    cfg_gateway_ip = all_configs.get("gateway_ip", DEFAULTS_CONFIG["gateway_ip"])

    return {
        "cfg_dias_cortesia": cfg_dias_cortesia,
        "cfg_dias_abonado": cfg_dias_abonado,
        "cfg_nombre_estacion": cfg_nombre_estacion,
        "cfg_url_destino": cfg_url_destino,
        "cfg_horario_hab": cfg_horario_hab,
        "cfg_horario_ini": cfg_horario_ini,
        "cfg_horario_fin": cfg_horario_fin,
        "cfg_banner_act": cfg_banner_act,
        "cfg_banner_tipo": cfg_banner_tipo,
        "cfg_banner_texto": cfg_banner_texto,
        "cfg_banner_url": cfg_banner_url,
        "cfg_gateway_ip": cfg_gateway_ip,
        "cfg_modo_qos": cfg_modo_qos,
        "cfg_capacidad": cfg_capacidad,
        "cfg_piso": cfg_piso,
        "cfg_bajada_mbps": cfg_bajada_mbps,
        "cfg_subida_mbps": cfg_subida_mbps,
        "request": request,
        "user": user,
        "total_cuentas": total_cuentas,
        "cuentas": cuentas,
        "total_prospectos": total_prospectos,
        "total_conectados": total_conectados,
        "abonados_conectados": abonados_conectados,
        "cortesias_activas": cortesias_activas,
        "prospectos": prospectos,
        "sesiones_activas": sesiones_activas,
        "cfg_cortesia": cfg_cortesia,
        "cfg_inactividad": cfg_inactividad,
        "cfg_limite": cfg_limite,
        "cfg_wa": cfg_wa,
        "cfg_tlf": cfg_tlf,
        "cfg_email": cfg_email,
        "cfg_ssid": cfg_ssid,
        "cfg_portal": cfg_portal
    }


def vista_admin_operaciones_zonapower(request: Request, user: models.User, db: Session) -> HTMLResponse:
    """Renderiza el panel de operaciones usando la plantilla Jinja."""
    from fastapi.templating import Jinja2Templates
    import permissions_manager
    templates = Jinja2Templates(directory="templates")
    templates.env.globals["has_perm"] = permissions_manager.user_has_perm
    templates.env.globals["has_any_perm"] = permissions_manager.user_has_any_perm
    templates.env.globals["get_perm_registry"] = permissions_manager.load_registry
    templates.env.globals["build_powertrack_perms"] = permissions_manager.build_powertrack_permissions_dict
    templates.env.globals["get_user_perms_list"] = permissions_manager.get_user_effective_perms_list
    ctx = get_zonapower_dashboard_context(request, user, db)
    return templates.TemplateResponse(request, "operaciones_zonapower.html", ctx)
