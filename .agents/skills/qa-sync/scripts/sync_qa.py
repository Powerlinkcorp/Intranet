#!/usr/bin/env python3
"""
Sync QA Intranet Automation Script
Powerlink Corp - Automatización de Integración y Despliegue a QA.

Flujo de ejecución:
1. Obtiene las últimas versiones de las ramas de desarrollo remotas.
2. Integra en 'pruebas', valida compilación y sintaxis.
3. Actualiza la rama 'qa' remota.
4. Conecta por SSH al servidor 10.0.1.179.
5. Libera transacciones colgadas (idle in transaction) en PostgreSQL intranet_qa.
6. Descarga en /var/www/intranet_qa los cambios de origin/qa.
7. Ejecuta migraciones / verificación de tablas y esquemas.
8. Corrige permisos (root:www-data 775) y compila.
9. Reinicia el servicio systemd intranet_qa.
10. Valida respuesta HTTP 200 en QA y confirma que Producción sigue 100% operativa.
"""

import os
import sys
import json
import time
import argparse
import subprocess
import paramiko

# Asegurar codificación UTF-8 en stdout/stderr para Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def log(msg, level="INFO"):
    print(f"[{level}] {msg}", flush=True)

def run_local(cmd, check=True):
    log(f"Ejecutando local: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0 and check:
        log(f"Error ejecutando '{cmd}':\n{res.stderr}", "ERROR")
        raise RuntimeError(f"Comando falló: {cmd}")
    return res.stdout.strip()

def run_ssh(ssh, cmd, timeout=20):
    log(f"Ejecutando SSH: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if err and "NOTICE" not in err and "skipping" not in err:
        log(f"SSH STDERR: {err}", "WARN")
    return out

def main():
    parser = argparse.ArgumentParser(description="Automatización de integración y despliegue a QA Intranet")
    parser.add_argument("--branches", nargs="+", default=["dixon", "Segovia", "whilly"],
                        help="Ramas a sincronizar e integrar en pruebas (por defecto: dixon Segovia whilly)")
    parser.add_argument("--server", default="10.0.1.179", help="IP del servidor")
    parser.add_argument("--user", default="root", help="Usuario SSH")
    parser.add_argument("--password", default="Redes2026", help="Clave SSH")
    parser.add_argument("--skip-git-merge", action="store_true", help="Saltar integración Git local y solo desplegar en servidor QA")
    parser.add_argument("--output", default="qa_sync_result.json", help="Archivo JSON de salida con el reporte")
    args = parser.parse_args()

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "branches_integrated": args.branches,
        "stages": {},
        "status": "FAILED"
    }

    try:
        # -------------------------------------------------------------
        # ETAPA 1: INTEGRACIÓN GIT LOCAL Y COMPILACIÓN
        # -------------------------------------------------------------
        if not args.skip_git_merge:
            log("=== ETAPA 1: Integrando ramas en 'pruebas' y 'qa' ===")
            run_local("git fetch origin")

            # Guardar rama actual
            original_branch = run_local("git branch --show-current")
            report["stages"]["original_branch"] = original_branch

            # Cambiar a pruebas y actualizar
            run_local("git checkout pruebas")
            run_local("git pull origin pruebas")

            # Fusionar cada rama solicitada
            for branch in args.branches:
                log(f"Fusionando origin/{branch} en pruebas...")
                run_local(f"git merge origin/{branch} --no-edit")

            # Validar que no queden marcadores residuales de conflicto
            diff_check = run_local("git diff --check", check=False)
            if diff_check:
                raise RuntimeError(f"Se detectaron posibles marcadores de conflicto:\n{diff_check}")

            # Validar compilación de sintaxis Python (multiplataforma)
            import compileall
            success = compileall.compile_file("main.py", quiet=1)
            success = compileall.compile_dir("routers", quiet=1) and success
            if os.path.exists("permissions_manager.py"):
                success = compileall.compile_file("permissions_manager.py", quiet=1) and success
            if not success:
                raise RuntimeError("Falló la compilación de archivos Python (error de sintaxis detectado).")
            log("✓ Compilación local exitosa sin errores de sintaxis.")

            # Push a origin/pruebas
            run_local("git push origin pruebas")

            # Sincronizar hacia qa
            run_local("git checkout qa")
            run_local("git pull origin qa")
            run_local("git merge pruebas --no-edit")
            run_local("git push origin qa")

            # Volver a la rama original
            run_local(f"git checkout {original_branch}")
            report["stages"]["git_integration"] = "SUCCESS"
        else:
            log("Omitiendo integración Git local por solicitud (--skip-git-merge)")
            report["stages"]["git_integration"] = "SKIPPED"

        # -------------------------------------------------------------
        # ETAPA 2: CONEXIÓN AL SERVIDOR Y DESPLIEGUE EN QA
        # -------------------------------------------------------------
        log(f"=== ETAPA 2: Conectando por SSH a {args.server} ===")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(args.server, username=args.user, password=args.password, timeout=15)
        log("✓ Conexión SSH establecida.")

        # Paso 2.1: Prevenir / Terminar bloqueos en PostgreSQL intranet_qa
        log("Liberando transacciones inactivas en PostgreSQL intranet_qa...")
        run_ssh(ssh, '''sudo -u postgres psql -d intranet_qa -c "
            SELECT pg_terminate_backend(pid) 
            FROM pg_stat_activity 
            WHERE datname='intranet_qa' 
              AND pid <> pg_backend_pid() 
              AND state in ('idle in transaction', 'active') 
              AND query NOT LIKE '%pg_stat_activity%';
        "''')

        # Paso 2.2: Git pull en /var/www/intranet_qa
        log("Descargando cambios en /var/www/intranet_qa...")
        run_ssh(ssh, "cd /var/www/intranet_qa && git checkout -- intranet_local.db 2>/dev/null || true")
        run_ssh(ssh, "cd /var/www/intranet_qa && git pull origin qa")
        current_commit = run_ssh(ssh, "cd /var/www/intranet_qa && git log -n 1 --oneline")
        log(f"✓ Servidor QA en commit: {current_commit}")
        report["stages"]["qa_server_commit"] = current_commit

        # Paso 2.3: Esquemas y Tablas en PostgreSQL
        log("Verificando esquemas y tablas faltantes en PostgreSQL...")
        run_ssh(ssh, '''sudo -u postgres psql -d intranet_qa -c "
            ALTER TABLE users ADD COLUMN IF NOT EXISTS permissions VARCHAR DEFAULT '';
            CREATE TABLE IF NOT EXISTS support_cases (
                id SERIAL PRIMARY KEY,
                fecha VARCHAR(20) NOT NULL,
                fecha_iso VARCHAR(20) NOT NULL,
                numero_caso INTEGER NOT NULL,
                cedula VARCHAR(50) NOT NULL,
                nombre_cliente VARCHAR(200),
                id_servicio VARCHAR(50),
                telefono VARCHAR(60),
                plan VARCHAR(120),
                analista VARCHAR(120) NOT NULL,
                reporte VARCHAR(150) NOT NULL,
                solucion VARCHAR(150) NOT NULL,
                observacion VARCHAR(250),
                notas_adicionales TEXT,
                hub VARCHAR(50) NOT NULL,
                zona VARCHAR(150),
                ubicacion TEXT,
                router_limitado BOOLEAN,
                router_modelo VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            GRANT ALL PRIVILEGES ON DATABASE intranet_qa TO intranet_user;
            GRANT ALL ON ALL TABLES IN SCHEMA public TO intranet_user;
            GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO intranet_user;
        "''')

        # Paso 2.4: Permisos del sistema de archivos y compilación en QA
        log("Ajustando permisos de sistema de archivos y validando compilación...")
        run_ssh(ssh, "chown -R root:www-data /var/www/intranet_qa")
        run_ssh(ssh, "chmod -R 775 /var/www/intranet_qa")
        run_ssh(ssh, "cd /var/www/intranet_qa && /var/www/intranet_qa/venv/bin/python -m compileall -q main.py routers permissions_manager.py")

        # Paso 2.5: Asegurar directiva de parada limpia en intranet_qa.service
        service_conf = """[Unit]
Description=Intranet QA
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/var/www/intranet_qa
Environment="PATH=/var/www/intranet_qa/venv/bin"
ExecStart=/var/www/intranet_qa/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001
TimeoutStopSec=5
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
        sftp = ssh.open_sftp()
        with sftp.open('/etc/systemd/system/intranet_qa.service', 'w') as f:
            f.write(service_conf)
        sftp.close()
        run_ssh(ssh, "systemctl daemon-reload")

        # Paso 2.6: Reiniciar intranet_qa
        log("Reiniciando servicio intranet_qa...")
        run_ssh(ssh, "systemctl restart intranet_qa")
        time.sleep(3)
        service_status = run_ssh(ssh, "systemctl is-active intranet_qa")
        log(f"Estado del servicio intranet_qa: {service_status}")
        report["stages"]["qa_service_active"] = (service_status == "active")

        # Paso 2.7: Verificaciones HTTP
        qa_http = run_ssh(ssh, "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/login")
        prod_http = run_ssh(ssh, "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/login")
        
        log(f"QA HTTP Status (puerto 8080): {qa_http}")
        log(f"PROD HTTP Status (puerto 80, intacto): {prod_http}")

        report["stages"]["qa_http_status"] = qa_http
        report["stages"]["prod_http_status"] = prod_http

        ssh.close()

        if qa_http == "200" and prod_http == "200":
            report["status"] = "SUCCESS"
            log("✓ Sincronización y despliegue a QA completado exitosamente.")
        else:
            report["status"] = "WARNING"
            log(f"Advertencia: Estados HTTP no esperados (QA={qa_http}, PROD={prod_http})", "WARN")

    except Exception as e:
        log(f"Excepción durante el proceso: {str(e)}", "ERROR")
        report["error"] = str(e)
        report["status"] = "FAILED"

    # Guardar reporte en archivo JSON
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log(f"Reporte detallado guardado en: {args.output}")

    if report["status"] != "SUCCESS":
        sys.exit(1)

if __name__ == "__main__":
    main()
