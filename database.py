import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:1234@localhost:5432/intranet_db")
SQLITE_FALLBACK_URL = os.getenv("SQLITE_FALLBACK_URL", "sqlite:///./intranet_local.db")

_using_sqlite = False


def _get_pg_engine_with_encoding():
    """Crea engine PostgreSQL con encoding forzado a UTF-8 via connection_factory."""
    import psycopg2
    from urllib.parse import urlparse, unquote

    r = urlparse(DATABASE_URL)
    kwargs = dict(
        host=r.hostname or "localhost",
        port=r.port or 5432,
        user=unquote(r.username or "postgres"),
        password=unquote(r.password or ""),
        dbname=unquote(r.path.lstrip("/") or "intranet_db"),
        client_encoding="utf8",
    )

    def creator():
        return psycopg2.connect(**kwargs)

    engine = create_engine("postgresql+psycopg2://", creator=creator, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))  # Verify it works
    return engine


def _ensure_db_exists():
    """Asegura que la base de datos intranet_db exista en PostgreSQL."""
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from urllib.parse import urlparse, unquote

    r = urlparse(DATABASE_URL)
    username = unquote(r.username or "postgres")
    password = unquote(r.password or "")
    hostname = r.hostname or "localhost"
    port = r.port or 5432
    dbname = unquote(r.path.lstrip("/") or "intranet_db")

    con = psycopg2.connect(
        dbname="postgres", user=username, host=hostname,
        password=password, port=port, client_encoding="utf8"
    )
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = con.cursor()
    cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (dbname,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{dbname}" ENCODING=\'UTF8\'')
        print(f"[DATABASE] Base de datos '{dbname}' creada con éxito.")
    else:
        print(f"[DATABASE] Base de datos '{dbname}' verificada (ya existía).")
    cur.close()
    con.close()


def get_engine():
    global _using_sqlite
    engine = None
    if "postgresql" in DATABASE_URL:
        try:
            _ensure_db_exists()
            engine = _get_pg_engine_with_encoding()
            print(f"[DATABASE] OK Conectado a PostgreSQL exitosamente.")
        except Exception as e:
            msg = str(e).encode("ascii", "ignore").decode("ascii")
            print(f"[DATABASE] PostgreSQL no disponible ({msg[:80]}). Usando SQLite fallback.")
    if engine is None:
        _using_sqlite = True
        engine = create_engine(SQLITE_FALLBACK_URL, connect_args={"check_same_thread": False})
        print(f"[DATABASE] OK Usando SQLite local: {SQLITE_FALLBACK_URL}")

    # Auto-migrate: add permissions column if it doesn't exist
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN permissions VARCHAR DEFAULT ''"))
    except Exception:
        pass # Column likely already exists

    # Auto-migrate flasheo tables and columns
    for col_def in [
        "station_id VARCHAR(50) DEFAULT 'ESTACION-DEFAULT'",
        "sync_status VARCHAR(20) DEFAULT 'SYNCED'",
        "synced_at DATETIME"
    ]:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE onus_flasheadas ADD COLUMN {col_def}"))
        except Exception:
            pass

    return engine


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
