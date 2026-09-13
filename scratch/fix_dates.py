import os

file_path = r"c:\Users\wgallardo\Documents\Proyectos gravity\intranet\main.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Buscamos la línea: date_only = str(raw_estado).split("T")[0]
old_code = """          if raw_estado:
              date_only = str(raw_estado).split("T")[0]
              try:
                  estado_dt = datetime.strptime(date_only, "%Y-%m-%d")"""

new_code = """          if raw_estado:
              # Extraer solo la fecha yyyy-mm-dd (primeros 10 caracteres) ignorando hora
              date_only = str(raw_estado).split("T")[0].split(" ")[0][:10]
              try:
                  estado_dt = datetime.strptime(date_only, "%Y-%m-%d")"""

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Corregido el parseo de raw_estado")
else:
    print("No se encontró el bloque exacto de raw_estado")
    
# Tambien arreglamos raw_inst por si acaso
old_code_inst = """          if raw_inst:
              date_only = str(raw_inst).split("T")[0]
              try:
                  inst_p_current = datetime.strptime(date_only, "%Y-%m-%d")"""

new_code_inst = """          if raw_inst:
              date_only = str(raw_inst).split("T")[0].split(" ")[0][:10]
              try:
                  inst_p_current = datetime.strptime(date_only, "%Y-%m-%d")"""

if old_code_inst in content:
    content = content.replace(old_code_inst, new_code_inst)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Corregido el parseo de raw_inst")

# Y raw_plan
old_code_plan = """         if raw_plan:
               date_only = str(raw_plan).split("T")[0]
               try:
                   plan_p = datetime.strptime(date_only, "%Y-%m-%d")"""

new_code_plan = """         if raw_plan:
               date_only = str(raw_plan).split("T")[0].split(" ")[0][:10]
               try:
                   plan_p = datetime.strptime(date_only, "%Y-%m-%d")"""

if old_code_plan in content:
    content = content.replace(old_code_plan, new_code_plan)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Corregido el parseo de raw_plan")
