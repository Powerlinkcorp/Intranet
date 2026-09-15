import os

file_path = r'c:\Users\wgallardo\Documents\Proyectos gravity\intranet\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Insert the boolean flags right after `count_activos_ayer += 1`
target_1 = """              if estatusOld == 'ACT.':
                  ingreso_ayer += costoOld
                  count_activos_ayer += 1"""

replacement_1 = """              if estatusOld == 'ACT.':
                  ingreso_ayer += costoOld
                  count_activos_ayer += 1
                  
              is_plan_in_range = True
              if plan_p and corte_dt and inst_dt:
                  is_plan_in_range = (corte_dt <= plan_p <= inst_dt)
                  
              is_estado_in_range = True
              if estado_dt and corte_dt and inst_dt:
                  is_estado_in_range = (corte_dt <= estado_dt <= inst_dt)"""

content = content.replace(target_1, replacement_1)

# Now replace the 'if' condition for Reconexiones
target_2 = "if estatusOld != 'ACT.' and estatusNew == 'ACT.':"
replacement_2 = "if estatusOld != 'ACT.' and estatusNew == 'ACT.' and is_estado_in_range:"
content = content.replace(target_2, replacement_2)

# Now replace the 'elif' condition for Retiros
target_3 = "elif estatusOld == 'ACT.' and estatusNew != 'ACT.':"
replacement_3 = "elif estatusOld == 'ACT.' and estatusNew != 'ACT.' and is_estado_in_range:"
content = content.replace(target_3, replacement_3)

# Now replace the 'elif' condition for Upgrades/Downgrades
target_4 = "elif estatusOld == 'ACT.' and estatusNew == 'ACT.':"
replacement_4 = "elif estatusOld == 'ACT.' and estatusNew == 'ACT.' and is_plan_in_range:"
content = content.replace(target_4, replacement_4)

# Replace 'if planOld != planNew:' for datosCambiosPlan
target_5 = """              if planOld != planNew:
                  datosCambiosPlan.append({"""
replacement_5 = """              if planOld != planNew and is_plan_in_range:
                  datosCambiosPlan.append({"""
content = content.replace(target_5, replacement_5)

# Replace 'if planOld != planNew or estatusOld != estatusNew:' for datosSeguimiento
target_6 = """              if planOld != planNew or estatusOld != estatusNew:
                  datosSeguimiento.append({"""
replacement_6 = """              if (planOld != planNew and is_plan_in_range) or (estatusOld != estatusNew and is_estado_in_range):
                  datosSeguimiento.append({"""
content = content.replace(target_6, replacement_6)

# Replace 'if estatusOld != estatusNew:' for datosEstatus
target_7 = """              if estatusOld != estatusNew:
                  datosEstatus.append({"""
replacement_7 = """              if estatusOld != estatusNew and is_estado_in_range:
                  datosEstatus.append({"""
content = content.replace(target_7, replacement_7)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Replacement successful")
