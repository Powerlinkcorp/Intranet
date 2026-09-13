import os

file_path = r'c:\Users\wgallardo\Documents\Proyectos gravity\intranet\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update ACTIVOS
old_activos = """          if estadoServicioNew == 'ACT.':
              if row.get('is_natural') is False:
                  totalActivosCorp += 1
              else:
                  totalActivos += 1
              ingreso_hoy += costoDelPlanNew
              datosClientesActivos.append({"""

new_activos = """          if estadoServicioNew == 'ACT.':
              if tipoServicioNew in ['PYME', 'CORPORATIVO']:
                  totalActivosCorp += 1
              elif tipoServicioNew == 'RESIDENCIAL':
                  totalActivos += 1
              
              ingreso_hoy += costoDelPlanNew
              datosClientesActivos.append({"""

if old_activos in content:
    content = content.replace(old_activos, new_activos)
    print("Activos updated")
else:
    print("Could not find Activos block")

# 2. Update SUSP.
old_susp = """              if row.get('is_natural') is False:
                  if estado_dt >= corte_corp:
                      totalSuspendidosFechaCorp += 1
              else:
                  if estado_dt >= corte_res:
                      totalSuspendidosFecha += 1"""

new_susp = """              if tipoServicioNew in ['PYME', 'CORPORATIVO']:
                  if estado_dt >= corte_corp:
                      totalSuspendidosFechaCorp += 1
              elif tipoServicioNew == 'RESIDENCIAL':
                  if estado_dt >= corte_res:
                      totalSuspendidosFecha += 1"""

if old_susp in content:
    content = content.replace(old_susp, new_susp)
    print("Susp updated")
else:
    print("Could not find Susp block")

# 3. Update EXO.
old_exo = """                  if '(emp)' in nombre_lower:
                      totalExoneradosEmp += 1
                  else:
                      if row.get('is_natural') is False:
                          totalExoneradosRegCorp += 1
                      else:
                          totalExoneradosReg += 1"""

new_exo = """                  if '(emp)' in nombre_lower:
                      totalExoneradosEmp += 1
                  else:
                      if tipoServicioNew in ['PYME', 'CORPORATIVO']:
                          totalExoneradosRegCorp += 1
                      elif tipoServicioNew == 'RESIDENCIAL':
                          totalExoneradosReg += 1"""

if old_exo in content:
    content = content.replace(old_exo, new_exo)
    print("Exo updated")
else:
    print("Could not find Exo block")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done!")
