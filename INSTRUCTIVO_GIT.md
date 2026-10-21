# Instructivo Oficial de Trabajo con Git y Despliegues — Intranet Powerlink

Este manual establece la metodología oficial para el desarrollo, control de versiones y despliegue continuo de la Intranet de Powerlink.

---

## 📌 1. Flujo General de Ramas (Diagrama)

```mermaid
gitGraph
   commit id: "Base"
   branch pruebas
   checkout pruebas
   commit id: "Integración"
   branch whilly
   checkout whilly
   commit id: "feat: mi tarea"
   commit id: "fix: ajustes"
   checkout pruebas
   merge whilly id: "Merge a Pruebas"
   branch qa
   checkout qa
   merge pruebas id: "Admin: Despliegue QA (8080)"
   branch produccion
   checkout produccion
   merge qa id: "Admin: Despliegue Prod (80)"
```

### Roles y Responsabilidades
* **Desarrollador (`whilly`, `dixon`, `brando`, `cedres`, etc.)**: Desarrolla en su rama local, sube a su rama remota y luego integra en la rama `pruebas`.
* **Administrador**: Es el **único autorizado** para tomar los cambios probados de la rama `pruebas`, pasarlos a `qa` y desplegarlos a los servidores (QA `10.0.1.179:8080` y Producción `10.0.1.179:80`).

---

## 💻 2. Guía para el Desarrollador (Paso a Paso)

### 2.1 Al terminar de trabajar en tu rama local
1. **Revisa los archivos modificados**:
   ```powershell
   git status
   ```
2. **⚠️ Lista Negra de Archivos (NUNCA agregarlos a Git)**:
   - Archivos de credenciales y variables: `.env`
   - Bases de datos locales o temporales: `*.db`, `*.sqlite3`, `intranet_local.db`, `*.db-shm`, `*.db-wal`
   - Caché de compilación: `__pycache__/`, `*.pyc`
   - Entornos virtuales y logs: `venv/`, `*.log`, `scratch/`

3. **Verifica la integridad de tu código**:
   Ejecuta una comprobación de sintaxis antes de guardar:
   ```powershell
   python -m py_compile main.py routers/*.py
   ```

### 2.2 Crear el Commit local
Agrega **únicamente** los archivos modificados para tu tarea (evita usar `git add .` a ciegas):
```powershell
git add routers/mi_router.py templates/mi_vista.html static/js/app.js
git commit -m "tipo(modulo): breve descripcion del cambio"
```

> **Convención recomendada de commits:**
> - `feat(...)`: Nueva funcionalidad.
> - `fix(...)`: Corrección de un error.
> - `style(...)`: Cambios visuales o de CSS sin afectar lógica.
> - `refactor(...)`: Reestructuración de código sin alterar su comportamiento.

### 2.3 Subir a tu Rama Remota
1. Descarga posibles cambios remotos de tu rama personal:
   ```powershell
   git pull origin <tu-rama>
   ```
2. Sube tus cambios al repositorio remoto:
   ```powershell
   git push origin <tu-rama>
   ```

### 2.4 Integrar hacia la Rama `pruebas`
Una vez que tus cambios están asegurados en tu rama:
1. Trae el historial remoto actualizado:
   ```powershell
   git fetch origin
   ```
2. Cambia a la rama `pruebas` y actualízala:
   ```powershell
   git checkout pruebas
   git pull origin pruebas
   ```
3. Fusiona tu rama de trabajo:
   ```powershell
   git merge <tu-rama>
   ```
4. **⚠️ Regla de Oro Anti-Conflictos**:
   - Si se presentan conflictos, resuélvelos en tu editor (VS Code / Antigravity).
   - **NUNCA** dejes marcas residuales (`<<<<<<< HEAD`, `=======`, `>>>>>>>`).
   - Verifica que no queden marcadores ejecutando:
     ```powershell
     git diff --check
     ```
   - Compila para asegurarte de que el código no tenga errores de sintaxis:
     ```powershell
     python -m py_compile main.py routers/*.py
     ```
5. Sube la rama `pruebas` actualizada a GitHub:
   ```powershell
   git push origin pruebas
   ```
6. Regresa a tu rama para continuar trabajando:
   ```powershell
   git checkout <tu-rama>
   ```

---

## 🛡️ 3. Guía Exclusiva del Administrador (QA y Producción)

> [!IMPORTANT]
> Solo el Administrador debe ejecutar estos pasos para garantizar que los entornos del servidor (`10.0.1.179`) no se interrumpan.

### 3.1 Promover de `pruebas` a `qa`
1. En tu máquina local, actualiza la rama `qa` con los cambios de `pruebas`:
   ```powershell
   git checkout qa
   git pull origin qa
   git merge pruebas
   python -m py_compile main.py routers/*.py
   git push origin qa
   ```

### 3.2 Despliegue en el Servidor QA (`10.0.1.179:8080`)
1. Conéctate por SSH al servidor:
   ```bash
   ssh root@10.0.1.179
   ```
2. Accede a la carpeta de QA y actualiza:
   ```bash
   cd /var/www/intranet_qa
   git status
   git pull origin qa
   ```
3. Valida que no haya marcadores residuales ni errores:
   ```bash
   grep -rn --exclude-dir={.git,venv,node_modules} '<<<<<<<' /var/www/intranet_qa
   /var/www/intranet_qa/venv/bin/python -m py_compile main.py routers/*.py
   ```
4. Reinicia el servicio y verifica:
   ```bash
   systemctl restart intranet_qa
   systemctl status intranet_qa --no-pager
   curl -I http://127.0.0.1:8001/login
   ```
5. Prueba en el navegador accediendo a: `http://10.0.1.179:8080`.

---

### 3.3 Despliegue en el Servidor de Producción (`10.0.1.179:80`)
Una vez que el entorno de QA fue probado y validado por los usuarios o el equipo:

1. **Crear Respaldo Preventivo Obligatorio (Rollback)**:
   ```bash
   BACKUP_DIR=/var/www/intranet_prod_backup_$(date +%Y%m%d_%H%M%S)
   cp -a /var/www/intranet_prod $BACKUP_DIR
   echo "Respaldo seguro creado en: $BACKUP_DIR"
   ```

2. **Sincronización Segura QA hacia Producción**:
   Se sincroniza el código verificado manteniendo intactos `.env`, `venv`, subidas de archivos (`static/uploads`) y logs:
   ```bash
   rsync -av --delete \
     --exclude='venv' \
     --exclude='.env' \
     --exclude='logs' \
     --exclude='static/uploads' \
     /var/www/intranet_qa/ /var/www/intranet_prod/
   ```

3. **Garantizar Permisos del Servidor Web**:
   ```bash
   chown -R root:www-data /var/www/intranet_prod
   ```

4. **Validación de Compilación en Producción**:
   ```bash
   cd /var/www/intranet_prod
   /var/www/intranet_prod/venv/bin/python -m py_compile main.py routers/*.py
   ```

5. **Reinicio y Verificación de Producción**:
   ```bash
   systemctl restart intranet_prod
   systemctl status intranet_prod --no-pager
   curl -I http://127.0.0.1:8000/login
   curl -I http://10.0.1.179:80/login
   ```

---

## 🚨 4. Protocolo de Emergencia ante Errores 502 / 503

Si tras una actualización el servidor deja de responder:

1. **Identificar qué servicio falló**:
   ```bash
   systemctl status intranet_qa --no-pager
   systemctl status intranet_prod --no-pager
   ```
2. **Revisar el registro del error exacto en Uvicorn**:
   ```bash
   journalctl -u intranet_qa --no-pager -n 50
   # o para producción:
   journalctl -u intranet_prod --no-pager -n 50
   ```
3. **Buscar marcadores de conflicto no resueltos**:
   ```bash
   grep -rn --exclude-dir={.git,venv,node_modules} '<<<<<<<' /var/www/intranet_qa
   ```
4. **Restaurar el respaldo (Rollback Inmediato en Producción)**:
   ```bash
   systemctl stop intranet_prod
   rsync -av --delete /var/www/<nombre_carpeta_backup>/ /var/www/intranet_prod/
   systemctl restart intranet_prod
   ```

---

## 🤖 5. Uso de la Habilidad Antigravity `git`

Puedes pedirle a Antigravity que realice cualquiera de estos pasos de forma automática diciendo simplemente:
- *"Antigravity, usa la habilidad git para subir mis cambios actuales a mi rama y luego a pruebas"*
- *"Antigravity, sube mis cambios a mi rama remota"*
- *"Antigravity, como administrador actualiza qa desde pruebas y despliega en el servidor"*
- *"Antigravity, clona y despliega QA a Producción con respaldo preventivo"*
- *"Antigravity, verifica la salud de los servicios de QA y Producción"*
