"""
client_normalizer.py - Módulo central para la normalización, clasificación
y cálculo unificado de clientes en la Intranet de Power Link.

Asegura consistencia entre:
- main.py (API de Integración, Reportes y Búsqueda de Clientes)
- comparativa_logic.py (Motor de Comparativas y Conciliación)
- daily_sync_job.py (Sincronización diaria con Rubpi)
- routers/soporte_router.py (Búsqueda de clientes para soporte)
"""

import re
from typing import Any, Dict, Optional, Tuple, Set

# ==============================================================================
# 1. NORMALIZACIÓN DE ESTADOS DE SERVICIO
# ==============================================================================

STATUS_MAP = {
    # Activo
    'ACTIVO': 'ACTIVO',
    'ACT.': 'ACTIVO',
    'ACT': 'ACTIVO',
    'ACTIVE': 'ACTIVO',
    # Suspendido
    'SUSPENDIDO': 'SUSPENDIDO',
    'SUSP.': 'SUSPENDIDO',
    'SUSP': 'SUSPENDIDO',
    'SUSPENDED': 'SUSPENDIDO',
    # Exonerado
    'EXONERADO': 'EXONERADO',
    'EXO.': 'EXONERADO',
    'EXO': 'EXONERADO',
    'EXONERATED': 'EXONERADO',
    # Retirado
    'RETIRADO': 'RETIRADO',
    'RET.': 'RETIRADO',
    'RET': 'RETIRADO',
    'RETIRO': 'RETIRADO',
    # Por Retirar
    'POR RETIRAR': 'POR RETIRAR',
    'POR RET.': 'POR RETIRAR',
    'POR RET': 'POR RETIRAR',
    # Transferido
    'TRANSFERIDO': 'TRANSFERIDO',
    'TRANS.': 'TRANSFERIDO',
    'TRANS': 'TRANSFERIDO',
    # Inactivo
    'INACTIVO': 'INACTIVO',
    'INAC.': 'INACTIVO',
    'INAC': 'INACTIVO',
}

def normalize_status(val: Any) -> str:
    """
    Normaliza cualquier variante de estado de servicio a su texto completo oficial en mayúsculas:
    'ACTIVO', 'SUSPENDIDO', 'EXONERADO', 'RETIRADO', 'POR RETIRAR', 'TRANSFERIDO', 'INACTIVO'.
    Si el valor no se reconoce, devuelve el string limpio en mayúsculas.
    """
    if val is None:
        return 'DESCONOCIDO'
    s = str(val).strip().upper()
    return STATUS_MAP.get(s, s if s else 'DESCONOCIDO')


# ==============================================================================
# 2. CLASIFICACIÓN RESIDENCIAL VS CORPORATIVO
# ==============================================================================

CORP_DOC_TYPES = {'J', 'G', 'C'} # Jurídico, Gubernamental, Comuna / Consejo
CORP_SERVICE_TYPES = {'PYME', 'CORPORATIVO', 'DEDICADO'}

def classify_client_segment(item: Dict[str, Any]) -> str:
    """
    Determina si un cliente o contrato es 'Corporativo' o 'Residencial' mediante
    el criterio unificado acordado:
    1. Si 'service_type' / 'Tipo de servicio' está en ['PYME', 'CORPORATIVO', 'DEDICADO'] -> Corporativo
    2. Si 'doc_type' está en ['J', 'G', 'C'] o la cédula inicia con J-, G-, C- -> Corporativo
    3. Si 'is_natural' explícitamente viene False -> Corporativo
    4. Caso contrario -> Residencial (Personas naturales V, E con servicios residenciales)
    """
    if not isinstance(item, dict):
        return 'Residencial'

    # 1. Por tipo de servicio
    srv_type = str(item.get('service_type') or item.get('Tipo de servicio') or '').strip().upper()
    if srv_type in CORP_SERVICE_TYPES:
        return 'Corporativo'

    # 2. Por tipo de documento
    doc_type = str(item.get('doc_type') or '').strip().upper()
    if doc_type in CORP_DOC_TYPES:
        return 'Corporativo'

    # Si doc_type viene vacío, verificar el prefijo de Cédula (ej. J-12345678)
    cedula = str(item.get('Cédula') or item.get('cedula') or item.get('doc') or '').strip().upper()
    if len(cedula) >= 2 and cedula[0] in CORP_DOC_TYPES and cedula[1] in ('-', ' '):
        return 'Corporativo'

    # 3. Por bandera is_natural de Rubpi
    is_nat = item.get('is_natural')
    if is_nat is not None:
        if isinstance(is_nat, str):
            if is_nat.lower() in ('false', '0', 'no'):
                return 'Corporativo'
        elif not bool(is_nat):
            return 'Corporativo'

    return 'Residencial'

def is_corporate(item: Dict[str, Any]) -> bool:
    """Helper booleano: True si es Corporativo, False si es Residencial."""
    return classify_client_segment(item) == 'Corporativo'

def is_residential(item: Dict[str, Any]) -> bool:
    """Helper booleano: True si es Residencial, False si es Corporativo."""
    return classify_client_segment(item) == 'Residencial'


# ==============================================================================
# 3. DETECCIÓN Y CLASIFICACIÓN DE CONTRATOS TV / IPTV
# ==============================================================================

def is_tv_or_iptv(item: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Determina si un contrato corresponde a un servicio de TV o IPTV para mantenerlo
    excluido de la facturación y clientes activos de internet, pero contabilizado
    en su estructura dedicada.
    
    Retorna: (es_tv, 'IPTV' | 'TV' | '')
    """
    if not isinstance(item, dict):
        return False, ''

    plan = str(item.get('plan') or item.get('Plan') or '').strip().upper()
    srv_type = str(item.get('service_type') or item.get('Tipo de servicio') or '').strip().upper()

    if 'IPTV' in plan or srv_type == 'IPTV':
        return True, 'IPTV'

    if plan == 'TV' or 'TV' in plan.split() or srv_type == 'TV':
        return True, 'TV'

    return False, ''


# ==============================================================================
# 4. DETECCIÓN DE EXONERADOS (EMPLEADOS VS REGULARES)
# ==============================================================================

def is_employee_exonerated(
    item: Dict[str, Any],
    employee_identifiers: Optional[Set[str]] = None
) -> bool:
    """
    Determina si un contrato con estado EXONERADO pertenece a un trabajador/empleado:
    1. Etiqueta explícita: Contiene '(emp)' en el nombre o en la cédula (insensible a mayúsculas).
    2. Cruce con base de datos de RRHH: Si se suministra `employee_identifiers` (conjunto de
       cédulas limpias o nombres normalizados de la tabla de empleados), verifica coincidencia.
    """
    if not isinstance(item, dict):
        return False

    name = str(item.get('name') or item.get('Nombres') or item.get('nombres') or '').strip().lower()
    cedula = str(item.get('cedula') or item.get('Cédula') or item.get('doc') or '').strip().lower()

    # 1. Validación de etiqueta exacta (emp)
    if '(emp)' in name or '(emp)' in cedula:
        return True

    # 2. Validación cruzada con la tabla de empleados (si está disponible)
    if employee_identifiers:
        # Cédula limpia de caracteres no alfanuméricos y sólo dígitos
        clean_ci = re.sub(r'[^0-9a-z]', '', cedula)
        digits_ci = re.sub(r'[^0-9]', '', cedula)
        if (clean_ci and clean_ci in employee_identifiers) or (digits_ci and digits_ci in employee_identifiers):
            return True

        # Nombre completo limpio
        clean_name = re.sub(r'\s+', ' ', name).strip()
        if clean_name and clean_name in employee_identifiers:
            return True

    return False


# ==============================================================================
# 5. UTILIDADES DE PARSING NUMÉRICO Y MONETARIO
# ==============================================================================

def parse_amount(val: Any) -> float:
    """
    Parsea de forma segura cualquier representación monetaria a float:
    Ejemplos: '$35.00', '35,00', '$ 1.250,50', None -> float.
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace('$', '').replace(' ', '').strip()
    if not s:
        return 0.0
    s = s.replace(',', '.')
    if s.count('.') > 1:
        parts = s.rsplit('.', 1)
        s = parts[0].replace('.', '') + '.' + parts[1]
    try:
        return float(s)
    except:
        return 0.0
