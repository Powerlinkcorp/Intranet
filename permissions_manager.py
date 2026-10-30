# -*- coding: utf-8 -*-
"""
permissions_manager.py — Gestor Empresarial de Roles y Permisos Jerárquicos (RBAC + PBAC)
Modalidad Power Track adaptada y optimizada para la Intranet Power Link.

Optimizaciones de Mejores Prácticas Implementadas:
  1. Caché en Memoria con invalidación por mtime (0 lecturas de disco innecesarias al renderizar el Sidebar).
  2. Memoización por instancia de usuario (`user._eff_perms_cache`) para complejidad O(1) en plantillas Jinja2.
  3. Modelo Híbrido Rol Base + Excepciones (Permite mantener el rol organizacional o usar modo Personalizado).
  4. Protección Anti-Bloqueo (Self-Lockout Guard): Impide que un admin se quite a sí mismo el acceso a Permisos.
  5. Bitácora de Auditoría de Seguridad (Quién cambió qué rol/permiso, a quién y cuándo).
  6. Registro Dinámico de Módulos, Desplegables y Sub-permisos + Guardas para Backend y Frontend (`window.INTRANET_PERMS`).
"""

import os
import json
import copy
from datetime import datetime
from typing import Dict, List, Any, Set, Optional
from fastapi import Depends, HTTPException, status, Request

REGISTRY_FILE = os.path.join("static", "data", "permissions_registry.json")
AUDIT_FILE = os.path.join("static", "data", "permissions_audit.json")

# Caché en memoria para máxima velocidad en cada request
_REGISTRY_CACHE: Optional[Dict[str, Any]] = None
_REGISTRY_MTIME: float = -1.0
_REGISTRY_VERSION: int = 0

# ==============================================================================
# 1. CATÁLOGO BASE DE MÓDULOS, DESPLEGABLES Y SUB-PERMISOS ESPECÍFICOS
# ==============================================================================
DEFAULT_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "mod_principal",
        "name": "Principal",
        "icon": "fa-solid fa-house",
        "color": "blue",
        "description": "Vistas generales de inicio, directorio corporativo y mesa de ayuda.",
        "is_system": True,
        "dropdowns": [
            {
                "id": "sub_principal_dashboard",
                "name": "Dashboard Inicio",
                "icon": "fa-solid fa-house",
                "route": "/",
                "legacy_keys": [],
                "default_open": True,
                "actions": [
                    {"id": "act_principal_dash_ver", "name": "Ver Muro, Anuncios y Cumpleaños", "type": "read"},
                    {"id": "act_principal_dash_crear", "name": "Publicar en Muro y Anuncios", "type": "create"},
                    {"id": "act_principal_dash_editar", "name": "Editar Publicaciones y Perfil", "type": "write"},
                    {"id": "act_principal_dash_eliminar", "name": "Eliminar Publicaciones del Muro", "type": "delete"},
                    {"id": "act_principal_recursos", "name": "Descargar Documentos y Recursos", "type": "export"},
                    {"id": "act_principal_feedback", "name": "Enviar Buzón de Sugerencias", "type": "write"}
                ]
            },
            {
                "id": "sub_principal_helpdesk",
                "name": "Comunicaciones / Helpdesk",
                "icon": "fa-solid fa-headset",
                "route": "/helpdesk",
                "legacy_keys": [],
                "default_open": True,
                "actions": [
                    {"id": "act_principal_helpdesk_ver", "name": "Ver Comunicaciones y Mesa de Ayuda", "type": "read"},
                    {"id": "act_principal_helpdesk_crear", "name": "Crear Tickets de Comunicación", "type": "create"},
                    {"id": "act_principal_helpdesk_editar", "name": "Gestionar y Responder Tickets", "type": "write"},
                    {"id": "act_principal_helpdesk_eliminar", "name": "Cerrar o Anular Tickets Helpdesk", "type": "delete"},
                    {"id": "act_principal_helpdesk_exportar", "name": "Exportar Historial de Comunicaciones", "type": "export"},
                    {"id": "act_principal_chat_usar", "name": "Usar Chat Interno Corporativo", "type": "write"}
                ]
            },
            {
                "id": "sub_principal_directorio",
                "name": "Directorio Telefónico",
                "icon": "fa-solid fa-address-book",
                "route": "/directorio",
                "legacy_keys": ["editar_directorio"],
                "default_open": True,
                "actions": [
                    {"id": "act_principal_dir_ver", "name": "Consultar Extensiones Telefónicas", "type": "read"},
                    {"id": "act_principal_dir_crear", "name": "Registrar Nueva Extensión Telefónica", "type": "create"},
                    {"id": "editar_directorio", "name": "Crear y Editar Extensiones", "type": "write"},
                    {"id": "act_principal_dir_eliminar", "name": "Eliminar Extensiones Telefónicas", "type": "delete"},
                    {"id": "act_principal_dir_exportar", "name": "Exportar Directorio Telefónico", "type": "export"}
                ]
            }
        ]
    },
    {
        "id": "mod_soporte",
        "name": "Soporte",
        "icon": "fa-solid fa-life-ring",
        "color": "purple",
        "description": "Gestión de reportes técnicos (Power Track), flasheo de ONUs y aprovisionamiento OLT.",
        "is_system": True,
        "dropdowns": [
            {
                "id": "sub_soporte_reporte",
                "name": "Reporte (Power Track)",
                "icon": "fa-solid fa-file-invoice",
                "route": "/reporte",
                "legacy_keys": ["perm_reporte", "ver_reportes"],
                "actions": [
                    {"id": "perm_dashboard_read", "name": "Dashboard: Ver Reportes y Estadísticas", "type": "read"},
                    {"id": "perm_dashboard_write", "name": "Dashboard: Crear, Editar y Cerrar Reportes", "type": "write"},
                    {"id": "act_reporte_crear", "name": "Reporte: Crear Nuevos Casos / Averías", "type": "create"},
                    {"id": "act_reporte_editar", "name": "Reporte: Diagnosticar y Modificar Averías", "type": "write"},
                    {"id": "act_reporte_eliminar", "name": "Reporte: Anular o Eliminar Reportes", "type": "delete"},
                    {"id": "act_reporte_exportar", "name": "Reporte: Exportar Reportes a Excel/CSV", "type": "export"},
                    {"id": "perm_coordinacion_read", "name": "Coordinación: Ver Asignaciones y Rutas", "type": "read"},
                    {"id": "perm_coordinacion_assign", "name": "Coordinación: Asignar Cuadrillas y Casos", "type": "write"},
                    {"id": "perm_afectaciones_read", "name": "Afectaciones: Ver Afectaciones Masivas", "type": "read"},
                    {"id": "perm_afectaciones_write", "name": "Afectaciones: Registrar y Editar Afectaciones", "type": "write"},
                    {"id": "perm_techs_read", "name": "Equipos Técnicos: Ver Cuadrillas y Técnicos", "type": "read"},
                    {"id": "perm_techs_write", "name": "Equipos Técnicos: Crear y Editar Equipos", "type": "write"},
                    {"id": "perm_motivos_read", "name": "Catálogos: Ver Zonas y Motivos de Falla", "type": "read"},
                    {"id": "perm_motivos_write", "name": "Catálogos: Agregar y Editar Zonas / Motivos", "type": "write"},
                    {"id": "perm_vgt_write", "name": "Módulo VGT: Gestionar Partes Diarios y Flota", "type": "write"},
                    {"id": "perm_logs_read", "name": "Auditoría: Ver Bitácora de Eventos (Logs)", "type": "read"},
                    {"id": "perm_users_write", "name": "Usuarios Soporte: Administrar Operadores Internos", "type": "admin"}
                ]
            },
            {
                "id": "sub_soporte_flasheo",
                "name": "Flasheo",
                "icon": "fa-solid fa-microchip",
                "route": "/soporte/flasheo",
                "legacy_keys": ["ver_flasheo", "perm_aprov"],
                "actions": [
                    {"id": "act_flasheo_ver", "name": "Ver Panel de Flasheo y Trazabilidad ONU", "type": "read"},
                    {"id": "act_flasheo_crear", "name": "Registrar Lotes / Cajas de ONUs", "type": "create"},
                    {"id": "act_flasheo_editar", "name": "Modificar Datos y Parámetros de ONUs", "type": "write"},
                    {"id": "act_flasheo_eliminar", "name": "Dar de baja o Anular Lote / ONU", "type": "delete"},
                    {"id": "act_flasheo_exportar", "name": "Exportar Reportes y Credenciales de ONUs", "type": "export"},
                    {"id": "act_flasheo_ejecutar", "name": "Ejecutar Flasheo y Sincronizar Estaciones", "type": "write"},
                    {"id": "act_flasheo_lotes", "name": "Gestionar Cajas y Asignación de ONUs", "type": "write"}
                ]
            },
            {
                "id": "sub_soporte_aprov",
                "name": "Aprovisionamiento",
                "icon": "fa-solid fa-server",
                "route": "/soporte/aprovisionamiento",
                "legacy_keys": ["ver_aprovisionamiento", "perm_aprov"],
                "actions": [
                    {"id": "act_aprov_ver", "name": "Consultar ONUs Desconfiguradas y Estado OLT", "type": "read"},
                    {"id": "act_aprov_crear", "name": "Aprovisionar / Registrar Nueva ONU en OLT", "type": "create"},
                    {"id": "act_aprov_autorizar", "name": "Autorizar y Configurar ONUs en SmartOLT", "type": "write"},
                    {"id": "act_aprov_migrar", "name": "Migrar VLAN y Perfiles de Velocidad", "type": "write"},
                    {"id": "act_aprov_eliminar", "name": "Desautorizar y Eliminar ONUs en OLT", "type": "delete"},
                    {"id": "act_aprov_exportar", "name": "Exportar Registros de Aprovisionamiento", "type": "export"},
                    {"id": "act_aprov_config", "name": "Configurar OLTs, IPs, VLANs y Credenciales", "type": "admin"}
                ]
            }
        ]
    },
    {
        "id": "mod_operaciones",
        "name": "Operaciones",
        "icon": "fa-solid fa-tools",
        "color": "amber",
        "description": "Centro de control de operaciones de red, actividades diarias, guardias y OZmap.",
        "is_system": True,
        "dropdowns": [
            {
                "id": "sub_op_welcome",
                "name": "Inicio / Resumen",
                "icon": "fa-solid fa-house",
                "route": "/admin/operaciones#welcome",
                "legacy_keys": [],
                "actions": [
                    {"id": "act_op_welcome_ver", "name": "Ver Panel Resumen e Indicadores Operativos", "type": "read"},
                    {"id": "act_op_welcome_crear", "name": "Publicar Aviso Operativo en Resumen", "type": "create"},
                    {"id": "act_op_welcome_editar", "name": "Configurar Widgets del Resumen Operativo", "type": "write"},
                    {"id": "act_op_welcome_eliminar", "name": "Eliminar Avisos del Resumen Operativo", "type": "delete"},
                    {"id": "act_op_welcome_exportar", "name": "Exportar Resumen Ejecutivo Operativo", "type": "export"}
                ]
            },
            {
                "id": "sub_op_daily",
                "name": "Actividades Diarias",
                "icon": "fa-solid fa-clipboard-list",
                "route": "/admin/operaciones#daily-activities",
                "legacy_keys": [],
                "actions": [
                    {"id": "act_op_daily_ver", "name": "Ver Bitácora de Actividades Diarias", "type": "read"},
                    {"id": "act_op_daily_crear", "name": "Registrar Nueva Actividad Diaria", "type": "create"},
                    {"id": "act_op_daily_editar", "name": "Modificar Actividades Diarias", "type": "write"},
                    {"id": "act_op_daily_eliminar", "name": "Eliminar Registros de Actividades Diarias", "type": "delete"},
                    {"id": "act_op_daily_exportar", "name": "Exportar Reportes de Actividades", "type": "export"}
                ]
            },
            {
                "id": "sub_op_events",
                "name": "Eventos de Red",
                "icon": "fa-solid fa-network-wired",
                "route": "/admin/operaciones#events-dashboard",
                "legacy_keys": [],
                "actions": [
                    {"id": "act_op_events_ver", "name": "Ver Tickets y Eventos de Red", "type": "read"},
                    {"id": "act_op_events_crear", "name": "Crear Eventos y Abrir Tickets de Red", "type": "create"},
                    {"id": "act_op_events_cerrar", "name": "Editar / Solventar y Cerrar Tickets de Red", "type": "write"},
                    {"id": "act_op_events_eliminar", "name": "Eliminar Tickets de Eventos de Red", "type": "delete"},
                    {"id": "act_op_events_exportar", "name": "Exportar Historial de Eventos de Red", "type": "export"}
                ]
            },
            {
                "id": "sub_op_guards",
                "name": "Cronograma de Guardias",
                "icon": "fa-solid fa-calendar-days",
                "route": "/admin/operaciones#guards",
                "legacy_keys": [],
                "actions": [
                    {"id": "act_op_guards_ver", "name": "Consultar Cronograma de Guardias", "type": "read"},
                    {"id": "act_op_guards_crear", "name": "Asignar Nuevos Turnos de Guardia", "type": "create"},
                    {"id": "act_op_guards_editar", "name": "Planificar y Modificar Turnos de Guardia", "type": "write"},
                    {"id": "act_op_guards_eliminar", "name": "Eliminar Turnos de Guardia", "type": "delete"},
                    {"id": "act_op_guards_exportar", "name": "Exportar Calendario de Guardias", "type": "export"}
                ]
            },
            {
                "id": "sub_op_projects",
                "name": "Proyectos",
                "icon": "fa-solid fa-folder-tree",
                "route": "/admin/operaciones#projects",
                "legacy_keys": [],
                "actions": [
                    {"id": "act_op_projects_ver", "name": "Ver Tablero de Proyectos de Ingeniería", "type": "read"},
                    {"id": "act_op_projects_crear", "name": "Crear Nuevos Proyectos de Red", "type": "create"},
                    {"id": "act_op_projects_editar", "name": "Actualizar y Gestionar Hitos de Proyectos", "type": "write"},
                    {"id": "act_op_projects_eliminar", "name": "Eliminar o Cancelar Proyectos", "type": "delete"},
                    {"id": "act_op_projects_exportar", "name": "Exportar Avance de Proyectos", "type": "export"}
                ]
            },
            {
                "id": "sub_op_activities",
                "name": "Requerimientos",
                "icon": "fa-solid fa-bolt",
                "route": "/admin/operaciones#activities",
                "legacy_keys": [],
                "actions": [
                    {"id": "act_op_activities_ver", "name": "Ver Requerimientos Operativos", "type": "read"},
                    {"id": "act_op_activities_crear", "name": "Registrar Nuevo Requerimiento Operativo", "type": "create"},
                    {"id": "act_op_activities_editar", "name": "Editar y Procesar Requerimientos", "type": "write"},
                    {"id": "act_op_activities_eliminar", "name": "Eliminar o Anular Requerimientos", "type": "delete"},
                    {"id": "act_op_activities_exportar", "name": "Exportar Listado de Requerimientos", "type": "export"}
                ]
            },
            {
                "id": "sub_op_ozmap",
                "name": "Módulo OZmap",
                "icon": "fa-solid fa-map-location-dot",
                "route": "/admin/operaciones#ozmap",
                "legacy_keys": [],
                "actions": [
                    {"id": "act_op_ozmap_ver", "name": "Consultar Clientes y Cajas NAP en OZmap", "type": "read"},
                    {"id": "act_op_ozmap_crear", "name": "Georreferenciar y Agregar Elementos en OZmap", "type": "create"},
                    {"id": "act_op_ozmap_sync", "name": "Editar y Sincronizar Clientes con SmartOLT/OZmap", "type": "write"},
                    {"id": "act_op_ozmap_eliminar", "name": "Desvincular o Eliminar Cajas/Elementos en OZmap", "type": "delete"},
                    {"id": "act_op_ozmap_exportar", "name": "Exportar Coordenadas y Reportes OZmap", "type": "export"}
                ]
            },
            {
                "id": "sub_op_ozmap_db",
                "name": "Base de Datos OZmap",
                "icon": "fa-solid fa-database",
                "route": "/admin/operaciones#ozmap-database",
                "legacy_keys": [],
                "actions": [
                    {"id": "act_op_ozmap_db_ver", "name": "Ver Historial y Bitácora OZmap", "type": "read"},
                    {"id": "act_op_ozmap_db_crear", "name": "Registrar Nuevas Cajas NAP en la Base", "type": "create"},
                    {"id": "act_op_ozmap_db_editar", "name": "Editar Registros y Diccionario de Cajas NAP", "type": "write"},
                    {"id": "act_op_ozmap_db_eliminar", "name": "Eliminar Registros de la Base OZmap", "type": "delete"},
                    {"id": "act_op_ozmap_db_exportar", "name": "Exportar Base de Datos OZmap (CSV/Excel)", "type": "export"}
                ]
            }
        ]
    },
    {
        "id": "mod_admin",
        "name": "Administración",
        "icon": "fa-solid fa-user-tie",
        "color": "emerald",
        "description": "Conciliación financiera, reportes gerenciales, histórico de clientes, RRHH y control de permisos.",
        "is_system": True,
        "dropdowns": [
            {
                "id": "sub_admin_integracion",
                "name": "Integración",
                "icon": "fa-solid fa-network-wired",
                "route": "/integracion",
                "legacy_keys": ["ver_integracion"],
                "actions": [
                    {"id": "ver_integracion", "name": "Ver Conciliación Financiera e Integración", "type": "read"},
                    {"id": "act_integracion_crear", "name": "Generar Nuevo Snapshot de Integración", "type": "create"},
                    {"id": "act_integracion_sync", "name": "Editar y Sincronizar Snapshots desde API", "type": "write"},
                    {"id": "act_integracion_eliminar", "name": "Depurar o Eliminar Snapshots Antiguos", "type": "delete"},
                    {"id": "act_integracion_exportar", "name": "Exportar Sábanas y Conciliaciones a Excel", "type": "export"}
                ]
            },
            {
                "id": "sub_admin_reportes",
                "name": "Reportes Admin",
                "icon": "fa-solid fa-chart-line",
                "route": "/reportes",
                "legacy_keys": ["ver_reportes"],
                "actions": [
                    {"id": "ver_reportes", "name": "Ver Reportes Gerenciales, Planes y ARPU", "type": "read"},
                    {"id": "act_reportes_crear", "name": "Generar Nuevos Cortes de Reportes", "type": "create"},
                    {"id": "act_reportes_editar", "name": "Configurar Metas y Filtros de Reportes", "type": "write"},
                    {"id": "act_reportes_eliminar", "name": "Eliminar Histórico de Reportes Generados", "type": "delete"},
                    {"id": "act_reportes_exportar", "name": "Exportar Reportes Gerenciales a Excel/PDF", "type": "export"}
                ]
            },
            {
                "id": "sub_admin_historico",
                "name": "Histórico",
                "icon": "fa-solid fa-history",
                "route": "/historico",
                "legacy_keys": ["ver_historico"],
                "actions": [
                    {"id": "ver_historico", "name": "Consultar Histórico y Trazabilidad de Clientes", "type": "read"},
                    {"id": "act_historico_crear", "name": "Registrar Nota / Evento en Histórico de Cliente", "type": "create"},
                    {"id": "act_historico_editar", "name": "Modificar Entradas en Histórico de Clientes", "type": "write"},
                    {"id": "act_historico_eliminar", "name": "Eliminar Entradas en Histórico de Clientes", "type": "delete"},
                    {"id": "act_historico_exportar", "name": "Exportar Historial Completo a Excel", "type": "export"}
                ]
            },
            {
                "id": "sub_admin_permisos",
                "name": "Permisos",
                "icon": "fa-solid fa-shield-halved",
                "route": "/admin/permisos",
                "legacy_keys": ["gestionar_permisos"],
                "actions": [
                    {"id": "act_permisos_ver", "name": "Ver Matriz de Roles y Permisos", "type": "read"},
                    {"id": "act_permisos_crear", "name": "Crear Nuevos Roles y Módulos", "type": "create"},
                    {"id": "gestionar_permisos", "name": "Modificar Roles, Permisos y Asignaciones", "type": "write"},
                    {"id": "act_permisos_eliminar", "name": "Eliminar Roles Personalizados o Módulos", "type": "delete"},
                    {"id": "act_permisos_exportar", "name": "Exportar Matriz y Auditoría de Permisos", "type": "export"}
                ]
            },
            {
                "id": "sub_admin_trabajadores",
                "name": "Trabajadores",
                "icon": "fa-solid fa-id-card-clip",
                "route": "/admin?tab=trabajadores",
                "legacy_keys": ["editar_usuarios"],
                "actions": [
                    {"id": "act_trabajadores_ver", "name": "Ver Nómina de Trabajadores", "type": "read"},
                    {"id": "act_trabajadores_crear", "name": "Registrar Nuevo Trabajador", "type": "create"},
                    {"id": "editar_usuarios", "name": "Editar Ficha, Cargo y Reestablecer Claves", "type": "write"},
                    {"id": "act_trabajadores_eliminar", "name": "Dar de baja o Suspender Trabajador", "type": "delete"},
                    {"id": "act_trabajadores_exportar", "name": "Exportar Directorio de Trabajadores a Excel", "type": "export"}
                ]
            },
            {
                "id": "sub_admin_panel",
                "name": "Panel Admin (RRHH)",
                "icon": "fa-solid fa-users",
                "route": "/admin",
                "legacy_keys": ["cargar_datos_usuarios"],
                "actions": [
                    {"id": "cargar_datos_usuarios", "name": "Acceder al Panel Admin y Carga de Empleados", "type": "read"},
                    {"id": "act_rrhh_crear", "name": "Crear Nuevos Anuncios y Eventos de Calendario", "type": "create"},
                    {"id": "act_rrhh_anuncios", "name": "Editar Anuncios, KPIs, Pop-up y Calendario", "type": "write"},
                    {"id": "act_rrhh_eliminar", "name": "Eliminar Anuncios y Eventos de Calendario", "type": "delete"},
                    {"id": "act_rrhh_exportar", "name": "Exportar Registros de RRHH y Empleados", "type": "export"}
                ]
            }
        ]
    }
]


# ==============================================================================
# 2. ROLES PREDEFINIDOS (ESTILO POWER TRACK + DEPARTAMENTALES)
# ==============================================================================
def _all_catalog_keys(catalog: List[Dict[str, Any]]) -> List[str]:
    keys = set()
    for mod in catalog:
        keys.add(mod["id"])
        for sub in mod.get("dropdowns", []):
            keys.add(sub["id"])
            for lk in sub.get("legacy_keys", []):
                keys.add(lk)
            for act in sub.get("actions", []):
                keys.add(act["id"])
    return sorted(list(keys))


DEFAULT_ROLES: List[Dict[str, Any]] = [
    {
        "id": "admin",
        "name": "Administrador (Acceso Total)",
        "badge": "👑 ADMIN",
        "color": "amber",
        "description": "Control total de todos los módulos, desplegables, acciones y configuración de roles.",
        "is_system": True,
        "all_access": True,
        "permissions": []
    },
    {
        "id": "supervisor_soporte",
        "name": "Supervisor de Soporte",
        "badge": "🛡️ SUP. SOPORTE",
        "color": "purple",
        "description": "Acceso completo a Soporte (Reporte, Flasheo y Aprovisionamiento con auditoría y gestión de equipos) y vista de Eventos de Red.",
        "is_system": True,
        "all_access": False,
        "permissions": [
            "mod_principal", "sub_principal_dashboard", "act_principal_dash_ver", "act_principal_recursos", "act_principal_feedback",
            "sub_principal_helpdesk", "act_principal_helpdesk_ver", "act_principal_chat_usar",
            "sub_principal_directorio", "act_principal_dir_ver",
            "mod_soporte",
            "sub_soporte_reporte", "perm_reporte", "ver_reportes",
            "perm_dashboard_read", "perm_dashboard_write",
            "perm_coordinacion_read", "perm_coordinacion_assign",
            "perm_afectaciones_read", "perm_afectaciones_write",
            "perm_techs_read", "perm_techs_write",
            "perm_motivos_read", "perm_motivos_write",
            "perm_vgt_write", "perm_logs_read", "perm_users_write",
            "sub_soporte_flasheo", "ver_flasheo", "perm_aprov",
            "act_flasheo_ver", "act_flasheo_ejecutar", "act_flasheo_lotes", "act_flasheo_exportar",
            "sub_soporte_aprov", "ver_aprovisionamiento",
            "act_aprov_ver", "act_aprov_autorizar", "act_aprov_migrar", "act_aprov_config",
            "mod_operaciones", "sub_op_events", "act_op_events_ver", "sub_op_guards", "act_op_guards_ver"
        ]
    },
    {
        "id": "operador_soporte",
        "name": "Operador de Soporte (Power Track)",
        "badge": "🎧 OP. SOPORTE",
        "color": "blue",
        "description": "Modalidad Operador Estándar de Power Track: Gestión de reportes, coordinación, afectaciones, técnicos y motivos en Soporte.",
        "is_system": True,
        "all_access": False,
        "permissions": [
            "mod_principal", "sub_principal_dashboard", "act_principal_dash_ver", "act_principal_recursos", "act_principal_feedback",
            "sub_principal_helpdesk", "act_principal_helpdesk_ver", "act_principal_chat_usar",
            "sub_principal_directorio", "act_principal_dir_ver",
            "mod_soporte",
            "sub_soporte_reporte", "perm_reporte", "ver_reportes",
            "perm_dashboard_read", "perm_dashboard_write",
            "perm_coordinacion_read", "perm_coordinacion_assign",
            "perm_afectaciones_read", "perm_afectaciones_write",
            "perm_techs_read", "perm_techs_write",
            "perm_motivos_read", "perm_motivos_write",
            "perm_vgt_write"
        ]
    },
    {
        "id": "tecnico_flasheo_aprov",
        "name": "Especialista Flasheo y Aprovisionamiento",
        "badge": "⚡ FLASHEO / APROV",
        "color": "cyan",
        "description": "Acceso especializado a los desplegables de Flasheo y Aprovisionamiento de ONUs en Soporte.",
        "is_system": True,
        "all_access": False,
        "permissions": [
            "mod_principal", "sub_principal_dashboard", "act_principal_dash_ver", "act_principal_recursos",
            "sub_principal_helpdesk", "act_principal_helpdesk_ver", "act_principal_chat_usar",
            "mod_soporte",
            "sub_soporte_flasheo", "ver_flasheo", "perm_aprov",
            "act_flasheo_ver", "act_flasheo_ejecutar", "act_flasheo_lotes", "act_flasheo_exportar",
            "sub_soporte_aprov", "ver_aprovisionamiento",
            "act_aprov_ver", "act_aprov_autorizar", "act_aprov_migrar"
        ]
    },
    {
        "id": "operador_noc",
        "name": "Operador de Operaciones / NOC",
        "badge": "🛰️ OPERACIONES",
        "color": "orange",
        "description": "Acceso completo a todos los desplegables del Módulo de Operaciones (Actividades, Eventos de Red, Guardias, Proyectos, OZmap).",
        "is_system": True,
        "all_access": False,
        "permissions": [
            "mod_principal", "sub_principal_dashboard", "act_principal_dash_ver", "act_principal_recursos", "act_principal_feedback",
            "sub_principal_helpdesk", "act_principal_helpdesk_ver", "act_principal_chat_usar",
            "sub_principal_directorio", "act_principal_dir_ver",
            "mod_operaciones",
            "sub_op_welcome", "act_op_welcome_ver",
            "sub_op_daily", "act_op_daily_ver", "act_op_daily_editar", "act_op_daily_exportar",
            "sub_op_events", "act_op_events_ver", "act_op_events_crear", "act_op_events_cerrar",
            "sub_op_guards", "act_op_guards_ver", "act_op_guards_editar",
            "sub_op_projects", "act_op_projects_ver", "act_op_projects_editar",
            "sub_op_activities", "act_op_activities_ver", "act_op_activities_editar",
            "sub_op_ozmap", "act_op_ozmap_ver", "act_op_ozmap_sync",
            "sub_op_ozmap_db", "act_op_ozmap_db_ver", "act_op_ozmap_db_editar", "act_op_ozmap_db_exportar",
            "mod_soporte", "sub_soporte_reporte", "perm_reporte", "perm_dashboard_read", "perm_afectaciones_read"
        ]
    },
    {
        "id": "rrhh",
        "name": "Administración y RRHH",
        "badge": "👔 RRHH / ADMIN",
        "color": "emerald",
        "description": "Gestión de trabajadores, carga de datos, directorio telefónico, anuncios e histórico administrativo.",
        "is_system": True,
        "all_access": False,
        "permissions": [
            "mod_principal", "sub_principal_dashboard", "act_principal_dash_ver", "act_principal_recursos", "act_principal_feedback",
            "sub_principal_helpdesk", "act_principal_helpdesk_ver", "act_principal_chat_usar",
            "sub_principal_directorio", "act_principal_dir_ver", "editar_directorio",
            "mod_admin",
            "sub_admin_trabajadores", "act_trabajadores_ver", "editar_usuarios",
            "sub_admin_panel", "cargar_datos_usuarios", "act_rrhh_anuncios",
            "sub_admin_historico", "ver_historico",
            "sub_admin_reportes", "ver_reportes", "act_reportes_exportar"
        ]
    },
    {
        "id": "user",
        "name": "Usuario Estándar (General)",
        "badge": "👤 ESTÁNDAR",
        "color": "slate",
        "description": "Acceso básico a los módulos principales de la Intranet (Inicio, Comunicaciones y Directorio).",
        "is_system": True,
        "all_access": False,
        "permissions": [
            "mod_principal",
            "sub_principal_dashboard", "act_principal_dash_ver", "act_principal_recursos", "act_principal_feedback",
            "sub_principal_helpdesk", "act_principal_helpdesk_ver", "act_principal_chat_usar",
            "sub_principal_directorio", "act_principal_dir_ver"
        ]
    },
    {
        "id": "personalizado",
        "name": "Personalizado (A medida)",
        "badge": "⚙️ PERSONALIZADO",
        "color": "amber",
        "description": "Permisos configurados manualmente por módulo, desplegable y acción específica.",
        "is_system": True,
        "all_access": False,
        "permissions": []
    }
]


# ==============================================================================
# 3. CACHÉ EN MEMORIA Y LECTURA / ESCRITURA DE REGISTRO
# ==============================================================================
def _ensure_registry_dir():
    os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)


def invalidate_cache():
    global _REGISTRY_CACHE, _REGISTRY_MTIME, _REGISTRY_VERSION
    _REGISTRY_CACHE = None
    _REGISTRY_MTIME = -1.0
    _REGISTRY_VERSION += 1


def ensure_standard_actions_for_catalog(catalog: List[Dict[str, Any]]):
    """
    Garantiza que TODO desplegable en el catálogo cuente con las 5 acciones estándar:
    - ver (read)
    - crear (create)
    - editar (write)
    - eliminar (delete)
    - exportar (export)
    Si alguna falta, la autogenera sin sobreescribir las existentes.
    """
    for mod in catalog:
        for sub in mod.get("dropdowns", []):
            sub_id = sub.get("id", "")
            sub_slug = sub_id.replace("sub_", "")
            sub_name = sub.get("name", "Ventana")
            actions = sub.setdefault("actions", [])
            existing_act_ids = {a.get("id") for a in actions}

            standard_suite = [
                ("ver", f"act_{sub_slug}_ver", f"Ver {sub_name} (Lectura)", "read"),
                ("crear", f"act_{sub_slug}_crear", f"Crear / Registrar en {sub_name}", "create"),
                ("editar", f"act_{sub_slug}_editar", f"Modificar / Editar en {sub_name}", "write"),
                ("eliminar", f"act_{sub_slug}_eliminar", f"Eliminar / Anular en {sub_name}", "delete"),
                ("exportar", f"act_{sub_slug}_exportar", f"Exportar datos de {sub_name} (Excel/CSV)", "export"),
            ]

            for verb, act_id, act_name, act_type in standard_suite:
                has_verb = any(
                    a.get("id") == act_id or 
                    a.get("id", "").endswith(f"_{verb}") or 
                    (verb == "editar" and "edit" in a.get("id", "").lower())
                    for a in actions
                )
                if not has_verb and act_id not in existing_act_ids:
                    actions.append({
                        "id": act_id,
                        "name": act_name,
                        "type": act_type
                    })
                    existing_act_ids.add(act_id)


def load_registry() -> Dict[str, Any]:
    """
    Carga el catálogo y los roles usando caché en memoria validada por mtime.
    Evita lecturas de disco repetitivas durante el renderizado de Jinja2.
    """
    global _REGISTRY_CACHE, _REGISTRY_MTIME, _REGISTRY_VERSION
    _ensure_registry_dir()

    current_mtime = os.path.getmtime(REGISTRY_FILE) if os.path.exists(REGISTRY_FILE) else 0.0
    if _REGISTRY_CACHE is not None and current_mtime == _REGISTRY_MTIME:
        return _REGISTRY_CACHE

    saved_data = {"custom_modules": [], "custom_dropdowns": {}, "custom_actions": {}, "roles": []}
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
        except Exception:
            pass

    catalog = copy.deepcopy(DEFAULT_CATALOG)
    mod_map = {m["id"]: m for m in catalog}

    # 1. Incorporar módulos personalizados nuevos
    for cmod in saved_data.get("custom_modules", []):
        if cmod.get("id") and cmod["id"] not in mod_map:
            catalog.append(cmod)
            mod_map[cmod["id"]] = cmod

    # 2. Incorporar desplegables (ventanas) agregados a módulos existentes
    custom_dropdowns = saved_data.get("custom_dropdowns", {})
    for mod_id, drop_list in custom_dropdowns.items():
        if mod_id in mod_map and isinstance(drop_list, list):
            existing_sub_ids = {d["id"] for d in mod_map[mod_id].get("dropdowns", [])}
            for d in drop_list:
                if d.get("id") and d["id"] not in existing_sub_ids:
                    mod_map[mod_id].setdefault("dropdowns", []).append(d)
                    existing_sub_ids.add(d["id"])

    # 3. Incorporar acciones (sub-permisos específicos) agregadas a desplegables
    custom_actions = saved_data.get("custom_actions", {})
    for sub_id, act_list in custom_actions.items():
        if not isinstance(act_list, list):
            continue
        for mod in catalog:
            for sub in mod.get("dropdowns", []):
                if sub["id"] == sub_id:
                    existing_act_ids = {a["id"] for a in sub.get("actions", [])}
                    for a in act_list:
                        if a.get("id") and a["id"] not in existing_act_ids:
                            sub.setdefault("actions", []).append(a)
                            existing_act_ids.add(a["id"])

    # 3.1 Garantizar que todo desplegable cuente con las 5 acciones estándar (CRUD + Exportar)
    ensure_standard_actions_for_catalog(catalog)

    # 4. Construir lista de roles
    all_keys = _all_catalog_keys(catalog)
    roles = copy.deepcopy(DEFAULT_ROLES)
    role_map = {r["id"]: r for r in roles}

    for saved_role in saved_data.get("roles", []):
        rid = saved_role.get("id")
        if not rid:
            continue
        if rid in role_map and rid != "admin":
            role_map[rid]["permissions"] = saved_role.get("permissions", role_map[rid]["permissions"])
            if saved_role.get("name"):
                role_map[rid]["name"] = saved_role["name"]
            if saved_role.get("badge"):
                role_map[rid]["badge"] = saved_role["badge"]
            if saved_role.get("description"):
                role_map[rid]["description"] = saved_role["description"]
        elif rid not in role_map:
            roles.append(saved_role)
            role_map[rid] = saved_role

    if "admin" in role_map:
        role_map["admin"]["permissions"] = all_keys

    _REGISTRY_CACHE = {
        "catalog": catalog,
        "roles": roles,
        "all_keys": all_keys
    }
    _REGISTRY_MTIME = current_mtime
    _REGISTRY_VERSION += 1
    return _REGISTRY_CACHE


def _read_raw_saved() -> Dict[str, Any]:
    _ensure_registry_dir()
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"custom_modules": [], "custom_dropdowns": {}, "custom_actions": {}, "roles": []}


def _write_raw_saved(data: Dict[str, Any]):
    _ensure_registry_dir()
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    invalidate_cache()


# ==============================================================================
# 4. BITÁCORA DE AUDITORÍA DE SEGURIDAD (MEJOR PRÁCTICA RBAC)
# ==============================================================================
def log_permission_audit(actor_username: str, action: str, target: str, details: str, ip: str = ""):
    """Registra en disco cada cambio de roles, permisos o estructura de módulos."""
    _ensure_registry_dir()
    logs = get_permission_audit_logs(limit=499)
    entry = {
        "id": int(datetime.now().timestamp() * 1000),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "actor": actor_username or "admin",
        "action": action,
        "target": target,
        "details": details,
        "ip": ip or "local"
    }
    logs.insert(0, entry)
    try:
        with open(AUDIT_FILE, "w", encoding="utf-8") as f:
            json.dump(logs[:500], f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_permission_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
    _ensure_registry_dir()
    if not os.path.exists(AUDIT_FILE):
        return []
    try:
        with open(AUDIT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data[:limit] if isinstance(data, list) else []
    except Exception:
        return []


# ==============================================================================
# 5. GESTIÓN DINÁMICA DE MÓDULOS, DESPLEGABLES Y ROLES
# ==============================================================================
def add_custom_window_or_permission(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = _read_raw_saved()
    target_type = payload.get("target_type", "dropdown")
    assign_roles = payload.get("assign_roles", [])

    created_keys = []

    if target_type == "module":
        mod_id = payload.get("id", "").strip()
        if not mod_id.startswith("mod_"):
            mod_id = f"mod_{mod_id}"
        new_mod = {
            "id": mod_id,
            "name": payload.get("name", "Nuevo Módulo").strip(),
            "icon": payload.get("icon", "fa-solid fa-cube").strip(),
            "color": payload.get("color", "blue").strip(),
            "description": payload.get("description", "").strip(),
            "is_system": False,
            "dropdowns": []
        }
        first_sub_name = payload.get("first_dropdown_name", "").strip()
        if first_sub_name:
            sub_slug = mod_id.replace("mod_", "")
            sub_id = f"sub_{sub_slug}_main"
            std_actions = [
                {"id": f"act_{sub_slug}_main_ver", "name": f"Ver {first_sub_name} (Lectura)", "type": "read"},
                {"id": f"act_{sub_slug}_main_crear", "name": f"Crear / Registrar en {first_sub_name}", "type": "create"},
                {"id": f"act_{sub_slug}_main_editar", "name": f"Modificar / Editar en {first_sub_name}", "type": "write"},
                {"id": f"act_{sub_slug}_main_eliminar", "name": f"Eliminar / Anular en {first_sub_name}", "type": "delete"},
                {"id": f"act_{sub_slug}_main_exportar", "name": f"Exportar datos de {first_sub_name} (Excel/CSV)", "type": "export"},
            ]
            new_mod["dropdowns"].append({
                "id": sub_id,
                "name": first_sub_name,
                "icon": payload.get("icon", "fa-solid fa-window-maximize"),
                "route": payload.get("route", "#").strip() or "#",
                "legacy_keys": [],
                "is_custom": True,
                "actions": std_actions
            })
            created_keys.append(sub_id)
            for a in std_actions:
                created_keys.append(a["id"])

        raw.setdefault("custom_modules", []).append(new_mod)
        created_keys.insert(0, mod_id)

    elif target_type == "dropdown":
        parent_mod = payload.get("module_id", "mod_soporte").strip()
        sub_id = payload.get("id", "").strip()
        if not sub_id.startswith("sub_"):
            sub_id = f"sub_{sub_id}"
        sub_name = payload.get("name", "Nueva Ventana").strip()
        base_slug = sub_id.replace("sub_", "")
        actions = payload.get("actions")
        if not actions or not isinstance(actions, list):
            actions = [
                {"id": f"act_{base_slug}_ver", "name": f"Ver {sub_name} (Lectura)", "type": "read"},
                {"id": f"act_{base_slug}_crear", "name": f"Crear / Registrar en {sub_name}", "type": "create"},
                {"id": f"act_{base_slug}_editar", "name": f"Modificar / Editar en {sub_name}", "type": "write"},
                {"id": f"act_{base_slug}_eliminar", "name": f"Eliminar / Anular en {sub_name}", "type": "delete"},
                {"id": f"act_{base_slug}_exportar", "name": f"Exportar datos de {sub_name} (Excel/CSV)", "type": "export"},
            ]
        new_drop = {
            "id": sub_id,
            "name": sub_name,
            "icon": payload.get("icon", "fa-solid fa-window-restore").strip(),
            "route": payload.get("route", "#").strip() or "#",
            "legacy_keys": payload.get("legacy_keys", []),
            "is_custom": True,
            "actions": actions
        }
        raw.setdefault("custom_dropdowns", {}).setdefault(parent_mod, []).append(new_drop)
        created_keys.append(parent_mod)
        created_keys.append(sub_id)
        for a in actions:
            created_keys.append(a["id"])

    elif target_type == "action":
        parent_sub = payload.get("dropdown_id", "").strip()
        act_id = payload.get("id", "").strip()
        if not act_id.startswith("act_") and not act_id.startswith("perm_"):
            act_id = f"act_{act_id}"
        new_act = {
            "id": act_id,
            "name": payload.get("name", "Nuevo Permiso Específico").strip(),
            "type": payload.get("action_type", "write").strip(),
            "is_custom": True
        }
        raw.setdefault("custom_actions", {}).setdefault(parent_sub, []).append(new_act)
        created_keys.append(act_id)

    if assign_roles and created_keys:
        current_reg = load_registry()
        role_lookup = {r["id"]: r for r in current_reg["roles"]}
        saved_roles_map = {r["id"]: r for r in raw.get("roles", [])}
        for rid in assign_roles:
            if rid == "admin":
                continue
            base_r = saved_roles_map.get(rid) or role_lookup.get(rid)
            if base_r:
                updated_perms = list(set(base_r.get("permissions", []) + created_keys))
                role_copy = dict(base_r)
                role_copy["permissions"] = updated_perms
                saved_roles_map[rid] = role_copy
        raw["roles"] = list(saved_roles_map.values())

    _write_raw_saved(raw)
    return load_registry()


def save_or_update_role(role_data: Dict[str, Any]) -> Dict[str, Any]:
    raw = _read_raw_saved()
    rid = role_data.get("id", "").strip().lower().replace(" ", "_")
    if not rid or rid == "admin":
        return load_registry()

    current_reg = load_registry()
    existing_role = next((r for r in current_reg["roles"] if r["id"] == rid), None)

    new_role_obj = {
        "id": rid,
        "name": role_data.get("name", existing_role["name"] if existing_role else rid).strip(),
        "badge": role_data.get("badge", existing_role["badge"] if existing_role else f"🛡️ {rid.upper()}").strip(),
        "color": role_data.get("color", existing_role["color"] if existing_role else "blue").strip(),
        "description": role_data.get("description", existing_role["description"] if existing_role else "").strip(),
        "is_system": existing_role["is_system"] if existing_role else False,
        "all_access": False,
        "permissions": normalize_permissions_list(role_data.get("permissions", []), current_reg["catalog"])
    }

    saved_roles = raw.get("roles", [])
    idx = next((i for i, r in enumerate(saved_roles) if r.get("id") == rid), -1)
    if idx >= 0:
        saved_roles[idx] = new_role_obj
    else:
        saved_roles.append(new_role_obj)
    raw["roles"] = saved_roles
    _write_raw_saved(raw)
    return load_registry()


def delete_custom_role(role_id: str) -> Dict[str, Any]:
    raw = _read_raw_saved()
    sys_ids = {r["id"] for r in DEFAULT_ROLES}
    if role_id in sys_ids:
        return load_registry()
    raw["roles"] = [r for r in raw.get("roles", []) if r.get("id") != role_id]
    _write_raw_saved(raw)
    return load_registry()


# ==============================================================================
# 6. NORMALIZACIÓN, HERENCIA HÍBRIDA Y MEMOIZACIÓN O(1)
# ==============================================================================
def parse_user_permissions(raw_perms: str) -> Set[str]:
    if not raw_perms:
        return set()
    return {p.strip() for p in str(raw_perms).split(",") if p.strip()}


def expand_effective_permissions(user_role: str, raw_perms: str, catalog: List[Dict[str, Any]] = None) -> Set[str]:
    """
    Calcula el conjunto efectivo de llaves de permiso que tiene un usuario,
    combinando permisos explícitos y retrocompatibilidad legacy.
    """
    reg = load_registry()
    if catalog is None:
        catalog = reg["catalog"]

    role_clean = (user_role or "user").strip().lower()
    if role_clean == "admin":
        return set(reg["all_keys"])

    perms = parse_user_permissions(raw_perms)

    if not perms and role_clean != "personalizado":
        role_obj = next((r for r in reg["roles"] if r["id"] == role_clean), None)
        if role_obj:
            perms = set(role_obj.get("permissions", []))

    if not perms:
        perms.update([
            "mod_principal",
            "sub_principal_dashboard", "act_principal_dash_ver", "act_principal_recursos", "act_principal_feedback",
            "sub_principal_helpdesk", "act_principal_helpdesk_ver", "act_principal_chat_usar",
            "sub_principal_directorio", "act_principal_dir_ver",
            "sub_principal_cumpleanos", "act_principal_cumple_ver",
            "sub_principal_gaceta", "act_principal_gaceta_ver"
        ])

    for mod in catalog:
        mod_id = mod["id"]
        any_sub_active = False
        for sub in mod.get("dropdowns", []):
            sub_id = sub["id"]
            legacy_keys = sub.get("legacy_keys", [])
            sub_actions = [a["id"] for a in sub.get("actions", [])]

            has_sub = (sub_id in perms) or any(lk in perms for lk in legacy_keys) or any(ak in perms for ak in sub_actions)

            if sub_id == "sub_soporte_flasheo" and ("ver_flasheo" in perms or "sub_soporte_flasheo" in perms or ("perm_aprov" in perms and "sub_soporte_aprov" not in perms)):
                has_sub = True
            elif sub_id == "sub_soporte_aprov" and ("ver_aprovisionamiento" in perms or "sub_soporte_aprov" in perms or ("perm_aprov" in perms and "sub_soporte_flasheo" not in perms)):
                has_sub = True

            if has_sub:
                any_sub_active = True
                perms.add(sub_id)
                if sub_id == "sub_soporte_reporte":
                    perms.add("perm_reporte")
                    perms.add("ver_reportes")
                elif sub_id == "sub_soporte_flasheo":
                    perms.add("ver_flasheo")
                elif sub_id == "sub_soporte_aprov":
                    perms.add("ver_aprovisionamiento")
                else:
                    for lk in legacy_keys:
                        perms.add(lk)

                if not any(ak in perms for ak in sub_actions) and sub_actions:
                    perms.add(sub_actions[0])

        if any_sub_active:
            perms.add(mod_id)

    return perms


def _get_memoized_user_perms(user: Any) -> Set[str]:
    """Obtiene los permisos efectivos del usuario usando memoización en el objeto `user`."""
    if not user:
        return set()
    role = (getattr(user, "role", "user") or "user").lower()
    raw_perms = getattr(user, "permissions", "") or ""
    cache_key = (role, raw_perms, _REGISTRY_VERSION)
    if getattr(user, "_eff_perms_key", None) == cache_key:
        return getattr(user, "_eff_perms_set", set())

    eff = expand_effective_permissions(role, raw_perms)
    try:
        setattr(user, "_eff_perms_key", cache_key)
        setattr(user, "_eff_perms_set", eff)
    except Exception:
        pass
    return eff


def normalize_permissions_list(perm_list: List[str], catalog: List[Dict[str, Any]] = None) -> List[str]:
    raw_str = ",".join([p.strip() for p in perm_list if p and p.strip()])
    expanded = expand_effective_permissions("personalizado", raw_str, catalog)
    return sorted(list(expanded))


def build_powertrack_permissions_dict(user_role: str, raw_perms: str) -> Dict[str, Any]:
    role_clean = (user_role or "user").strip().lower()
    if role_clean == "admin":
        return None

    eff = expand_effective_permissions(user_role, raw_perms)

    return {
        "dashboard": {
            "read": ("perm_dashboard_read" in eff) or ("sub_soporte_reporte" in eff),
            "write": "perm_dashboard_write" in eff
        },
        "coordinacion": {
            "read": ("perm_coordinacion_read" in eff) or ("perm_dashboard_read" in eff),
            "assign": ("perm_coordinacion_assign" in eff) or ("perm_dashboard_write" in eff)
        },
        "afectaciones": {
            "read": ("perm_afectaciones_read" in eff) or ("perm_techs_read" in eff) or ("perm_dashboard_read" in eff),
            "write": ("perm_afectaciones_write" in eff) or ("perm_techs_write" in eff)
        },
        "techs": {
            "read": ("perm_techs_read" in eff) or ("perm_dashboard_read" in eff),
            "write": "perm_techs_write" in eff
        },
        "motivos": {
            "read": ("perm_motivos_read" in eff) or ("perm_dashboard_read" in eff),
            "write": ("perm_motivos_write" in eff) or ("perm_dashboard_write" in eff)
        },
        "vgt": {
            "read": ("perm_vgt_write" in eff) or ("perm_dashboard_read" in eff),
            "write": ("perm_vgt_write" in eff) or ("perm_dashboard_write" in eff)
        },
        "users": {
            "read": "perm_users_write" in eff,
            "write": "perm_users_write" in eff
        },
        "logs": {
            "read": "perm_logs_read" in eff
        }
    }


def user_has_perm(user: Any, perm_key: str) -> bool:
    """Helper O(1) memoizado para plantillas Jinja2 y endpoints FastAPI."""
    if not user:
        return False
    role = (getattr(user, "role", "user") or "user").lower()
    if role == "admin":
        return True
    return perm_key in _get_memoized_user_perms(user)


def user_has_any_perm(user: Any, perm_keys: List[str]) -> bool:
    if not user:
        return False
    role = (getattr(user, "role", "user") or "user").lower()
    if role == "admin":
        return True
    eff = _get_memoized_user_perms(user)
    return any(k in eff for k in perm_keys)


def get_user_effective_perms_list(user: Any) -> List[str]:
    """Devuelve la lista de permisos efectivos para inyectar en `window.INTRANET_PERMS`."""
    if not user:
        return []
    return sorted(list(_get_memoized_user_perms(user)))
