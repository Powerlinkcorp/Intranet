import os
from database import engine, Base, SessionLocal, DATABASE_URL
import models
from security import get_password_hash

def ensure_postgresql_database_exists():
    """Si se usa PostgreSQL, asegura que la base de datos intranet_db esté creada en el servidor."""
    if "postgresql" in DATABASE_URL:
        try:
            import psycopg2
            from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
            from urllib.parse import urlparse, unquote
            result = urlparse(DATABASE_URL)
            username = unquote(result.username) if result.username else 'postgres'
            password = unquote(result.password) if result.password else 'postgres'
            hostname = result.hostname or 'localhost'
            port = result.port or 5432
            dbname = unquote(result.path.lstrip('/')) or 'intranet_db'

            print(f"[INIT DB] Verificando base de datos PostgreSQL '{dbname}' en {hostname}:{port}...")
            con = psycopg2.connect(dbname='postgres', user=username, host=hostname, password=password, port=port, client_encoding='utf8')
            con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = con.cursor()
            cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (dbname,))
            exists = cur.fetchone()
            if not exists:
                cur.execute(f'CREATE DATABASE "{dbname}"')
                print(f"[INIT DB] Base de datos '{dbname}' creada con éxito.")
            else:
                print(f"[INIT DB] Base de datos '{dbname}' ya existe.")
            cur.close()
            con.close()
        except Exception as e:
            safe_err = str(e).encode('ascii', 'ignore').decode('ascii')
            print(f"[INIT DB] Aviso al verificar BD PostgreSQL: {safe_err}")

def init_db():
    ensure_postgresql_database_exists()
    print("[INIT DB] Creando tablas de base de datos...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1. Seed Default Users
        admin_user = db.query(models.User).filter(models.User.email == "admin@empresa.com").first()
        if not admin_user:
            admin_user = models.User(
                username="admin",
                email="admin@empresa.com",
                hashed_password=get_password_hash("Admin123!"),
                full_name="Gestor RRHH / Admin",
                role="admin",
                avatar_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=150"
            )
            db.add(admin_user)
            print("  + Usuario Admin creado: admin@empresa.com / Admin123!")

        sabina_user = db.query(models.User).filter(models.User.email == "sabina@empresa.com").first()
        if not sabina_user:
            sabina_user = models.User(
                username="ssabina",
                email="sabina@empresa.com",
                hashed_password=get_password_hash("User123!"),
                full_name="Sabina S.",
                role="user",
                avatar_url="https://images.unsplash.com/photo-1494790108377-be9c29b29330?q=80&w=150"
            )
            db.add(sabina_user)
            print("  + Usuario Estándar creado: sabina@empresa.com / User123!")

        # 2. Seed Hero Announcement
        if db.query(models.Announcement).count() == 0:
            announcement = models.Announcement(
                title="Sabina, ¡revisa las últimas noticias!",
                image_url="https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=1200",
                link_url="#"
            )
            db.add(announcement)
            print("  + Anuncio Principal inicial creado.")

        # 3. Seed Resources
        if db.query(models.Resource).count() == 0:
            resources = [
                models.Resource(title="Solicitud de Vacaciones", category="Solicitudes", file_path="/static/docs/planilla_vacaciones.pdf"),
                models.Resource(title="Aplicación Helpdesk Mobile", category="Aplicaciones", file_path="/static/docs/app_helpdesk.pdf"),
                models.Resource(title="Plantilla Informe Mensual", category="Plantillas", file_path="/static/docs/plantilla_informe.docx"),
                models.Resource(title="Manual del Empleado 2026", category="Manual Empleado", file_path="/static/docs/manual_empleado_2026.pdf"),
            ]
            db.add_all(resources)
            print("  + Recursos iniciales creados.")

        # 4. Seed Employees
        if db.query(models.Employee).count() == 0:
            employees = [
                models.Employee(name="Sabina S.", email="sabina@empresa.com", position="Analista de Procesos", photo_url="https://images.unsplash.com/photo-1494790108377-be9c29b29330?q=80&w=150", birthday_date="12 de Mayo"),
                models.Employee(name="Yaroslav P.", email="yaroslav@empresa.com", position="Desarrollador Senior", photo_url="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=150", birthday_date="24 de Septiembre"),
                models.Employee(name="Jane Smith", email="jsmith@empresa.com", position="Diseñadora UX/UI", photo_url="https://images.unsplash.com/photo-1438761681033-6461ffad8d80?q=80&w=150", birthday_date="03 de Noviembre"),
                models.Employee(name="Rosa Bell", email="rbell@empresa.com", position="Especialista RRHH", photo_url="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?q=80&w=150", birthday_date="08 de Agosto"),
                models.Employee(name="Carlos Mendoza", email="cmendoza@empresa.com", position="Coordinador de Operaciones", photo_url="https://images.unsplash.com/photo-1544005313-94ddf0286df2?q=80&w=150", birthday_date="18 de Julio"),
            ]
            db.add_all(employees)
            print("  + Empleados iniciales agregados.")

        # 5. Seed KPIs
        if db.query(models.KpiMetric).count() == 0:
            kpis = [
                models.KpiMetric(title="Clientes activos", value="23% ↑", trend="up"),
                models.KpiMetric(title="Clientes powerlink Go", value="5.2% ↑", trend="up"),
                models.KpiMetric(title="Zonas habilitadas", value="27.6K ↓", trend="down"),
            ]
            db.add_all(kpis)
            print("  + Métricas KPI iniciales agregadas.")

        # 6. Seed Calendar Event
        if db.query(models.CalendarEvent).count() == 0:
            event = models.CalendarEvent(day=15, month=7, year=2026, title="Reunión General de Equipo", description="Evaluación Trimestral de Resultados")
            db.add(event)
            print("  + Evento de calendario inicial creado.")

        # 7. Seed Sample Chat Message
        if db.query(models.ChatMessage).count() == 0:
            chat = models.ChatMessage(user_email="soporte@empresa.com", user_name="Soporte Intranet", channel="#General", message="¡Bienvenidos a la nueva plataforma Intranet!")
            db.add(chat)
            print("  + Mensaje de chat inicial creado.")

        db.commit()
        print("[INIT DB] Proceso de inicialización finalizado exitosamente.")
    except Exception as e:
        db.rollback()
        safe_err = str(e).encode('ascii', 'ignore').decode('ascii')
        print(f"[INIT DB] Error poblando base de datos: {safe_err}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
