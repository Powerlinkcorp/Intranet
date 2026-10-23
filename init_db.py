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

        # 2. Seed Hero Announcement
        if db.query(models.Announcement).count() == 0:
            announcement = models.Announcement(
                title="¡Bienvenidos a la plataforma Intranet Power Link!",
                image_url="https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=1200",
                link_url="#"
            )
            db.add(announcement)
            print("  + Anuncio Principal inicial creado.")

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
