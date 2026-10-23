---
name: git
description: Flujo estandarizado de Git y despliegue para la Intranet de Powerlink. Guía y ejecuta las etapas de desarrollo (commit y push a rama personal), integración a la rama pruebas, y el flujo del Administrador para despliegue seguro a QA y Producción en el servidor 10.0.1.179.
---

# Procedimiento Operativo Estándar: Git y Despliegues Intranet Powerlink

Este documento define las reglas obligatorias y los flujos de trabajo de Git para todo el equipo de desarrollo de la Intranet, así como el protocolo exclusivo de despliegue para el **Administrador**.

---

## 1. Mapa de Ramas del Proyecto

| Rama | Propósito | Responsable | Entorno Asociado |
| :--- | :--- | :--- | :--- |
| `<usuario>` *(whilly, dixon, etc.)* | Desarrollo activo de tareas asignadas | Desarrollador | Entorno Local |
| `pruebas` | Rama común de integración y validación previa | Desarrolladores / Equipo | Pruebas integradas locales |
| `qa` | Entorno de Aseguramiento de Calidad en servidor | **Solo Administrador** | Servidor QA (`10.0.1.179:8080`) |
| `Produccion` / `main` | Entorno productivo oficial para toda la empresa | **Solo Administrador** | Servidor Prod (`10.0.1.179:80`) |

> [!WARNING]
> Ningún desarrollador debe hacer push directo a las ramas `qa`, `Produccion` o `main`. Todo cambio debe pasar obligatoriamente por su rama de trabajo y luego ser integrado en `pruebas`.

---

## 2. Flujo del Desarrollador

### Paso 2.1: Finalizar el trabajo en la rama local
Antes de enviar cualquier cambio, verifica que no estés incluyendo archivos residuales o de entorno:
1. Revisa el estado de tus archivos:
   ```powershell
   git status
   ```
2. **Archivos Prohibidos en Git**: Asegúrate de que **NUNCA** se agreguen al control de versiones:
   - Archivos de entorno: `.env`
   - Bases de datos locales: `*.db`, `*.sqlite3`, `intranet_local.db`, `*.db-shm`, `*.db-wal`
   - Carpetas temporales: `__pycache__/`, `venv/`, `scratch/`
   - Logs: `*.log`
3. Valida la sintaxis del código antes de comitear:
   ```powershell
   python -m py_compile main.py routers/*.py
   ```

### Paso 2.2: Crear el Commit local
Agrega únicamente los archivos en los que trabajaste:
```powershell
git add ruta/al/archivo1.py templates/archivo2.html
git commit -m "tipo(modulo): breve descripcion clara del cambio"
```
*Ejemplos de commits:*
- `feat(operaciones): agregar filtro de fechas en modulo ozmap`
- `fix(chat): corregir recepcion de mensajes websocket`

### Paso 2.3: Subir a tu Rama Remota
1. Descarga posibles cambios remotos de tu rama primero:
   ```powershell
   git pull origin <tu-rama>
   ```
2. Sube tus cambios a tu rama remota en GitHub:
   ```powershell
   git push origin <tu-rama>
   ```

### Paso 2.4: Integrar hacia la Rama `pruebas`
Una vez que tus cambios están seguros en tu rama remota:
1. Obtén el estado más reciente del repositorio:
   ```powershell
   git fetch origin
   ```
2. Cambia a la rama `pruebas` y actualízala:
   ```powershell
   git checkout pruebas
   git pull origin pruebas
   ```
3. Fusiona tu rama en `pruebas`:
   ```powershell
   git merge <tu-rama>
   ```
4. **Validación Crucial Anti-Conflictos**:
   - Si Git indica conflictos, resuélvelos manualmente en tu editor.
   - **NUNCA** guardes un archivo con marcadores de conflicto (`<<<<<<<`, `=======`, `>>>>>>>`).
   - Verifica que no queden marcadores ejecutando:
     ```powershell
     # Comprobación de marcadores residuales
     git diff --check
     ```
   - Prueba la compilación:
     ```powershell
     python -m py_compile main.py routers/*.py
     ```
5. Sube la rama `pruebas` actualizada:
   ```powershell
   git push origin pruebas
   ```
6. Regresa a tu rama de trabajo para continuar:
   ```powershell
   git checkout <tu-rama>
   ```

---

## 3. Flujo Exclusivo del Administrador (QA y Producción)

Solo el Administrador está autorizado para desplegar cambios a los servidores.

### Paso 3.1: Promover de `pruebas` a `qa`
1. En local, fusionar `pruebas` en `qa`:
   ```powershell
   git checkout qa
   git pull origin qa
   git merge pruebas
   python -m py_compile main.py routers/*.py
   git push origin qa
   ```

### Paso 3.2: Actualizar el Servidor QA (`10.0.1.179:8080`)
1. Conectar al servidor mediante SSH:
   ```bash
   ssh root@10.0.1.179
   ```
2. Ir al directorio de QA y verificar que no existan modificaciones locales sucias:
   ```bash
   cd /var/www/intranet_qa
   git status
   ```
3. Descargar los cambios de QA:
   ```bash
   git pull origin qa
   ```
4. Validar sintaxis y que no existan marcadores residuales:
   ```bash
   grep -rn --exclude-dir={.git,venv,node_modules} '<<<<<<<' /var/www/intranet_qa
   /var/www/intranet_qa/venv/bin/python -m py_compile main.py routers/*.py
   ```
5. Reiniciar el servicio de QA y verificar su estado:
   ```bash
   systemctl restart intranet_qa
   systemctl status intranet_qa --no-pager
   curl -I http://127.0.0.1:8001/login
   ```
6. Realizar pruebas funcionales en el navegador accediendo a `http://10.0.1.179:8080`.

---

### Paso 3.3: Promover y Desplegar a Producción (`10.0.1.179:80`)
Una vez que el entorno de QA ha sido probado y certificado:

1. **Creación de Respaldo Preventivo Obligatorio (Rollback seguro)**:
   ```bash
   BACKUP_PROD=/var/www/intranet_prod_backup_$(date +%Y%m%d_%H%M%S)
   cp -a /var/www/intranet_prod $BACKUP_PROD
   echo "Respaldo creado en: $BACKUP_PROD"
   ```

2. **Sincronización segura QA -> Prod**:
   Sincronizar el código fuente verificado, preservando intactos la base de datos de producción, el entorno virtual (`venv`), la configuración `.env`, las subidas de usuarios y los logs:
   ```bash
   rsync -av --delete \
     --exclude='venv' \
     --exclude='.env' \
     --exclude='logs' \
     --exclude='static/uploads' \
     /var/www/intranet_qa/ /var/www/intranet_prod/
   ```

3. **Garantizar Permisos de Apache**:
   ```bash
   chown -R root:www-data /var/www/intranet_prod
   ```

4. **Validación de Compilación en Prod**:
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

## 4. Guía de Diagnóstico Rápido ante Incidentes

Si el servidor responde con error `502 Bad Gateway` o `503 Service Unavailable`:
1. **Comprobar qué servicio falló**:
   ```bash
   systemctl status intranet_qa --no-pager
   systemctl status intranet_prod --no-pager
   ```
2. **Revisar las últimas líneas del log de error del servicio**:
   ```bash
   journalctl -u intranet_qa --no-pager -n 50
   # o para producción:
   journalctl -u intranet_prod --no-pager -n 50
   ```
3. **Buscar errores de sintaxis o marcadores de conflicto**:
   ```bash
   grep -rn --exclude-dir={.git,venv,node_modules} '<<<<<<<' /var/www/intranet_qa
   ```
4. **Restauración de Emergencia (Rollback)**:
   Si el problema persiste en Producción, restaura inmediatamente el respaldo anterior:
   ```bash
   # Detener servicio
   systemctl stop intranet_prod
   # Restaurar desde el último backup
   rsync -av --delete /var/www/<directorio_backup>/ /var/www/intranet_prod/
   # Reiniciar
   systemctl restart intranet_prod
   ```

---

## 5. Protocolo de Ejecución Automática para Antigravity

Cuando un colaborador o desarrollador diga:
- *"Antigravity, sube mis cambios a pruebas"*
- *"Antigravity, integra mi trabajo en la rama pruebas"*
- O invoque la habilidad `git` para subir a pruebas:

Antigravity ejecutará **de forma autónoma e inmediata** la siguiente secuencia mediante la herramienta `run_command`:

### Paso 1: Detección y Blindaje de Rama
```powershell
git branch --show-current
```
- Si la rama actual es `pruebas`, `qa`, `Produccion` o `main`, **DETENERSE INMEDIATAMENTE** y alertar al usuario:
  *"No debes trabajar directamente sobre la rama protegida. Crea o cambia a tu rama personal primero."*
- Guardar el nombre de la rama actual en una variable (ej: `$MI_RAMA = "whilly"`).

### Paso 2: Auditoría de Archivos y Compilación Previa
```powershell
git status -s
```
- **Filtro de seguridad**: Si aparecen archivos `.env`, `*.db`, `*.sqlite3`, `intranet_local.db`, `*.db-shm`, `*.db-wal` o carpetas temporales, **NUNCA** hacer `git add .`.
- Validar compilación local:
```powershell
python -m py_compile main.py routers/*.py
```
- Si hay algún `SyntaxError`, **DETENERSE** y mostrar el error al usuario para corregirlo antes de continuar.

### Paso 3: Commit y Push a la Rama Personal
- Si hay cambios pendientes de comitear:
  - Preguntar o inferir un mensaje de commit claro según los archivos modificados.
  - Agregar solo los archivos de código/recursos válidos:
    ```powershell
    git add routers/ templates/ static/ (archivos específicos)
    git commit -m "feat/fix(modulo): descripción del cambio"
    ```
- Sincronizar y subir a la rama remota del colaborador:
```powershell
git pull origin <MI_RAMA> ; git push origin <MI_RAMA>
```

### Paso 4: Fusión e Integración a la Rama `pruebas`
```powershell
git fetch origin
git checkout pruebas
git pull origin pruebas
git merge <MI_RAMA>
```

### Paso 5: Verificación Anti-Conflictos y Compilación en `pruebas`
- Verificar ausencia total de marcadores de conflicto:
```powershell
git diff --check
```
- Si hay conflictos: **DETENERSE**, avisar al usuario qué archivos tienen conflicto y asistir en su resolución limpia.
- Validar compilación nuevamente:
```powershell
python -m py_compile main.py routers/*.py
```

### Paso 6: Publicar en `pruebas` y Regresar a la Rama Personal
```powershell
git push origin pruebas
git checkout <MI_RAMA>
```
- Confirmar al usuario con un reporte claro:
  - Cambios respaldados en `origin/<MI_RAMA>`.
  - Integración completada con éxito en `origin/pruebas`.
  - Rama de trabajo restaurada a `<MI_RAMA>`.
  - Notificar que el Administrador ya puede promover los cambios a QA.

