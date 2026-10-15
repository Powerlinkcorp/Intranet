# -*- coding: utf-8 -*-
"""
history_service.py — Servicio de persistencia y exportación de historial (CSV / Excel .xlsx).
"""
import csv
import os
import threading
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

CSV_FILE = os.path.join(LOGS_DIR, "registro_aprovisionamiento.csv")
XLSX_FILE = os.path.join(LOGS_DIR, "registro_aprovisionamiento.xlsx")

HISTORY_LOCK = threading.Lock()

CSV_HEADERS = [
    "FechaHora",
    "Usuario",
    "IP",
    "MAC",
    "PON_Serial",
    "Modelo",
    "VLAN",
    "SSID_2G",
    "SSID_5G",
    "Resultado",
    "Detalles"
]


class HistoryService:
    @staticmethod
    def _ensure_migrated_csv():
        if not os.path.exists(CSV_FILE):
            return
        try:
            with open(CSV_FILE, "r", encoding="utf-8-sig", errors="replace") as f:
                first_line = f.readline()
            if "Usuario" not in first_line:
                rows = []
                with open(CSV_FILE, "r", encoding="utf-8-sig", errors="replace") as f:
                    reader = csv.reader(f)
                    old_headers = next(reader, None)
                    for r in reader:
                        if r:
                            # Insertar "admin" como usuario por defecto
                            new_r = [r[0], "admin"] + r[1:]
                            rows.append(new_r)
                with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(CSV_HEADERS)
                    writer.writerows(rows)
        except Exception:
            pass

    @staticmethod
    def log(ip, mac, pon_serial, modelo, vlan, ssid_2g, ssid_5g, resultado, detalles, usuario="admin"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_clean = (usuario or "admin").strip()
        with HISTORY_LOCK:
            HistoryService._ensure_migrated_csv()
            file_exists = os.path.exists(CSV_FILE)
            with open(CSV_FILE, "a", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(CSV_HEADERS)
                writer.writerow([
                    timestamp,
                    user_clean,
                    ip or "",
                    mac or "",
                    pon_serial or "",
                    modelo or "",
                    vlan or "",
                    ssid_2g or "",
                    ssid_5g or "",
                    resultado or "",
                    str(detalles).replace("\n", " ")
                ])

            # 2. Guardar en XLSX
            HistoryService._append_xlsx(timestamp, user_clean, ip, mac, pon_serial, modelo, vlan, ssid_2g, ssid_5g, resultado, detalles)

    @staticmethod
    def _append_xlsx(timestamp, usuario, ip, mac, pon_serial, modelo, vlan, ssid_2g, ssid_5g, resultado, detalles):
        try:
            from openpyxl import Workbook, load_workbook
            from openpyxl.styles import Font, PatternFill, Alignment

            if not os.path.exists(XLSX_FILE):
                wb = Workbook()
                ws = wb.active
                ws.title = "Aprovisionamientos"
                ws.append(CSV_HEADERS)
                header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
                header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
                for cell in ws[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                wb = load_workbook(XLSX_FILE)
                ws = wb.active

            try:
                ts_val = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            except Exception:
                ts_val = timestamp

            row = [ts_val, usuario, ip, mac, pon_serial, modelo, vlan, ssid_2g, ssid_5g, resultado, str(detalles)]
            ws.append(row)

            last_row = ws.max_row
            ws.cell(row=last_row, column=1).number_format = "DD/MM/YYYY HH:MM:SS"

            res_cell = ws.cell(row=last_row, column=10)
            if "EXITO" in str(resultado).upper():
                res_cell.font = Font(color="047857", bold=True)
            elif "ERROR" in str(resultado).upper() or "FALLO" in str(resultado).upper():
                res_cell.font = Font(color="B91C1C", bold=True)

            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = col[0].column_letter
                ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

            wb.save(XLSX_FILE)
        except Exception:
            pass

    @staticmethod
    def get_recent(limit: int = 50) -> list:
        if not os.path.exists(CSV_FILE):
            return []
        with HISTORY_LOCK:
            try:
                items = []
                with open(CSV_FILE, "r", encoding="utf-8-sig", errors="replace") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        items.append(row)
                return items[-limit:][::-1]
            except Exception:
                return []

    @staticmethod
    def get_export_file() -> tuple:
        """Retorna (ruta_archivo, tipo_mimetype, nombre_descarga)."""
        if os.path.exists(XLSX_FILE):
            return (
                XLSX_FILE,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "registro_aprovisionamiento.xlsx"
            )
        elif os.path.exists(CSV_FILE):
            return (CSV_FILE, "text/csv", "registro_aprovisionamiento.csv")
        return (None, None, None)

    @staticmethod
    def get_vlan_usage_counts() -> dict:
        """
        Retorna un diccionario {str(vlan): int(cantidad_usos)} basado en los registros exitosos.
        """
        counts = {}
        if not os.path.exists(CSV_FILE):
            return counts
        with HISTORY_LOCK:
            try:
                with open(CSV_FILE, "r", encoding="utf-8-sig", errors="replace") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        vlan = str(row.get("VLAN") or "").strip()
                        if vlan and vlan != "3":  # VLAN 3 es la inicial de gestión
                            counts[vlan] = counts.get(vlan, 0) + 1
            except Exception:
                pass
        return counts
