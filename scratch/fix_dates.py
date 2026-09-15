import os

file_path = r'c:\Users\wgallardo\Documents\Proyectos gravity\intranet\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target1 = """    try:
        corte_dt = datetime.strptime(fechaCorte, "%Y-%m-%d")
    except:
        corte_dt = datetime.min
        
    try:
        inst_dt = datetime.strptime(fechaInstalaciones, "%Y-%m-%d")
        inst_str = inst_dt.strftime("%d/%m/%Y")
    except:
"""

replacement1 = """    try:
        corte_dt = datetime.strptime(fechaCorte, "%Y-%m-%d")
    except:
        hoy = datetime.now()
        corte_dt = datetime(hoy.year, hoy.month, 1)
        
    try:
        inst_dt = datetime.strptime(fechaInstalaciones, "%Y-%m-%d")
        inst_str = inst_dt.strftime("%d/%m/%Y")
    except:
"""

target2 = """        fechaPlanDesdeFormat = safe_date_str(raw_plan)
        fechaInstalacionFormat = safe_date_str(raw_inst)
        
        estado_dt = datetime.min
        inst_p_current = None"""

replacement2 = """        fechaPlanDesdeFormat = safe_date_str(raw_plan)
        fechaInstalacionFormat = safe_date_str(raw_inst)
        
        estado_dt = datetime.min
        inst_p_current = None
        plan_p = None"""

if target1 in content and target2 in content:
    content = content.replace(target1, replacement1)
    content = content.replace(target2, replacement2)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed fallback logic and variable leaks")
else:
    print("Targets not found")
