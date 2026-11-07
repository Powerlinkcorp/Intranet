import os
import re
import sys
import argparse
from datetime import datetime, timedelta
import pandas as pd
import client_normalizer as cn

# Configure output encoding
sys.stdout.reconfigure(encoding='utf-8')

# Constants
BASE_DIR = r"Z:\Integracion\Data Integracion\integracion whilly cuadros diarios"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "ARCHIVOS")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "comparativa_clientes.html")
OUTPUT_EXCEL = os.path.join(OUTPUT_DIR, "comparativa_clientes.xlsx")

def find_folders():
    """Lists directories in base path matching DD MM YYYY, parses them as dates, and returns them sorted descending."""
    if not os.path.exists(BASE_DIR):
        print(f"Error: Base directory '{BASE_DIR}' does not exist.")
        return []
        
    pattern = re.compile(r"^\d{2} \d{2} \d{4}$")
    valid_folders = []
    
    # We filter out future dates relative to current time to avoid typo folders like "04 03 3026"
    now_limit = datetime.now() + timedelta(days=1)
    
    for entry in os.listdir(BASE_DIR):
        full_path = os.path.join(BASE_DIR, entry)
        if os.path.isdir(full_path) and pattern.match(entry):
            try:
                date_val = datetime.strptime(entry, "%d %m %Y")
                if date_val <= now_limit:
                    valid_folders.append((date_val, entry, full_path))
            except ValueError:
                continue
                
    # Sort descending by date
    valid_folders.sort(key=lambda x: x[0], reverse=True)
    return valid_folders

def find_client_list_file(folder_path):
    """Finds the main client file matching 'Listado_de_clientes' but not '_juridicos'."""
    for entry in os.listdir(folder_path):
        if entry.lower().endswith(".xlsx") or entry.lower().endswith(".xls"):
            if "listado_de_clientes" in entry.lower() and "juridicos" not in entry.lower():
                return os.path.join(folder_path, entry)
    return None

def format_date_str(val):
    """Helper to cleanly format dates or timestamps."""
    if pd.isna(val) or val == "":
        return "N/A"
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.strftime("%d/%m/%Y %I:%M %p")
    
    # Try parsing string if possible
    val_str = str(val).strip()
    try:
        dt = pd.to_datetime(val_str)
        if not pd.isna(dt):
            return dt.strftime("%d/%m/%Y %I:%M %p")
    except Exception:
        pass
    
    return val_str

def generate_excel_file(changes, new_clients, variations):
    """Generates the triple-sheet Excel file with comparative data and cost variations."""
    # Format and select columns for Changes
    if len(changes) > 0:
        excel_changes = changes[[
            'ID Servicio', 'Cédula_hoy', 'Nombres_hoy', 'Plan_hoy', 
            'Estado servicio_ayer', 'Estado servicio_hoy', 'Fecha última cambio de estado'
        ]].copy()
        excel_changes.columns = [
            'ID Servicio', 'Cédula', 'Cliente', 'Plan', 
            'Estado Anterior', 'Estado Nuevo', 'Fecha de Cambio'
        ]
        excel_changes['Fecha de Cambio'] = excel_changes['Fecha de Cambio'].apply(format_date_str)
    else:
        excel_changes = pd.DataFrame(columns=[
            'ID Servicio', 'Cédula', 'Cliente', 'Plan', 
            'Estado Anterior', 'Estado Nuevo', 'Fecha de Cambio'
        ])
        
    # Format and select columns for New Clients
    if len(new_clients) > 0:
        excel_new = new_clients[[
            'ID Servicio', 'Cédula', 'Nombres', 'Plan', 
            'Estado servicio', 'Fecha de instalación'
        ]].copy()
        excel_new.columns = [
            'ID Servicio', 'Cédula', 'Cliente', 'Plan', 
            'Estado', 'Fecha de Instalación'
        ]
        excel_new['Fecha de Instalación'] = excel_new['Fecha de Instalación'].apply(format_date_str)
    else:
        excel_new = pd.DataFrame(columns=[
            'ID Servicio', 'Cédula', 'Cliente', 'Plan', 
            'Estado', 'Fecha de Instalación'
        ])
        
    # Format and select columns for Cost Variations
    if len(variations) > 0:
        excel_var = variations[[
            'ID Servicio', 'Cédula', 'Cliente', 'Tipo de Variación',
            'Plan Anterior', 'Plan Nuevo', 'Estado Anterior', 'Estado Nuevo',
            'Costo Anterior', 'Costo Nuevo', 'Variación'
        ]].copy()
    else:
        excel_var = pd.DataFrame(columns=[
            'ID Servicio', 'Cédula', 'Cliente', 'Tipo de Variación',
            'Plan Anterior', 'Plan Nuevo', 'Estado Anterior', 'Estado Nuevo',
            'Costo Anterior', 'Costo Nuevo', 'Variación'
        ])
        
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
        excel_changes.to_excel(writer, sheet_name="Cambios de Estado", index=False)
        excel_new.to_excel(writer, sheet_name="Nuevos Clientes", index=False)
        excel_var.to_excel(writer, sheet_name="Variaciones de Costo", index=False)

def generate_html(yesterday_name, today_name, df_yesterday, df_today, changes, new_clients, variations):
    """Generates the premium HTML report file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    title = f"Comparativa de Clientes: {yesterday_name} vs {today_name}"
    
    total_yesterday = len(df_yesterday)
    total_today = len(df_today)
    diff_total = total_today - total_yesterday
    diff_sign = "+" if diff_total >= 0 else ""
    
    total_added = variations[variations['Variación'] > 0]['Variación'].sum() if len(variations) > 0 else 0.0
    total_subtracted = variations[variations['Variación'] < 0]['Variación'].sum() if len(variations) > 0 else 0.0
    net_variation = variations['Variación'].sum() if len(variations) > 0 else 0.0
    
    class_net = "trend-up" if net_variation >= 0 else "trend-down"
    sign_net = "+" if net_variation >= 0 else ""

    all_plans = set(changes['Plan_hoy'].dropna().astype(str)) | set(new_clients['Plan'].dropna().astype(str))
    if len(variations) > 0:
        all_plans |= set(variations['Plan Nuevo'].replace('N/A', pd.NA).dropna().astype(str))
        all_plans |= set(variations['Plan Anterior'].replace('N/A', pd.NA).dropna().astype(str))
    plan_options = sorted(list(all_plans))

    changes_rows_html = ""
    for idx, row in changes.iterrows():
        id_serv = row['ID Servicio']
        ci = row['Cédula_hoy']
        nombre = row['Nombres_hoy']
        plan = row['Plan_hoy']
        est_ayer = row['Estado servicio_ayer']
        est_hoy = row['Estado servicio_hoy']
        fecha_cambio = format_date_str(row['Fecha última cambio de estado'])
        
        class_ayer = est_ayer.lower().replace(" ", "_").replace("-", "_") if isinstance(est_ayer, str) else "unknown"
        class_hoy = est_hoy.lower().replace(" ", "_").replace("-", "_") if isinstance(est_hoy, str) else "unknown"
        
        changes_rows_html += f"""
        <tr data-plan="{plan}" data-status-old="{est_ayer}" data-status-new="{est_hoy}">
            <td><strong>{id_serv}</strong></td>
            <td>{ci}</td>
            <td class="client-name">{nombre}</td>
            <td>{plan}</td>
            <td><span class="badge status-{class_ayer}">{est_ayer}</span></td>
            <td>
                <div class="transition-cell">
                    <svg class="arrow-svg" viewBox="0 0 24 24" width="16" height="16"><path fill="none" d="M0 0h24v24H0z"/><path d="M16.172 11l-5.364-5.364 1.414-1.414L20 12l-7.778 7.778-1.414-1.414L16.172 13H4v-2z" fill="currentColor"/></svg>
                    <span class="badge status-{class_hoy}">{est_hoy}</span>
                </div>
            </td>
            <td class="date-cell">{fecha_cambio}</td>
        </tr>
        """

    new_rows_html = ""
    for idx, row in new_clients.iterrows():
        id_serv = row['ID Servicio']
        ci = row['Cédula']
        nombre = row['Nombres']
        plan = row['Plan']
        est = row['Estado servicio']
        fecha_inst = format_date_str(row['Fecha de instalación'])
        
        class_est = est.lower().replace(" ", "_").replace("-", "_") if isinstance(est, str) else "unknown"
        
        new_rows_html += f"""
        <tr data-plan="{plan}" data-status="{est}">
            <td><strong>{id_serv}</strong></td>
            <td>{ci}</td>
            <td class="client-name">{nombre}</td>
            <td>{plan}</td>
            <td><span class="badge status-{class_est}">{est}</span></td>
            <td class="date-cell">{fecha_inst}</td>
        </tr>
        """

    var_rows_html = ""
    for idx, row in variations.iterrows():
        id_serv = row['ID Servicio']
        ci = row['Cédula']
        nombre = row['Cliente']
        tipo_var = row['Tipo de Variación']
        plan_ayer = row['Plan Anterior']
        plan_hoy = row['Plan Nuevo']
        est_ayer = row['Estado Anterior']
        est_hoy = row['Estado Nuevo']
        cost_ayer = float(row['Costo Anterior'])
        cost_hoy = float(row['Costo Nuevo'])
        var_val = float(row['Variación'])
        
        class_var = "trend-up" if var_val > 0 else "trend-down"
        sign_var = "+" if var_val > 0 else ""
        
        class_est_ayer = est_ayer.lower().replace(" ", "_").replace("-", "_") if isinstance(est_ayer, str) else "unknown"
        class_est_hoy = est_hoy.lower().replace(" ", "_").replace("-", "_") if isinstance(est_hoy, str) else "unknown"
        
        badge_est_ayer = f'<span class="badge status-{class_est_ayer}">{est_ayer}</span>' if est_ayer != 'N/A' else '<span class="text-muted">N/A</span>'
        badge_est_hoy = f'<span class="badge status-{class_est_hoy}">{est_hoy}</span>' if est_hoy != 'N/A' else '<span class="text-muted">N/A</span>'
        
        if plan_hoy != 'N/A' and plan_ayer != 'N/A' and plan_ayer != plan_hoy:
            plan_cell = f"""
            <div class="transition-cell">
                <span class="text-muted">{plan_ayer}</span>
                <svg class="arrow-svg" viewBox="0 0 24 24" width="12" height="12"><path fill="none" d="M0 0h24v24H0z"/><path d="M16.172 11l-5.364-5.364 1.414-1.414L20 12l-7.778 7.778-1.414-1.414L16.172 13H4v-2z" fill="currentColor"/></svg>
                <span class="client-name">{plan_hoy}</span>
            </div>
            """
        elif plan_hoy != 'N/A':
            plan_cell = f'<span class="client-name">{plan_hoy}</span>'
        else:
            plan_cell = f'<span class="text-muted">{plan_ayer}</span>'
            
        if est_hoy != 'N/A' and est_ayer != 'N/A' and est_ayer != est_hoy:
            status_cell = f"""
            <div class="transition-cell">
                {badge_est_ayer}
                <svg class="arrow-svg" viewBox="0 0 24 24" width="12" height="12"><path fill="none" d="M0 0h24v24H0z"/><path d="M16.172 11l-5.364-5.364 1.414-1.414L20 12l-7.778 7.778-1.414-1.414L16.172 13H4v-2z" fill="currentColor"/></svg>
                {badge_est_hoy}
            </div>
            """
        elif est_hoy != 'N/A':
            status_cell = badge_est_hoy
        else:
            status_cell = badge_est_ayer

        filter_plan = plan_hoy if plan_hoy != 'N/A' else plan_ayer
        
        var_rows_html += f"""
        <tr data-plan="{filter_plan}" data-type-var="{tipo_var}">
            <td><strong>{id_serv}</strong></td>
            <td>{ci}</td>
            <td class="client-name">{nombre}</td>
            <td><span class="badge-type-var">{tipo_var}</span></td>
            <td>{plan_cell}</td>
            <td>{status_cell}</td>
            <td>${cost_ayer:.2f}</td>
            <td>${cost_hoy:.2f}</td>
            <td><span class="{class_var}" style="font-weight: 700;">{sign_var}${var_val:.2f}</span></td>
        </tr>
        """

    plan_filter_html = "".join([f'<option value="{opt}">{opt}</option>' for opt in plan_options])

    html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: #151c2c;
            --text-color: #f3f4f6;
            --text-muted: #9ca3af;
            --primary: #3b82f6;
            --primary-glow: rgba(59, 130, 246, 0.15);
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.15);
            --warning: #f59e0b;
            --warning-glow: rgba(245, 158, 11, 0.15);
            --danger: #ef4444;
            --danger-glow: rgba(239, 68, 68, 0.15);
            --purple: #8b5cf6;
            --purple-glow: rgba(139, 92, 246, 0.15);
            --border-color: #242f41;
            --hover-bg: #1e293b;
            --font-main: 'Inter', sans-serif;
            --font-heading: 'Outfit', sans-serif;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: var(--font-main);
            line-height: 1.5;
            padding: 2rem;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        /* Header Styling */
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}

        .logo-area h1 {{
            font-family: var(--font-heading);
            font-size: 1.8rem;
            font-weight: 700;
            background: linear-gradient(135deg, #60a5fa, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.25rem;
        }}

        .logo-area p {{
            color: var(--text-muted);
            font-size: 0.9rem;
        }}

        .header-actions {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}

        .date-badge {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 0.5rem 1rem;
            border-radius: 50px;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .date-badge span {{
            color: var(--primary);
            font-weight: 600;
        }}

        .btn-download {{
            background: linear-gradient(135deg, var(--success), #059669);
            color: #ffffff;
            border: none;
            padding: 0.6rem 1.2rem;
            border-radius: 50px;
            font-weight: 600;
            font-family: var(--font-main);
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            text-decoration: none;
            box-shadow: 0 4px 12px var(--success-glow);
        }}

        .btn-download:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(16, 185, 129, 0.3);
            filter: brightness(1.1);
        }}

        .btn-toggle-upload {{
            background: var(--card-bg);
            color: var(--text-color);
            border: 1px solid var(--border-color);
            padding: 0.6rem 1.2rem;
            border-radius: 50px;
            font-weight: 600;
            font-family: var(--font-main);
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            text-decoration: none;
        }}

        .btn-toggle-upload:hover {{
            background: var(--hover-bg);
            border-color: var(--primary);
            transform: translateY(-1px);
        }}

        /* Collapsible Upload Panel */
        .upload-panel {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            display: none;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
        }}

        .upload-panel.active {{
            display: block;
        }}

        .upload-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 1.5rem;
        }}

        .drop-zone {{
            border: 2px dashed var(--border-color);
            border-radius: 12px;
            padding: 2rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: #0f1422;
        }}

        .drop-zone:hover, .drop-zone.drag-over {{
            border-color: var(--primary);
            background: rgba(59, 130, 246, 0.05);
        }}

        .drop-zone-title {{
            font-weight: 600;
            font-size: 0.95rem;
            margin-bottom: 0.5rem;
            color: var(--text-color);
        }}

        .drop-zone-desc {{
            color: var(--text-muted);
            font-size: 0.8rem;
        }}

        .drop-zone-file-name {{
            color: var(--success);
            font-weight: 600;
            margin-top: 0.5rem;
            font-size: 0.85rem;
        }}

        .btn-compare-web {{
            background: linear-gradient(135deg, var(--primary), #2563eb);
            color: #ffffff;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-weight: 600;
            font-family: var(--font-main);
            font-size: 0.95rem;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            width: 100%;
            box-shadow: 0 4px 12px var(--primary-glow);
        }}

        .btn-compare-web:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(59, 130, 246, 0.3);
            filter: brightness(1.1);
        }}

        .btn-compare-web:disabled {{
            background: var(--border-color);
            color: var(--text-muted);
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }}

        /* Metric Dashboard Cards */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }}

        .metric-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            position: relative;
            overflow: hidden;
            transition: transform 0.3s ease, border-color 0.3s ease;
        }}

        .metric-card:hover {{
            transform: translateY(-5px);
            border-color: rgba(59, 130, 246, 0.4);
        }}

        .metric-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background-color: var(--primary);
        }}

        .metric-card.success::before {{ background-color: var(--success); }}
        .metric-card.warning::before {{ background-color: var(--warning); }}
        .metric-card.purple::before {{ background-color: var(--purple); }}
        .metric-card.danger::before {{ background-color: var(--danger); }}

        .metric-card .title {{
            color: var(--text-muted);
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}

        .metric-card .value {{
            font-family: var(--font-heading);
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }}

        .metric-card .subtitle {{
            font-size: 0.85rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }}

        .trend-up {{ color: #10b981 !important; }}
        .trend-down {{ color: #ef4444 !important; }}

        .badge-type-var {{
            background-color: rgba(255, 255, 255, 0.05);
            color: var(--text-color);
            border: 1px solid var(--border-color);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 500;
        }}

        /* Main Workspace: Filter & Tabs Box */
        .workspace {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
        }}

        /* Navigation Tabs */
        .tabs-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .tabs {{
            display: flex;
            gap: 0.5rem;
            background: #0f1422;
            padding: 0.25rem;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }}

        .tab-btn {{
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 0.5rem 1.25rem;
            border-radius: 6px;
            font-weight: 500;
            font-family: var(--font-main);
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .tab-btn:hover {{
            color: var(--text-color);
        }}

        .tab-btn.active {{
            background-color: var(--primary);
            color: #ffffff;
            box-shadow: 0 4px 12px var(--primary-glow);
        }}

        .tab-btn .badge-count {{
            background: rgba(255, 255, 255, 0.2);
            color: inherit;
            padding: 0.1rem 0.5rem;
            border-radius: 50px;
            font-size: 0.75rem;
            font-weight: 700;
        }}

        /* Search & Filter bar */
        .filters-bar {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            margin-bottom: 1.5rem;
        }}

        .search-wrapper {{
            flex: 1;
            min-width: 250px;
            position: relative;
        }}

        .search-input {{
            width: 100%;
            background-color: #0f1422;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 0.75rem 1rem 0.75rem 2.5rem;
            color: var(--text-color);
            font-family: var(--font-main);
            font-size: 0.9rem;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }}

        .search-input:focus {{
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-glow);
        }}

        .search-icon {{
            position: absolute;
            left: 0.75rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            pointer-events: none;
        }}

        .select-filter {{
            background-color: #0f1422;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 0.75rem 1.5rem 0.75rem 1rem;
            color: var(--text-color);
            font-family: var(--font-main);
            font-size: 0.9rem;
            min-width: 180px;
            cursor: pointer;
            outline: none;
            transition: border-color 0.2s ease;
            appearance: none;
            background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%239ca3af' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
            background-repeat: no-repeat;
            background-position: right 0.75rem center;
            background-size: 1rem;
        }}

        .select-filter:focus {{
            border-color: var(--primary);
        }}

        .clear-filters-btn {{
            background: transparent;
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 0.75rem 1rem;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s ease;
        }}

        .clear-filters-btn:hover {{
            background: var(--hover-bg);
            color: var(--text-color);
        }}

        /* Table Styling */
        .table-container {{
            overflow-x: auto;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            background-color: #0f1422;
        }}

        .data-table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
        }}

        .data-table th {{
            background-color: #171f30;
            color: var(--text-color);
            font-weight: 600;
            padding: 1rem;
            border-bottom: 1px solid var(--border-color);
            font-family: var(--font-heading);
            font-size: 0.95rem;
        }}

        .data-table td {{
            padding: 1rem;
            border-bottom: 1px solid var(--border-color);
            color: #d1d5db;
        }}

        .data-table tbody tr {{
            transition: background-color 0.15s ease;
        }}

        .data-table tbody tr:hover {{
            background-color: rgba(255, 255, 255, 0.02);
        }}

        .data-table tbody tr:last-child td {{
            border-bottom: none;
        }}

        .client-name {{
            font-weight: 500;
            color: #ffffff;
        }}

        /* Status Badge System */
        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.75rem;
            border-radius: 50px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .status-activo {{
            background-color: var(--success-glow);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .status-suspendido {{
            background-color: var(--warning-glow);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .status-retirado, .status-inactivo {{
            background-color: var(--danger-glow);
            color: #fca5a5;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}

        .status-por_retirar, .status-por-retirar {{
            background-color: rgba(245, 158, 11, 0.1);
            color: #f59e0b;
            border: 1px solid rgba(245, 158, 11, 0.2);
        }}

        .status-exonerado, .status-transferido {{
            background-color: var(--purple-glow);
            color: #c084fc;
            border: 1px solid rgba(139, 92, 246, 0.3);
        }}

        .status-eliminado {{
            background-color: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }}

        .transition-cell {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .arrow-svg {{
            color: var(--text-muted);
            animation: pulse-arrow 1.5s infinite;
        }}

        @keyframes pulse-arrow {{
            0%, 100% {{ transform: translateX(0); opacity: 0.5; }}
            50% {{ transform: translateX(3px); opacity: 1; }}
        }}

        .date-cell {{
            color: var(--text-muted);
            font-size: 0.85rem;
        }}

        .empty-state {{
            display: none;
            padding: 3rem;
            text-align: center;
            color: var(--text-muted);
        }}

        .empty-state svg {{
            margin-bottom: 1rem;
            color: var(--border-color);
        }}

        .empty-state p {{
            font-size: 1rem;
            font-weight: 500;
        }}

        .tab-panel {{
            display: none;
        }}

        .tab-panel.active {{
            display: block;
        }}

        footer {{
            margin-top: 3rem;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.8rem;
            border-top: 1px solid var(--border-color);
            padding-top: 1.5rem;
        }}

        @media (max-width: 768px) {{
            body {{
                padding: 1rem;
            }}

            header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 1rem;
            }}

            .header-actions {{
                flex-direction: column;
                align-items: stretch;
                width: 100%;
            }}

            .date-badge {{
                align-self: flex-start;
            }}

            .btn-download {{
                justify-content: center;
            }}

            .tabs-header {{
                flex-direction: column;
                align-items: stretch;
            }}

            .tabs {{
                width: 100%;
            }}

            .tab-btn {{
                flex: 1;
                justify-content: center;
            }}
        }}
    </style>
</head>
<body>

<div class="container">
    <header>
        <div class="logo-area">
            <h1>GRAVITY INTEGRACIÓN</h1>
            <p>Monitoreo diario de listados de clientes residenciales</p>
        </div>
        <div class="header-actions">
            <button class="btn-toggle-upload" id="btn-toggle-upload" onclick="toggleUploadPanel()">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
                Cargar Archivos Manuales
            </button>
            <div class="date-badge">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-calendar" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
                Análisis: Ayer <span id="lbl-badge-yesterday">{yesterday_name}</span> vs Hoy <span id="lbl-badge-today">{today_name}</span>
            </div>
            <a href="comparativa_clientes.xlsx" id="btn-download-excel" class="btn-download" download>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-download-cloud"><polyline points="8 17 12 21 16 17"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/><polyline points="8 17 12 21 16 17"/></svg>
                Descargar en Excel
            </a>
        </div>
    </header>

    <!-- Collapsible Upload Panel -->
    <div class="upload-panel" id="upload-panel">
        <h3 style="font-family: var(--font-heading); font-size: 1.2rem; margin-bottom: 0.5rem; color: var(--primary);">
            Cargar archivos manualmente para comparar en el navegador
        </h3>
        <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.5rem;">
            Arrastra y suelta tus archivos Excel o haz clic en los recuadros para cargarlos. La comparación se realizará por completo en tu navegador de forma segura.
        </p>
        <div class="upload-grid">
            <div class="drop-zone" id="dz-yesterday" onclick="document.getElementById('input-yesterday').click()">
                <div class="drop-zone-title">Archivo Anterior (Ayer)</div>
                <div class="drop-zone-desc" id="dz-yesterday-desc">Arrastra el archivo aquí o haz clic para buscar</div>
                <div class="drop-zone-file-name" id="dz-yesterday-file"></div>
                <input type="file" id="input-yesterday" style="display: none;" accept=".xlsx,.xls" onchange="handleFileSelect(event, 'yesterday')">
            </div>
            <div class="drop-zone" id="dz-today" onclick="document.getElementById('input-today').click()">
                <div class="drop-zone-title">Archivo Nuevo (Hoy)</div>
                <div class="drop-zone-desc" id="dz-today-desc">Arrastra el archivo aquí o haz clic para buscar</div>
                <div class="drop-zone-file-name" id="dz-today-file"></div>
                <input type="file" id="input-today" style="display: none;" accept=".xlsx,.xls" onchange="handleFileSelect(event, 'today')">
            </div>
        </div>
        <button class="btn-compare-web" id="btn-compare-web" onclick="runWebComparison()" disabled>
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            Iniciar Comparación
        </button>
    </div>

    <!-- Metrics Dashboard Grid -->
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="title">Total de Clientes Hoy</div>
            <div class="value">{total_today:,}</div>
            <div class="subtitle">
                Ayer: {total_yesterday:,} | 
                <span class="{"trend-up" if diff_total >= 0 else "trend-down"}">
                    {diff_sign}{diff_total:,} ({diff_total/total_yesterday*100:+.2f}%)
                </span>
            </div>
        </div>
        <div class="metric-card warning">
            <div class="title">Cambios de Estatus</div>
            <div class="value">{len(changes)}</div>
            <div class="subtitle">Clientes que pasaron a otro estado</div>
        </div>
        <div class="metric-card success">
            <div class="title">Clientes Nuevos</div>
            <div class="value">{len(new_clients)}</div>
            <div class="subtitle">Nuevas instalaciones agregadas hoy</div>
        </div>
        <div class="metric-card purple">
            <div class="title">Variación Facturación</div>
            <div class="value {class_net}">{sign_net}${net_variation:,.2f}</div>
            <div class="subtitle">
                <span class="trend-up" style="font-weight:600;">+{len(variations[variations['Variación'] > 0])}</span>&nbsp;|&nbsp;
                <span class="trend-down" style="font-weight:600;">-{len(variations[variations['Variación'] < 0])}</span>
            </div>
        </div>
    </div>

    <!-- Main Workspace -->
    <div class="workspace">
        <div class="tabs-header">
            <div class="tabs">
                <button class="tab-btn active" id="tab-btn-changes" onclick="switchTab('changes')">
                    Cambios de Estatus
                    <span class="badge-count">{len(changes)}</span>
                </button>
                <button class="tab-btn" id="tab-btn-new-clients" onclick="switchTab('new-clients')">
                    Nuevos Clientes
                    <span class="badge-count">{len(new_clients)}</span>
                </button>
                <button class="tab-btn" id="tab-btn-variations" onclick="switchTab('variations')">
                    Variaciones de Costo
                    <span class="badge-count">{len(variations)}</span>
                </button>
            </div>

            <!-- Global search and filters -->
            <div class="filters-bar">
                <div class="search-wrapper">
                    <svg class="search-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <input type="text" id="search-input" class="search-input" placeholder="Buscar por Nombre, Cédula o ID..." oninput="applyFilters()">
                </div>
                
                <select id="plan-filter" class="select-filter" onchange="applyFilters()">
                    <option value="">Todos los Planes</option>
                    {plan_filter_html}
                </select>

                <button class="clear-filters-btn" onclick="clearFilters()">Limpiar Filtros</button>
            </div>
        </div>

        <!-- Panel 1: Changes -->
        <div id="changes-panel" class="tab-panel active">
            <div class="table-container">
                <table class="data-table" id="changes-table">
                    <thead>
                        <tr>
                            <th>ID Servicio</th>
                            <th>Cédula</th>
                            <th>Cliente</th>
                            <th>Plan de Internet</th>
                            <th>Estado Anterior</th>
                            <th>Estado Nuevo</th>
                            <th>Fecha Cambio de Estado</th>
                        </tr>
                    </thead>
                    <tbody id="changes-tbody">
                        {changes_rows_html}
                    </tbody>
                </table>
                <div class="empty-state" id="changes-empty">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <p>No se encontraron cambios de estado con los filtros aplicados.</p>
                </div>
            </div>
        </div>

        <!-- Panel 2: New Clients -->
        <div id="new-clients-panel" class="tab-panel">
            <div class="table-container">
                <table class="data-table" id="new-clients-table">
                    <thead>
                        <tr>
                            <th>ID Servicio</th>
                            <th>Cédula</th>
                            <th>Cliente</th>
                            <th>Plan de Internet</th>
                            <th>Estado Inicial</th>
                            <th>Fecha de Instalación</th>
                        </tr>
                    </thead>
                    <tbody id="new-clients-tbody">
                        {new_rows_html}
                    </tbody>
                </table>
                <div class="empty-state" id="new-clients-empty">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <p>No se encontraron nuevos clientes con los filtros aplicados.</p>
                </div>
            </div>
        </div>

        <!-- Panel 3: Variations -->
        <div id="variations-panel" class="tab-panel">
            <div class="table-container">
                <table class="data-table" id="variations-table">
                    <thead>
                        <tr>
                            <th>ID Servicio</th>
                            <th>Cédula</th>
                            <th>Cliente</th>
                            <th>Tipo de Variación</th>
                            <th>Plan Anterior / Nuevo</th>
                            <th>Estado Anterior / Nuevo</th>
                            <th>Costo Ant.</th>
                            <th>Costo Nuevo</th>
                            <th>Variación Mensual</th>
                        </tr>
                    </thead>
                    <tbody id="variations-tbody">
                        {var_rows_html}
                    </tbody>
                </table>
                <div class="empty-state" id="variations-empty">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <p>No se encontraron variaciones de costo con los filtros aplicados.</p>
                </div>
            </div>
        </div>
    </div>

    <footer>
        Generado automáticamente por Antigravity IDE - {datetime.now().strftime('%d/%m/%Y %I:%M:%S %p')}
    </footer>
</div>

<script>
    let activeTab = 'changes';
    let fileData = {{
        yesterday: null,
        yesterdayName: '',
        today: null,
        todayName: ''
    }};

    function toggleUploadPanel() {{
        const panel = document.getElementById('upload-panel');
        const btn = document.getElementById('btn-toggle-upload');
        panel.classList.toggle('active');
        if (panel.classList.contains('active')) {{
            btn.style.borderColor = 'var(--primary)';
            btn.style.color = 'var(--primary)';
        }} else {{
            btn.style.borderColor = 'var(--border-color)';
            btn.style.color = 'var(--text-color)';
        }}
    }}

    function setupDragAndDrop() {{
        ['yesterday', 'today'].forEach(type => {{
            const dz = document.getElementById('dz-' + type);
            
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {{
                dz.addEventListener(eventName, e => {{
                    e.preventDefault();
                    e.stopPropagation();
                }}, false);
            }});

            ['dragenter', 'dragover'].forEach(eventName => {{
                dz.addEventListener(eventName, () => {{
                    dz.classList.add('drag-over');
                }}, false);
            }});

            ['dragleave', 'drop'].forEach(eventName => {{
                dz.addEventListener(eventName, () => {{
                    dz.classList.remove('drag-over');
                }}, false);
            }});

            dz.addEventListener('drop', e => {{
                const dt = e.dataTransfer;
                const files = dt.files;
                if (files.length) {{
                    processFile(files[0], type);
                }}
            }}, false);
        }});
    }}

    function handleFileSelect(event, type) {{
        const files = event.target.files;
        if (files.length) {{
            processFile(files[0], type);
        }}
    }}

    function processFile(file, type) {{
        const reader = new FileReader();
        reader.onload = function(e) {{
            try {{
                const data = new Uint8Array(e.target.result);
                const workbook = XLSX.read(data, {{type: 'array'}});
                const firstSheetName = workbook.SheetNames[0];
                const worksheet = workbook.Sheets[firstSheetName];
                const jsonData = XLSX.utils.sheet_to_json(worksheet);
                
                fileData[type] = jsonData;
                fileData[type + 'Name'] = file.name;
                
                document.getElementById('dz-' + type + '-desc').innerText = "Archivo cargado correctamente";
                document.getElementById('dz-' + type + '-file').innerText = file.name;
                
                if (fileData.yesterday && fileData.today) {{
                    document.getElementById('btn-compare-web').removeAttribute('disabled');
                }}
            }} catch (error) {{
                alert("Error al leer el archivo Excel: " + error.message);
            }}
        }};
        reader.readAsArrayBuffer(file);
    }}

    document.addEventListener("DOMContentLoaded", () => {{
        setupDragAndDrop();
    }});

    function switchTab(tabId) {{
        activeTab = tabId;
        
        // Update tab buttons
        document.getElementById('tab-btn-changes').classList.remove('active');
        document.getElementById('tab-btn-new-clients').classList.remove('active');
        document.getElementById('tab-btn-variations').classList.remove('active');
        
        document.getElementById('tab-btn-' + tabId).classList.add('active');
        
        // Update tab panels
        document.querySelectorAll('.tab-panel').forEach(panel => {{
            panel.classList.remove('active');
        }});
        document.getElementById(tabId + '-panel').classList.add('active');
        
        applyFilters();
    }}

    function applyFilters() {{
        const searchVal = document.getElementById('search-input').value.toLowerCase().trim();
        const planVal = document.getElementById('plan-filter').value;
        
        const activeTableBody = document.getElementById(activeTab + '-tbody');
        const rows = activeTableBody.getElementsByTagName('tr');
        let visibleCount = 0;
        
        for (let row of rows) {{
            const idServicio = row.cells[0].innerText.toLowerCase();
            const cedula = row.cells[1].innerText.toLowerCase();
            const cliente = row.cells[2].innerText.toLowerCase();
            const plan = row.getAttribute('data-plan');
            
            // Text Search Match
            const matchesSearch = !searchVal || 
                                  idServicio.includes(searchVal) || 
                                  cedula.includes(searchVal) || 
                                  cliente.includes(searchVal);
            
            // Plan Filter Match
            const matchesPlan = !planVal || plan === planVal;
            
            if (matchesSearch && matchesPlan) {{
                row.style.display = '';
                visibleCount++;
            }} else {{
                row.style.display = 'none';
            }}
        }}
        
        // Toggle empty state
        const emptyState = document.getElementById(activeTab + '-empty');
        const table = document.getElementById(activeTab + '-table');
        if (visibleCount === 0) {{
            table.style.display = 'none';
            emptyState.style.display = 'block';
        }} else {{
            table.style.display = 'table';
            emptyState.style.display = 'none';
        }}
    }}

    function clearFilters() {{
        document.getElementById('search-input').value = '';
        document.getElementById('plan-filter').value = '';
        applyFilters();
    }}

    function cleanStr(val) {{
        if (val === undefined || val === null) return '';
        return String(val).trim();
    }}

    function formatJsDateStr(val) {{
        if (!val) return 'N/A';
        if (typeof val === 'number') {{
            const date = new Date((val - 25569) * 86400 * 1000);
            return formatDateTime(date);
        }}
        
        const strVal = cleanStr(val);
        if (!strVal || strVal === 'N/A' || strVal === 'NaN') return 'N/A';
        
        const dt = new Date(strVal);
        if (!isNaN(dt.getTime())) {{
            return formatDateTime(dt);
        }}
        return strVal;
    }}

    function formatDateTime(date) {{
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        
        let hours = date.getHours();
        const ampm = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12;
        hours = hours ? hours : 12;
        const hoursStr = String(hours).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        
        return `${{day}}/${{month}}/${{year}} ${{hoursStr}}:${{minutes}} ${{ampm}}`;
    }}

    function runWebComparison() {{
        const dfYesterday = fileData.yesterday;
        const dfToday = fileData.today;
        
        const normalizeColumns = rows => {{
            return rows.map(row => {{
                const cleanRow = {{}};
                Object.keys(row).forEach(key => {{
                    cleanRow[key.trim()] = row[key];
                }});
                return cleanRow;
            }});
        }};
        
        const yesterdayRows = normalizeColumns(dfYesterday);
        const todayRows = normalizeColumns(dfToday);
        
        const yMap = new Map();
        yesterdayRows.forEach(row => {{
            const id = cleanStr(row['ID Servicio']);
            if (id) yMap.set(id, row);
        }});
        
        const tMap = new Map();
        todayRows.forEach(row => {{
            const id = cleanStr(row['ID Servicio']);
            if (id) tMap.set(id, row);
        }});
        
        const changes = [];
        todayRows.forEach(tRow => {{
            const id = cleanStr(tRow['ID Servicio']);
            if (yMap.has(id)) {{
                const yRow = yMap.get(id);
                const estAyer = cleanStr(yRow['Estado servicio']);
                const estHoy = cleanStr(tRow['Estado servicio']);
                
                if (estAyer !== estHoy) {{
                    changes.push({{
                        id: id,
                        cedula: cleanStr(tRow['Cédula']),
                        nombres: cleanStr(tRow['Nombres']),
                        plan: cleanStr(tRow['Plan']),
                        estadoAyer: estAyer,
                        estadoHoy: estHoy,
                        fechaCambio: formatJsDateStr(tRow['Fecha última cambio de estado'])
                    }});
                }}
            }}
        }});
        
        const newClients = [];
        todayRows.forEach(tRow => {{
            const id = cleanStr(tRow['ID Servicio']);
            if (!yMap.has(id)) {{
                newClients.push({{
                    id: id,
                    cedula: cleanStr(tRow['Cédula']),
                    nombres: cleanStr(tRow['Nombres']),
                    plan: cleanStr(tRow['Plan']),
                    estado: cleanStr(tRow['Estado servicio']),
                    fechaInstalacion: formatJsDateStr(tRow['Fecha de instalación'])
                }});
            }}
        }});
        
        const removedClients = [];
        yesterdayRows.forEach(yRow => {{
            const id = cleanStr(yRow['ID Servicio']);
            if (!tMap.has(id)) {{
                removedClients.push(yRow);
            }}
        }});
        
        const variations = [];
        
        todayRows.forEach(tRow => {{
            const id = cleanStr(tRow['ID Servicio']);
            if (yMap.has(id)) {{
                const yRow = yMap.get(id);
                
                const estAyer = cleanStr(yRow['Estado servicio']).toUpperCase();
                const estHoy = cleanStr(tRow['Estado servicio']).toUpperCase();
                
                const planCostAyer = parseFloat(yRow['Costo del plan']) || 0;
                const planCostHoy = parseFloat(tRow['Costo del plan']) || 0;
                
                const billingAyer = (estAyer === 'ACTIVO') ? planCostAyer : 0;
                const billingHoy = (estHoy === 'ACTIVO') ? planCostHoy : 0;
                const diff = billingHoy - billingAyer;
                
                if (diff !== 0) {{
                    let typeVar = 'Otro Cambio';
                    if (estAyer !== 'ACTIVO' && estHoy === 'ACTIVO') {{
                        typeVar = 'Reconexión';
                    }} else if (estAyer === 'ACTIVO' && estHoy !== 'ACTIVO') {{
                        typeVar = 'Suspensión / Desactivación';
                    }} else if (estAyer === 'ACTIVO' && estHoy === 'ACTIVO') {{
                        typeVar = 'Cambio de Plan';
                    }}
                    
                    variations.push({{
                        id: id,
                        cedula: cleanStr(tRow['Cédula']),
                        nombres: cleanStr(tRow['Nombres'] || tRow['Cliente'] || yRow['Nombres']),
                        tipo: typeVar,
                        planAyer: cleanStr(yRow['Plan']),
                        planHoy: cleanStr(tRow['Plan']),
                        estadoAyer: cleanStr(yRow['Estado servicio']),
                        estadoHoy: cleanStr(tRow['Estado servicio']),
                        costoAyer: planCostAyer,
                        costoHoy: planCostHoy,
                        variacion: diff
                    }});
                }}
            }}
        }});
        
        newClients.forEach(tRow => {{
            const estHoy = cleanStr(tRow.estado).toUpperCase();
            const planCostHoy = parseFloat(dfToday.find(r => cleanStr(r['ID Servicio']) === tRow.id)?.['Costo del plan']) || 0;
            const billingHoy = (estHoy === 'ACTIVO') ? planCostHoy : 0;
            
            if (billingHoy !== 0) {{
                variations.push({{
                    id: tRow.id,
                    cedula: tRow.cedula,
                    nombres: tRow.nombres,
                    tipo: 'Nueva Instalación',
                    planAyer: 'N/A',
                    planHoy: tRow.plan,
                    estadoAyer: 'N/A',
                    estadoHoy: tRow.estado,
                    costoAyer: 0,
                    costoHoy: planCostHoy,
                    variacion: billingHoy
                }});
            }}
        }});
        
        removedClients.forEach(yRow => {{
            const estAyer = cleanStr(yRow['Estado servicio']).toUpperCase();
            const planCostAyer = parseFloat(yRow['Costo del plan']) || 0;
            const billingAyer = (estAyer === 'ACTIVO') ? planCostAyer : 0;
            
            if (billingAyer !== 0) {{
                variations.push({{
                    id: cleanStr(yRow['ID Servicio']),
                    cedula: cleanStr(yRow['Cédula']),
                    nombres: cleanStr(yRow['Nombres']),
                    tipo: 'Retiro / Eliminación',
                    planAyer: cleanStr(yRow['Plan']),
                    planHoy: 'N/A',
                    estadoAyer: cleanStr(yRow['Estado servicio']),
                    estadoHoy: 'N/A',
                    costoAyer: planCostAyer,
                    costoHoy: 0,
                    variacion: -billingAyer
                }});
            }}
        }});
        
        updateDashboardHTML(todayRows.length, yesterdayRows.length, changes, newClients, variations);
        
        generateExcelBlob(changes, newClients, variations);
        
        toggleUploadPanel();
        alert("¡Cruce manual finalizado con éxito en el navegador!");
    }}

    function updateDashboardHTML(totalToday, totalYesterday, changes, newClients, variations) {{
        document.getElementById('lbl-badge-yesterday').innerText = fileData.yesterdayName;
        document.getElementById('lbl-badge-today').innerText = fileData.todayName;
        
        const diffTotal = totalToday - totalYesterday;
        const diffSign = diffTotal >= 0 ? '+' : '';
        const pctDiff = totalYesterday > 0 ? (diffTotal / totalYesterday * 100).toFixed(2) : '0.00';
        const trendClass = diffTotal >= 0 ? 'trend-up' : 'trend-down';
        
        const cardTotal = document.querySelector('.metrics-grid > .metric-card:nth-child(1)');
        cardTotal.querySelector('.value').innerText = totalToday.toLocaleString();
        cardTotal.querySelector('.subtitle').innerHTML = `Ayer: ${{totalYesterday.toLocaleString()}} | <span class="${{trendClass}}">${{diffSign}}${{diffTotal.toLocaleString()}} (${{diffSign}}${{pctDiff}}%)</span>`;
        
        const cardChanges = document.querySelector('.metrics-grid > .metric-card.warning');
        cardChanges.querySelector('.value').innerText = changes.length;
        document.querySelector('#tab-btn-changes .badge-count').innerText = changes.length;
        
        const cardNew = document.querySelector('.metrics-grid > .metric-card.success');
        cardNew.querySelector('.value').innerText = newClients.length;
        document.querySelector('#tab-btn-new-clients .badge-count').innerText = newClients.length;
        
        let netVar = 0;
        let upVarCount = 0;
        let downVarCount = 0;
        variations.forEach(v => {{
            netVar += v.variacion;
            if (v.variacion > 0) upVarCount++;
            if (v.variacion < 0) downVarCount++;
        }});
        
        const cardVar = document.querySelector('.metrics-grid > .metric-card.purple');
        const signNet = netVar >= 0 ? '+' : '';
        const trendNetClass = netVar >= 0 ? 'trend-up' : 'trend-down';
        
        const varValueNode = cardVar.querySelector('.value');
        varValueNode.className = `value ${{trendNetClass}}`;
        varValueNode.innerText = `${{signNet}}$${{netVar.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}`;
        cardVar.querySelector('.subtitle').innerHTML = `<span class="trend-up" style="font-weight:600;">+${{upVarCount}}</span>&nbsp;|&nbsp;<span class="trend-down" style="font-weight:600;">-${{downVarCount}}</span>`;
        document.querySelector('#tab-btn-variations .badge-count').innerText = variations.length;
        
        const planSet = new Set();
        changes.forEach(c => planSet.add(c.plan));
        newClients.forEach(n => planSet.add(n.plan));
        variations.forEach(v => {{
            if (v.planHoy !== 'N/A') planSet.add(v.planHoy);
            if (v.planAyer !== 'N/A') planSet.add(v.planAyer);
        }});
        
        const planFilter = document.getElementById('plan-filter');
        planFilter.innerHTML = '<option value="">Todos los Planes</option>';
        Array.from(planSet).sort().forEach(p => {{
            if (p) planFilter.innerHTML += `<option value="${{p}}">${{p}}</option>`;
        }});
        
        const changesTbody = document.getElementById('changes-tbody');
        changesTbody.innerHTML = '';
        changes.forEach(row => {{
            const classAyer = cleanStr(row.estadoAyer).toLowerCase().replace(/ /g, '_').replace(/-/g, '_');
            const classHoy = cleanStr(row.estadoHoy).toLowerCase().replace(/ /g, '_').replace(/-/g, '_');
            
            changesTbody.innerHTML += `
            <tr data-plan="${{row.plan}}" data-status-old="${{row.estadoAyer}}" data-status-new="${{row.estadoHoy}}">
                <td><strong>${{row.id}}</strong></td>
                <td>${{row.cedula}}</td>
                <td class="client-name">${{row.nombres}}</td>
                <td>${{row.plan}}</td>
                <td><span class="badge status-${{classAyer}}">${{row.estadoAyer}}</span></td>
                <td>
                    <div class="transition-cell">
                        <svg class="arrow-svg" viewBox="0 0 24 24" width="16" height="16"><path fill="none" d="M0 0h24v24H0z"/><path d="M16.172 11l-5.364-5.364 1.414-1.414L20 12l-7.778 7.778-1.414-1.414L16.172 13H4v-2z" fill="currentColor"/></svg>
                        <span class="badge status-${{classHoy}}">${{row.estadoHoy}}</span>
                    </div>
                </td>
                <td class="date-cell">${{row.fechaCambio}}</td>
            </tr>`;
        }});
        
        const newTbody = document.getElementById('new-clients-tbody');
        newTbody.innerHTML = '';
        newClients.forEach(row => {{
            const classEst = cleanStr(row.estado).toLowerCase().replace(/ /g, '_').replace(/-/g, '_');
            newTbody.innerHTML += `
            <tr data-plan="${{row.plan}}" data-status="${{row.estado}}">
                <td><strong>${{row.id}}</strong></td>
                <td>${{row.cedula}}</td>
                <td class="client-name">${{row.nombres}}</td>
                <td>${{row.plan}}</td>
                <td><span class="badge status-${{classEst}}">${{row.estado}}</span></td>
                <td class="date-cell">${{row.fechaInstalacion}}</td>
            </tr>`;
        }});
        
        const varTbody = document.getElementById('variations-tbody');
        varTbody.innerHTML = '';
        variations.forEach(row => {{
            const classVar = row.variacion > 0 ? 'trend-up' : 'trend-down';
            const signVar = row.variacion > 0 ? '+' : '';
            
            const classEstAyer = cleanStr(row.estadoAyer).toLowerCase().replace(/ /g, '_').replace(/-/g, '_');
            const classEstHoy = cleanStr(row.estadoHoy).toLowerCase().replace(/ /g, '_').replace(/-/g, '_');
            
            const badgeEstAyer = row.estadoAyer !== 'N/A' ? `<span class="badge status-${{classEstAyer}}">${{row.estadoAyer}}</span>` : `<span class="text-muted">N/A</span>`;
            const badgeEstHoy = row.estadoHoy !== 'N/A' ? `<span class="badge status-${{classEstHoy}}">${{row.estadoHoy}}</span>` : `<span class="text-muted">N/A</span>`;
            
            let planCell = '';
            if (row.planHoy !== 'N/A' && row.planAyer !== 'N/A' && row.planAyer !== row.planHoy) {{
                planCell = `
                <div class="transition-cell">
                    <span class="text-muted">${{row.planAyer}}</span>
                    <svg class="arrow-svg" viewBox="0 0 24 24" width="12" height="12"><path fill="none" d="M0 0h24v24H0z"/><path d="M16.172 11l-5.364-5.364 1.414-1.414L20 12l-7.778 7.778-1.414-1.414L16.172 13H4v-2z" fill="currentColor"/></svg>
                    <span class="client-name">${{row.planHoy}}</span>
                </div>`;
            }} else if (row.planHoy !== 'N/A') {{
                planCell = `<span class="client-name">${{row.planHoy}}</span>`;
            }} else {{
                planCell = `<span class="text-muted">${{row.planAyer}}</span>`;
            }}
            
            let statusCell = '';
            if (row.estadoHoy !== 'N/A' && row.estadoAyer !== 'N/A' && row.estadoAyer !== row.estadoHoy) {{
                statusCell = `
                <div class="transition-cell">
                    ${{badgeEstAyer}}
                    <svg class="arrow-svg" viewBox="0 0 24 24" width="12" height="12"><path fill="none" d="M0 0h24v24H0z"/><path d="M16.172 11l-5.364-5.364 1.414-1.414L20 12l-7.778 7.778-1.414-1.414L16.172 13H4v-2z" fill="currentColor"/></svg>
                    ${{badgeEstHoy}}
                </div>`;
            }} else if (row.estadoHoy !== 'N/A') {{
                statusCell = badgeEstHoy;
            }} else {{
                statusCell = badgeEstAyer;
            }}
            
            const filterPlan = row.planHoy !== 'N/A' ? row.planHoy : row.planAyer;
            
            varTbody.innerHTML += `
            <tr data-plan="${{filterPlan}}" data-type-var="${{row.tipo}}">
                <td><strong>${{row.id}}</strong></td>
                <td>${{row.cedula}}</td>
                <td class="client-name">${{row.nombres}}</td>
                <td><span class="badge-type-var">${{row.tipo}}</span></td>
                <td>${{planCell}}</td>
                <td>${{statusCell}}</td>
                <td>$${{row.costoAyer.toFixed(2)}}</td>
                <td>$${{row.costoHoy.toFixed(2)}}</td>
                <td><span class="${{classVar}}" style="font-weight: 700;">${{signVar}}$${{row.variacion.toFixed(2)}}</span></td>
            </tr>`;
        }});
        
        applyFilters();
    }}

    function generateExcelBlob(changes, newClients, variations) {{
        const excelChanges = changes.map(c => ({{
            'ID Servicio': c.id,
            'Cédula': c.cedula,
            'Cliente': c.nombres,
            'Plan': c.plan,
            'Estado Anterior': c.estadoAyer,
            'Estado Nuevo': c.estadoHoy,
            'Fecha de Cambio': c.fechaCambio
        }}));
        
        const excelNew = newClients.map(n => ({{
            'ID Servicio': n.id,
            'Cédula': n.cedula,
            'Cliente': n.nombres,
            'Plan': n.plan,
            'Estado': n.estado,
            'Fecha de Instalación': n.fechaInstalacion
        }}));
        
        const excelVar = variations.map(v => ({{
            'ID Servicio': v.id,
            'Cédula': v.cedula,
            'Cliente': v.nombres,
            'Tipo de Variación': v.tipo,
            'Plan Anterior': v.planAyer,
            'Plan Nuevo': v.planHoy,
            'Estado Anterior': v.estadoAyer,
            'Estado Nuevo': v.estadoHoy,
            'Costo Anterior': v.costoAyer,
            'Costo Nuevo': v.costoHoy,
            'Variación': v.variacion
        }}));
        
        const wb = XLSX.utils.book_new();
        const wsChanges = XLSX.utils.json_to_sheet(excelChanges);
        const wsNew = XLSX.utils.json_to_sheet(excelNew);
        const wsVar = XLSX.utils.json_to_sheet(excelVar);
        
        XLSX.utils.book_append_sheet(wb, wsChanges, "Cambios de Estatus");
        XLSX.utils.book_append_sheet(wb, wsNew, "Nuevos Clientes");
        XLSX.utils.book_append_sheet(wb, wsVar, "Variaciones de Costo");
        
        const wbout = XLSX.write(wb, {{bookType: 'xlsx', type: 'array'}});
        const blob = new Blob([wbout], {{type: 'application/octet-stream'}});
        
        const downloadBtn = document.getElementById('btn-download-excel');
        downloadBtn.href = URL.createObjectURL(blob);
        downloadBtn.download = "comparativa_clientes_manual.xlsx";
    }}
</script>

</body>
</html>
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_template)

def compare_and_report(yesterday, today, yesterday_name=None, today_name=None):
    """Core function to read files, run comparison and output files."""
    # Resolve yesterday file path and name
    if os.path.isdir(yesterday):
        yesterday_file = find_client_list_file(yesterday)
        yesterday_lbl = yesterday_name or os.path.basename(yesterday)
    elif os.path.isfile(yesterday):
        yesterday_file = yesterday
        yesterday_lbl = yesterday_name or os.path.basename(yesterday)
    else:
        # Check if it is a directory name under BASE_DIR
        path = os.path.join(BASE_DIR, yesterday)
        if os.path.exists(path):
            yesterday_file = find_client_list_file(path)
            yesterday_lbl = yesterday
        else:
            raise ValueError(f"No se pudo encontrar el archivo o carpeta de ayer: {yesterday}")

    # Resolve today file path and name
    if os.path.isdir(today):
        today_file = find_client_list_file(today)
        today_lbl = today_name or os.path.basename(today)
    elif os.path.isfile(today):
        today_file = today
        today_lbl = today_name or os.path.basename(today)
    else:
        # Check if it is a directory name under BASE_DIR
        path = os.path.join(BASE_DIR, today)
        if os.path.exists(path):
            today_file = find_client_list_file(path)
            today_lbl = today
        else:
            raise ValueError(f"No se pudo encontrar el archivo o carpeta de hoy: {today}")

    if not yesterday_file or not today_file:
        raise ValueError(f"No se encontró el listado de clientes en ambas ubicaciones.\nAyer: {yesterday_file}\nHoy: {today_file}")
        
    df_yesterday = pd.read_excel(yesterday_file)
    df_today = pd.read_excel(today_file)
    
    df_yesterday.columns = [c.strip() for c in df_yesterday.columns]
    df_today.columns = [c.strip() for c in df_today.columns]
    
    # Estandarización unificada de Estado de Servicio
    if 'Estado servicio' in df_yesterday.columns:
        df_yesterday['Estado servicio'] = df_yesterday['Estado servicio'].apply(cn.normalize_status)
    if 'Estado servicio' in df_today.columns:
        df_today['Estado servicio'] = df_today['Estado servicio'].apply(cn.normalize_status)

    # Exclusión de Contratos TV / IPTV de la comparativa de clientes de Internet
    def _is_tv_row(r):
        p = str(r.get('Plan', '')).strip()
        ts = str(r.get('Tipo de servicio', '')).strip()
        is_tv, _ = cn.is_tv_or_iptv({'plan': p, 'service_type': ts})
        return is_tv

    if 'Plan' in df_yesterday.columns:
        df_yesterday = df_yesterday[~df_yesterday.apply(_is_tv_row, axis=1)].copy()
    if 'Plan' in df_today.columns:
        df_today = df_today[~df_today.apply(_is_tv_row, axis=1)].copy()
    
    # Ensure 'Costo del plan' is numeric
    if 'Costo del plan' in df_yesterday.columns:
        df_yesterday['Costo del plan'] = pd.to_numeric(df_yesterday['Costo del plan'], errors='coerce').fillna(0.0)
    else:
        df_yesterday['Costo del plan'] = 0.0

    if 'Costo del plan' in df_today.columns:
        df_today['Costo del plan'] = pd.to_numeric(df_today['Costo del plan'], errors='coerce').fillna(0.0)
    else:
        df_today['Costo del plan'] = 0.0

    # 1. State/status changes for existing clients
    m = pd.merge(
        df_yesterday[['ID Servicio', 'Cédula', 'Nombres', 'Estado servicio', 'Plan', 'Costo del plan']],
        df_today[['ID Servicio', 'Cédula', 'Nombres', 'Estado servicio', 'Fecha última cambio de estado', 'Plan', 'Costo del plan']],
        on='ID Servicio',
        suffixes=('_ayer', '_hoy')
    )
    
    changes = m[m['Estado servicio_ayer'] != m['Estado servicio_hoy']].copy()
    
    # 2. Billing variations for existing clients
    m['billing_ayer'] = m.apply(lambda r: float(r['Costo del plan_ayer']) if cn.normalize_status(r['Estado servicio_ayer']) == 'ACTIVO' else 0.0, axis=1)
    m['billing_hoy'] = m.apply(lambda r: float(r['Costo del plan_hoy']) if cn.normalize_status(r['Estado servicio_hoy']) == 'ACTIVO' else 0.0, axis=1)
    m['variation'] = m['billing_hoy'] - m['billing_ayer']
    
    cost_changes = m[m['variation'] != 0.0].copy()
    
    def classify_cost_change(row):
        st_ayer = cn.normalize_status(row['Estado servicio_ayer'])
        st_hoy = cn.normalize_status(row['Estado servicio_hoy'])
        plan_ayer = str(row['Plan_ayer']).strip()
        plan_hoy = str(row['Plan_hoy']).strip()
        
        if st_ayer != 'ACTIVO' and st_hoy == 'ACTIVO':
            return 'Reconexión'
        elif st_ayer == 'ACTIVO' and st_hoy == 'SUSPENDIDO':
            return 'Suspensión'
        elif st_ayer == 'ACTIVO' and st_hoy in ['RETIRADO', 'POR RETIRAR']:
            return 'Retiro Definitivo'
        elif st_ayer == 'ACTIVO' and st_hoy == 'EXONERADO':
            return 'Pase a Exonerado'
        elif st_ayer == 'ACTIVO' and st_hoy != 'ACTIVO':
            return 'Desactivación'
        elif st_ayer == 'ACTIVO' and st_hoy == 'ACTIVO':
            if plan_ayer != plan_hoy:
                return 'Cambio de Plan'
            else:
                return 'Ajuste de Tarifa / Costo'
        else:
            return 'Otro Cambio'
            
    if len(cost_changes) > 0:
        cost_changes['Tipo de Variación'] = cost_changes.apply(classify_cost_change, axis=1)
    else:
        cost_changes['Tipo de Variación'] = pd.Series(dtype=str)
        
    # 3. New clients
    ids_yesterday = set(df_yesterday['ID Servicio'])
    new_clients = df_today[~df_today['ID Servicio'].isin(ids_yesterday)].copy()
    
    new_clients['billing_ayer'] = 0.0
    new_clients['billing_hoy'] = new_clients.apply(lambda r: float(r['Costo del plan']) if cn.normalize_status(r['Estado servicio']) == 'ACTIVO' else 0.0, axis=1)
    new_clients['variation'] = new_clients['billing_hoy']
    
    new_billing_clients = new_clients[new_clients['variation'] != 0.0].copy()
    new_billing_clients['Tipo de Variación'] = 'Nueva Instalación'
    
    # 4. Removed clients
    ids_today = set(df_today['ID Servicio'])
    removed_clients = df_yesterday[~df_yesterday['ID Servicio'].isin(ids_today)].copy()
    
    removed_clients['billing_ayer'] = removed_clients.apply(lambda r: float(r['Costo del plan']) if cn.normalize_status(r['Estado servicio']) == 'ACTIVO' else 0.0, axis=1)
    removed_clients['billing_hoy'] = 0.0
    removed_clients['variation'] = -removed_clients['billing_ayer']
    
    removed_billing_clients = removed_clients[removed_clients['variation'] != 0.0].copy()
    removed_billing_clients['Tipo de Variación'] = 'Retiro Definitivo'
    
    # Combined variations
    variations_list = []
    
    for _, row in cost_changes.iterrows():
        variations_list.append({
            'ID Servicio': row['ID Servicio'],
            'Cédula': row['Cédula_hoy'],
            'Cliente': row['Nombres_hoy'],
            'Tipo de Variación': row['Tipo de Variación'],
            'Plan Anterior': row['Plan_ayer'],
            'Plan Nuevo': row['Plan_hoy'],
            'Estado Anterior': row['Estado servicio_ayer'],
            'Estado Nuevo': row['Estado servicio_hoy'],
            'Costo Anterior': float(row['Costo del plan_ayer']),
            'Costo Nuevo': float(row['Costo del plan_hoy']),
            'Variación': float(row['variation'])
        })
        
    for _, row in new_billing_clients.iterrows():
        variations_list.append({
            'ID Servicio': row['ID Servicio'],
            'Cédula': row['Cédula'],
            'Cliente': row['Nombres'],
            'Tipo de Variación': 'Nueva Instalación',
            'Plan Anterior': 'N/A',
            'Plan Nuevo': row['Plan'],
            'Estado Anterior': 'N/A',
            'Estado Nuevo': row['Estado servicio'],
            'Costo Anterior': 0.0,
            'Costo Nuevo': float(row['Costo del plan']),
            'Variación': float(row['variation'])
        })
        
    for _, row in removed_billing_clients.iterrows():
        variations_list.append({
            'ID Servicio': row['ID Servicio'],
            'Cédula': row['Cédula'],
            'Cliente': row['Nombres'],
            'Tipo de Variación': 'Retiro / Eliminación',
            'Plan Anterior': row['Plan'],
            'Plan Nuevo': 'N/A',
            'Estado Anterior': row['Estado servicio'],
            'Estado Nuevo': 'N/A',
            'Costo Anterior': float(row['Costo del plan']),
            'Costo Nuevo': 0.0,
            'Variación': float(row['variation'])
        })
        
    df_variations = pd.DataFrame(variations_list)
    if len(df_variations) == 0:
        df_variations = pd.DataFrame(columns=[
            'ID Servicio', 'Cédula', 'Cliente', 'Tipo de Variación',
            'Plan Anterior', 'Plan Nuevo', 'Estado Anterior', 'Estado Nuevo',
            'Costo Anterior', 'Costo Nuevo', 'Variación'
        ])
        
    changes = changes.fillna("")
    new_clients = new_clients.fillna("")
    df_variations = df_variations.fillna("")
    
    generate_excel_file(changes, new_clients, df_variations)
    generate_html(yesterday_lbl, today_lbl, df_yesterday, df_today, changes, new_clients, df_variations)
    return len(changes), len(new_clients), len(df_variations)

def main():
    parser = argparse.ArgumentParser(description="Compara listados de clientes de ayer y hoy.")
    parser.add_argument("--yesterday", type=str, help="Nombre de la carpeta de ayer (DD MM YYYY)")
    parser.add_argument("--today", type=str, help="Nombre de la carpeta de hoy (DD MM YYYY)")
    args = parser.parse_args()

    # Resolve yesterday and today
    yesterday_name, today_name = None, None

    if args.today and args.yesterday:
        yesterday_name, today_name = args.yesterday, args.today
    else:
        # Check if 03 07 2026 and 02 07 2026 exist directly in BASE_DIR
        now = datetime.now()
        t_str = "03 07 2026"
        y_str = "02 07 2026"
        t_path = os.path.join(BASE_DIR, t_str)
        y_path = os.path.join(BASE_DIR, y_str)
        
        if os.path.exists(t_path) and os.path.exists(y_path):
            today_name = t_str
            yesterday_name = y_str
        else:
            folders = find_folders()
            if len(folders) < 2:
                print("Error: Se necesitan al menos 2 carpetas con formato DD MM YYYY para comparar.")
                sys.exit(1)
            today_name = folders[0][1]
            yesterday_name = folders[1][1]

    print(f"Ejecutando comparación manual: {yesterday_name} vs {today_name}")
    try:
        changes_count, new_count, var_count = compare_and_report(yesterday_name, today_name)
        print(f"Completado: {changes_count} cambios, {new_count} nuevos, {var_count} variaciones de costo.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
