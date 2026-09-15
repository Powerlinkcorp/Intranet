import os
import re

file_path = r'c:\Users\wgallardo\Documents\Proyectos gravity\intranet\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# I will find the block starting with:
#               billingAyer = costoOld if estatusOld == 'ACT.' else 0.0
# and replace the logic until the end of datosEstatus.append

pattern = re.compile(r"(billingAyer = costoOld if estatusOld == 'ACT\.' else 0\.0\s+billingHoy = costoDelPlanNew if estatusNew == 'ACT\.' else 0\.0\s+variacionNeta = billingHoy - billingAyer\s+if estatusOld == 'ACT\.':\s+ingreso_ayer \+= costoOld\s+count_activos_ayer \+= 1\s+)(.*?)(          else:\s+if estadoServicioNew == 'ACT\.':)", re.DOTALL)

def replacer(match):
    prefix = match.group(1)
    core = match.group(2)
    suffix = match.group(3)
    
    new_core = """
              is_plan_in_range = True
              if plan_p and corte_dt and inst_dt:
                  is_plan_in_range = (corte_dt <= plan_p <= inst_dt)
                  
              is_estado_in_range = True
              if estado_dt and corte_dt and inst_dt:
                  is_estado_in_range = (corte_dt <= estado_dt <= inst_dt)

              # Finanzas - Bridge
              if estatusOld != 'ACT.' and estatusNew == 'ACT.' and is_estado_in_range:
                  impacto_reconexiones += costoDelPlanNew
                  count_reconexiones += 1
                  datosConciliacionDetalle.append({
                      'ID Servicio': sid,
                      'Cédula': row['Cédula'],
                      'Nombres': row['Nombres'],
                      'Concepto': 'Reconexiones',
                      'Plan Anterior': planOld,
                      'Plan Actual': planNew,
                      'Estado Anterior': estatusOld,
                      'Estado Actual': estatusNew,
                      'Costo Anterior': costoOld,
                      'Costo Actual': costoDelPlanNew,
                      'Variación': costoDelPlanNew,
                      'Fecha': fechaEstadoFormat
                  })
              elif estatusOld == 'ACT.' and estatusNew != 'ACT.' and is_estado_in_range:
                  if estado_dt >= corte_dt:
                      impacto_retiros_post_corte += costoOld
                      count_retiros_post_corte += 1
                  else:
                      impacto_retiros_pre_corte += costoOld
                      count_retiros_pre_corte += 1
                  datosConciliacionDetalle.append({
                      'ID Servicio': sid,
                      'Cédula': row['Cédula'],
                      'Nombres': row['Nombres'],
                      'Concepto': 'Retiros',
                      'Plan Anterior': planOld,
                      'Plan Actual': planNew,
                      'Estado Anterior': estatusOld,
                      'Estado Actual': estatusNew,
                      'Costo Anterior': costoOld,
                      'Costo Actual': 0.0,
                      'Variación': -costoOld,
                      'Fecha': fechaEstadoFormat
                  })
              elif estatusOld == 'ACT.' and estatusNew == 'ACT.' and is_plan_in_range:
                  if costoDelPlanNew > costoOld:
                      if '3 MESES BENEFICIO' in planOld.upper() or '3 MESES BENEFICIO' in planNew.upper():
                          impacto_upgrades_beneficio += (costoDelPlanNew - costoOld)
                          count_upgrades_beneficio += 1
                          concepto_upg = 'Cambios 3 Meses Beneficio a otro Plan'
                      else:
                          impacto_upgrades += (costoDelPlanNew - costoOld)
                          count_upgrades += 1
                          concepto_upg = 'Upgrades de Plan'
                      datosConciliacionDetalle.append({
                          'ID Servicio': sid,
                          'Cédula': row['Cédula'],
                          'Nombres': row['Nombres'],
                          'Concepto': concepto_upg,
                          'Plan Anterior': planOld,
                          'Plan Actual': planNew,
                          'Estado Anterior': estatusOld,
                          'Estado Actual': estatusNew,
                          'Costo Anterior': costoOld,
                          'Costo Actual': costoDelPlanNew,
                          'Variación': costoDelPlanNew - costoOld,
                          'Fecha': fechaPlanDesdeFormat
                      })
                  elif costoDelPlanNew < costoOld:
                      impacto_downgrades += (costoOld - costoDelPlanNew)
                      count_downgrades += 1
                      datosConciliacionDetalle.append({
                          'ID Servicio': sid,
                          'Cédula': row['Cédula'],
                          'Nombres': row['Nombres'],
                          'Concepto': 'Downgrades de Plan',
                          'Plan Anterior': planOld,
                          'Plan Actual': planNew,
                          'Estado Anterior': estatusOld,
                          'Estado Actual': estatusNew,
                          'Costo Anterior': costoOld,
                          'Costo Actual': costoDelPlanNew,
                          'Variación': -(costoOld - costoDelPlanNew),
                          'Fecha': fechaPlanDesdeFormat
                      })
              
              if planOld != planNew and is_plan_in_range:
                  datosCambiosPlan.append({
                      'ID Servicio': sid,
                      'Cédula': row['Cédula'],
                      'Nombres': row['Nombres'],
                      'Plan Anterior': planOld,
                      'Plan Nuevo': planNew,
                      'Costo Anterior': costoOld,
                      'Costo Nuevo': costoDelPlanNew,
                      'Variación de Costo': variacionNeta,
                      'Estado Actual': row['Estado servicio'],
                      'Estado Anterior': estatusOld,
                      'Estado Nuevo': estatusNew,
                      'Fecha Plan Actual Desde': fechaPlanDesdeFormat 
                  })
                  
              if (planOld != planNew and is_plan_in_range) or (estatusOld != estatusNew and is_estado_in_range):
                  datosSeguimiento.append({
                      'ID Servicio': sid,
                      'Cédula': row['Cédula'],
                      'Nombres': row['Nombres'],
                      'Plan Anterior': planOld,
                      'Plan Nuevo': planNew,
                      'Costo Anterior': costoOld,
                      'Costo Nuevo': costoDelPlanNew,
                      'Variación de Costo': variacionNeta,
                      'Estado Anterior': estatusOld,
                      'Estado Nuevo': estatusNew,
                      'Fecha último Cambio Estado': fechaEstadoFormat,
                      'Fecha Plan Actual Desde': fechaPlanDesdeFormat
                  })
                  
              if estatusOld != estatusNew and is_estado_in_range:
                  datosEstatus.append({
                      'ID Servicio': sid,
                      'Cédula': row['Cédula'],
                      'Nombres': row['Nombres'],
                      'Plan Actual': planNew,
                      'Costo Anterior': costoOld,
                      'Costo Nuevo': costoDelPlanNew,
                      'Variación de Costo': variacionNeta,
                      'Estado Anterior': estatusOld,
                      'Estado Nuevo': estatusNew,
                      'Fecha último Cambio Estado': fechaEstadoFormat
                  })
"""
    return prefix + new_core + suffix

# Important: Need to replace special characters 'CǸdula' back to 'Cédula' or whatever they were, 
# But wait! Python script output earlier showed 'CǸdula' which might just be PowerShell garbling UTF-8. 
# Inside the real file, it's 'Cédula' and 'Variación'. I'll write 'Cédula' explicitly. 
# Also 'Fecha último Cambio Estado' instead of 'Fecha sltimo...'

content_new = pattern.sub(replacer, content)

if content_new != content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content_new)
    print("Changes applied.")
else:
    print("Pattern not found!")
