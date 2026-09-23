# -*- coding: utf-8 -*-
"""
api_history.py — Controladores de endpoints para historial y exportación.
"""
from aprovisionamiento.core.services.history_service import HistoryService


def handle_history(limit: int = 50) -> tuple:
    records = HistoryService.get_recent(limit=limit)
    return ({"success": True, "records": records, "history": records, "count": len(records)}, 200)


def handle_export_excel() -> tuple:
    path, mime, filename = HistoryService.get_export_file()
    if path:
        return (path, mime, filename, 200)
    return (None, None, None, 404)
