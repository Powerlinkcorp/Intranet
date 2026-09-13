import os
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from database import engine, SessionLocal
from models import Client, ClientHistory

BASE_DIR = r"Z:\Integracion\Data Integracion Whilly\integracion whilly cuadros diarios"

def process_folder(folder_path, date_obj, db: Session):
    print(f"Procesando carpeta: {folder_path} - Fecha: {date_obj}")
    
    # Archivos a buscar
    # Pueden tener sufijos con la hora como (1_2_2026, 7_54 a. m.).xlsx
    # Usaremos una búsqueda parcial
    excel_files = [f for f in os.listdir(folder_path) if f.endswith('.xlsx') or f.endswith('.xls')]
    
    res_file = next((f for f in excel_files if 'Listado_de_clientes_juridicos' not in f and 'Listado_de_clientes' in f), None)
    corp_file = next((f for f in excel_files if 'Listado_de_clientes_juridicos' in f), None)
    
    all_clients = []
    
    if res_file:
        try:
            # pandas ignores UI filters in excel automatically, giving the raw flat data.
            df_res = pd.read_excel(os.path.join(folder_path, res_file))
            df_res['ClientType'] = 'Residencial'
            all_clients.append(df_res)
        except Exception as e:
            print(f"Error leyendo {res_file}: {e}")
            
    if corp_file:
        try:
            df_corp = pd.read_excel(os.path.join(folder_path, corp_file))
            df_corp['ClientType'] = 'Corporativo'
            all_clients.append(df_corp)
        except Exception as e:
            print(f"Error leyendo {corp_file}: {e}")

    if not all_clients:
        print("No se encontraron archivos válidos en esta carpeta.")
        return
        
    df_combined = pd.concat(all_clients, ignore_index=True)
    
    # Mapeo de columnas
    col_map = {
        'ID Servicio': 'id_servicio',
        'Cédula': 'cedula',
        'Nombres': 'nombres',
        'Plan': 'plan',
        'Estado servicio': 'estado',
        'Fecha de instalación': 'fecha_instalacion'
    }
    
    for col in col_map.keys():
        if col not in df_combined.columns:
             for real_col in df_combined.columns:
                 if col.lower() in real_col.lower():
                     df_combined.rename(columns={real_col: col_map[col]}, inplace=True)
                     break
        else:
             df_combined.rename(columns={col: col_map[col]}, inplace=True)

    for index, row in df_combined.iterrows():
        id_servicio = str(row.get('id_servicio', '')).strip()
        if not id_servicio or id_servicio == 'nan':
            continue
            
        nombre = str(row.get('nombres', '')).strip()
        cedula = str(row.get('cedula', '')).strip()
        plan_actual = str(row.get('plan', '')).strip()
        estado_actual = str(row.get('estado', '')).strip().upper()
        fecha_inst = str(row.get('fecha_instalacion', '')).strip()
        tipo_cliente = row.get('ClientType', 'Residencial')
        
        # Buscar cliente existente en BD
        db_client = db.query(Client).filter(Client.service_id == id_servicio).first()
        
        if not db_client:
            # Cliente nuevo
            new_client = Client(
                service_id=id_servicio,
                cedula=cedula,
                name=nombre,
                client_type=tipo_cliente,
                current_plan=plan_actual,
                status=estado_actual,
                installation_date=fecha_inst,
                last_status_change_date=date_obj.strftime("%Y-%m-%d")
            )
            db.add(new_client)
            db.flush() # Para obtener el ID
            
            hist = ClientHistory(
                client_id=new_client.id,
                record_date=date_obj,
                event_type="NUEVO_CLIENTE",
                old_value=None,
                new_value=estado_actual
            )
            db.add(hist)
        else:
            # Cliente existente, chequear cambios
            if db_client.status != estado_actual:
                hist_status = ClientHistory(
                    client_id=db_client.id,
                    record_date=date_obj,
                    event_type="CAMBIO_ESTATUS",
                    old_value=db_client.status,
                    new_value=estado_actual
                )
                db.add(hist_status)
                db_client.status = estado_actual
                db_client.last_status_change_date = date_obj.strftime("%Y-%m-%d")
                
            if db_client.current_plan != plan_actual:
                hist_plan = ClientHistory(
                    client_id=db_client.id,
                    record_date=date_obj,
                    event_type="CAMBIO_PLAN",
                    old_value=db_client.current_plan,
                    new_value=plan_actual
                )
                db.add(hist_plan)
                db_client.current_plan = plan_actual
                
    db.commit()


def main():
    if not os.path.exists(BASE_DIR):
        print(f"No se encontró el directorio base: {BASE_DIR}")
        return

    # Obtener carpetas y ordenarlas por fecha
    folders = []
    for item in os.listdir(BASE_DIR):
        item_path = os.path.join(BASE_DIR, item)
        if os.path.isdir(item_path):
            try:
                # El formato es dd mm yyyy (con espacios)
                # Ejemplo: "01 02 2026"
                parts = item.split()
                if len(parts) >= 3:
                    date_str = f"{parts[0]} {parts[1]} {parts[2]}"
                    date_obj = datetime.strptime(date_str, "%d %m %Y")
                    folders.append((date_obj, item_path))
            except ValueError:
                pass
                
    # Ordenar cronológicamente
    folders.sort(key=lambda x: x[0])
    
    db = SessionLocal()
    try:
        for date_obj, folder_path in folders:
            process_folder(folder_path, date_obj, db)
    finally:
        db.close()
        
    print("Importación histórica completada.")

if __name__ == "__main__":
    main()
