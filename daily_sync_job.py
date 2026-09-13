import os
from datetime import datetime
from sqlalchemy.orm import Session
from database import engine, SessionLocal
from models import Client, ClientHistory

# Import the actual fetch logic from your main application
from main import fetch_powerlink_data

def sync_daily(db: Session):
    date_obj = datetime.now()
    print(f"[{date_obj.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando sincronización diaria con API...")
    
    try:
        api_response_res = fetch_powerlink_data(is_natural=True)
        api_response_corp = fetch_powerlink_data(is_natural=False)
        
        all_clients = []
        if api_response_res and 'data' in api_response_res:
            all_clients.extend(api_response_res['data'])
            
        if api_response_corp and 'data' in api_response_corp:
            all_clients.extend(api_response_corp['data'])
            
        if not all_clients:
            print("No se recibieron datos de la API.")
            return
            
    except Exception as e:
        print(f"Error consultando la API: {e}")
        return

    print(f"Se obtuvieron {len(all_clients)} registros de la API. Procesando...")
    
    for item in all_clients:
        sid = str(item.get('id_servicio', '')).strip()
        if not sid:
            continue
            
        # Map fields similarly to the frontend logic
        raw_st = str(item.get('service_status', '')).strip().upper()
        if raw_st == 'EXONERADO': mapped_st = 'Exo.'
        elif raw_st == 'SUSPENDIDO': mapped_st = 'Susp.'
        elif raw_st == 'POR RETIRAR': mapped_st = 'Por Ret.'
        elif raw_st == 'TRANSFERIDO': mapped_st = 'Trans.'
        elif raw_st == 'RETIRADO': mapped_st = 'Ret.'
        elif raw_st == 'ACTIVO': mapped_st = 'Act.'
        else: mapped_st = raw_st.title() if raw_st else ''
        mapped_st = mapped_st.upper() # Keep it upper case for consistency with import script
        
        doc_type = str(item.get('doc_type', '')).strip().upper()
        doc = str(item.get('doc', '')).strip()
        cedula = f"{doc_type}-{doc}"
        nombre = str(item.get('name', '')).strip()
        plan_actual = str(item.get('plan', '')).strip()
        fecha_inst = str(item.get('creation_date', '')).strip()
        
        is_nat = doc_type not in ('J', 'G', 'C')
        if 'is_natural' in item:
            is_nat = bool(item['is_natural'])
            
        tipo_cliente = "Residencial" if is_nat else "Corporativo"
        estado_actual = mapped_st
        
        db_client = db.query(Client).filter(Client.service_id == sid).first()
        
        if not db_client:
            new_client = Client(
                service_id=sid,
                cedula=cedula,
                name=nombre,
                client_type=tipo_cliente,
                current_plan=plan_actual,
                status=estado_actual,
                installation_date=fecha_inst,
                last_status_change_date=date_obj.strftime("%Y-%m-%d")
            )
            db.add(new_client)
            db.flush()
            
            hist = ClientHistory(
                client_id=new_client.id,
                record_date=date_obj,
                event_type="NUEVO_CLIENTE",
                old_value=None,
                new_value=estado_actual
            )
            db.add(hist)
        else:
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
    print("Sincronización diaria completada exitosamente.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        sync_daily(db)
    finally:
        db.close()
