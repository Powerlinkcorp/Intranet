import pandas as pd
from sqlalchemy.orm import Session
from database import SessionLocal
import models
import security
import datetime
import random
import string
import unicodedata

def clean_text(text):
    if pd.isna(text):
        return ""
    return str(text).strip()

def remove_accents(input_str):
    if pd.isna(input_str):
        return ""
    nfkd_form = unicodedata.normalize('NFKD', str(input_str))
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

def generate_username(name, apellido, db):
    clean_n = remove_accents(name).lower().replace(" ", "")
    clean_a = remove_accents(apellido).lower().replace(" ", "")
    
    usuario = (clean_n[0] + clean_a) if len(clean_n) > 0 else "usuario"
    base_username = usuario
    counter = 1
    while db.query(models.User).filter(models.User.username == usuario).first():
        usuario = f"{base_username}{counter}"
        counter += 1
    return usuario

def main():
    file_path = r"C:\Users\wgallardo\Documents\LISTADO DE EMPLEADOS PARA LA INTRANET (1).xlsx"
    print(f"Cargando {file_path}...")
    df = pd.read_excel(file_path)
    
    # Encontrar nombre correcto de columnas independientemente de caracteres especiales (tildes)
    cols = df.columns.tolist()
    col_cedula = next((c for c in cols if 'dula' in c.lower()), None)
    col_cumple = next((c for c in cols if 'cumple' in c.lower()), None)
    col_correo = next((c for c in cols if 'correo' in c.lower()), None)
    
    db: Session = SessionLocal()
    
    try:
        # 1. Crear departamentos unicos
        departamentos = df['DEPARTAMENTOS'].dropna().unique()
        print(f"Encontrados {len(departamentos)} departamentos. Sincronizando...")
        for dept_name in departamentos:
            dept_name = str(dept_name).strip()
            existing_dept = db.query(models.Department).filter(models.Department.name == dept_name).first()
            if not existing_dept:
                new_dept = models.Department(name=dept_name)
                db.add(new_dept)
        db.commit()
        
        # 2. Iterar empleados y crearlos
        created_count = 0
        skipped_count = 0
        
        for idx, row in df.iterrows():
            nombre = clean_text(row.get('nombre', ''))
            apellido = clean_text(row.get('apellido', ''))
            if not nombre and not apellido:
                continue
                
            email = clean_text(row.get(col_correo, ''))
            department = clean_text(row.get('DEPARTAMENTOS', 'General'))
            cargo = clean_text(row.get('CARGO', 'Empleado'))
            cedula = clean_text(row.get(col_cedula, ''))
            
            # Formatear fecha
            birthday_date = ""
            raw_bday = row.get(col_cumple, None)
            if pd.notna(raw_bday):
                if isinstance(raw_bday, datetime.datetime):
                    birthday_date = raw_bday.strftime('%Y-%m-%d')
                else:
                    birthday_date = str(raw_bday)[:10]

            # Generar contraseña y usuario tempranamente para el email si está vacío
            usuario = generate_username(nombre, apellido, db)
            if not email:
                email = f"{usuario}@empresa.com"

            # Verificar si ya existe el usuario por email
            if email:
                if db.query(models.User).filter(models.User.email == email).first():
                    print(f"Saltando a {nombre} {apellido} - Email {email} ya existe.")
                    skipped_count += 1
                    continue
            
            # Crear empleado (retrocompatibilidad)
            photo_url = "https://ngfihmioixtfnrmlrlam.supabase.co/storage/v1/object/public/power/WhatsApp_Image_2026-03-20_at_3.44.14_PM-removebg-preview.png"
            
            # A veces la cédula ya existe en Employee table (por antiguos test)
            if cedula:
                existing_emp = db.query(models.Employee).filter(models.Employee.cedula == cedula).first()
                if existing_emp:
                    pass # Solo lo ignoramos en la tabla antigua
                else:
                    emp = models.Employee(
                        name=nombre, apellido=apellido, email=email, position=cargo, 
                        department=department, cedula=cedula, birthday_date=birthday_date, 
                        photo_url=photo_url
                    )
                    db.add(emp)
            else:
                emp = models.Employee(
                    name=nombre, apellido=apellido, email=email, position=cargo, 
                    department=department, cedula=cedula, birthday_date=birthday_date, 
                    photo_url=photo_url
                )
                db.add(emp)
            
            # Generar contraseña y usuario
            usuario = generate_username(nombre, apellido, db)
            palabras = ['Power', 'Link', 'Gravity', 'System', 'Secure', 'Admin']
            password = random.choice(palabras) + random.choice(['*','#','$','&','@']) + str(random.randint(100,999))
            hashed_pw = security.get_password_hash(password)
            
            new_user = models.User(
                username=usuario,
                email=email or f"{usuario}@empresa.com",
                hashed_password=hashed_pw,
                full_name=f"{nombre} {apellido}",
                role="user",
                avatar_url=photo_url,
                cargo=cargo,
                department=department,
                birthday_date=birthday_date
            )
            db.add(new_user)
            db.commit()
            created_count += 1
            
        print(f"\nFinalizado. Creados: {created_count}. Omitidos: {skipped_count}.")
        
    except Exception as e:
        print(f"Error durante migración: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    main()
