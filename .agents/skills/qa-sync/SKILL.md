---
name: qa-sync
description: >-
  Automatiza el ciclo de sincronización e integración de ramas de desarrollo (dixon, Segovia, whilly) hacia pruebas y qa, ejecutando la actualización segura y sin caídas en el servidor QA de la Intranet (10.0.1.179:8080) protegiendo el entorno de producción.
---

# Automatización de Sincronización y Despliegue en QA

## Overview
Esta habilidad ejecuta de forma automatizada y protegida el ciclo semanal de integración y despliegue al servidor de QA (`10.0.1.179:8080`), integrando los cambios de los colaboradores (`dixon`, `Segovia`, `whilly`) en las ramas `pruebas` y `qa`, liberando bloqueos en PostgreSQL, aplicando esquemas pendientes y reiniciando el servicio sin afectar bajo ninguna circunstancia el entorno de Producción (`/var/www/intranet_prod`).

## Dependencies
- Rama Git local y remota sincronizada.
- Python 3 con las librerías estándar y `paramiko`.
- Acceso SSH al servidor `10.0.1.179`.

## Quick Start
Para ejecutar la sincronización e integración a QA directamente:

```powershell
python .agents/skills/qa-sync/scripts/sync_qa.py
```

O si solo se desea sincronizar ramas específicas:
```powershell
python .agents/skills/qa-sync/scripts/sync_qa.py --branches dixon whilly
```

O si solo se desea re-desplegar en el servidor QA sin volver a fusionar localmente:
```powershell
python .agents/skills/qa-sync/scripts/sync_qa.py --skip-git-merge
```

## Utility Scripts

### `sync_qa.py`
Ubicado en `scripts/sync_qa.py`, realiza todas las etapas de validación e integración:

- **Argumentos**:
  - `--branches [rama1 rama2 ...]`: Ramas a integrar en `pruebas` y `qa` (por defecto: `dixon Segovia whilly`).
  - `--server [IP]`: IP del servidor (por defecto: `10.0.1.179`).
  - `--skip-git-merge`: Omite la fase de Git local y ejecuta directamente las comprobaciones y despliegue en el servidor remoto.
  - `--output [ruta.json]`: Archivo donde se escribe el reporte detallado en formato JSON (por defecto: `qa_sync_result.json`).

## Workflow

### 1. Integración Local y Verificación de Conflictos
- Obtiene (`fetch`) las últimas versiones de las ramas remotas de los desarrolladores (`dixon`, `Segovia`, `whilly`).
- Realiza merge hacia la rama `pruebas`.
- Valida que no existan marcadores residuales de conflicto (`git diff --check`).
- Ejecuta compilación local de Python (`python -m py_compile ...`) para asegurar que no hay errores de sintaxis antes de publicar.
- Publica en `origin/pruebas` y actualiza `origin/qa`.

### 2. Saneamiento de Base de Datos en QA
- Se conecta vía SSH a `10.0.1.179`.
- Termina conexiones en estado `idle in transaction` que puedan retener bloqueos en la base de datos `intranet_qa`.

### 3. Despliegue en Servidor QA
- Descarga los cambios en `/var/www/intranet_qa` mediante `git pull origin qa`.
- Valida y asegura la presencia de columnas y tablas requeridas (`permissions` en `users`, `support_cases`, etc.).
- Otorga permisos en el esquema PostgreSQL a `intranet_user`.
- Corrige permisos de archivos (`chown -R root:www-data`, `chmod -R 775`).
- Garantiza la directiva `TimeoutStopSec=5` en `intranet_qa.service`.
- Reinicia `intranet_qa.service` y verifica su estado activo.

### 4. Auditoría y Protección de Producción
- Consulta HTTP en el puerto 8080 (QA) confirmando `HTTP 200`.
- Consulta HTTP en el puerto 80 (Producción) confirmando `HTTP 200` y verificando que el entorno productivo no sufrió modificaciones.
- Genera el reporte final en archivo JSON.

## Common Mistakes
1. **Intentar desplegar en Producción sin autorización**: Este proceso está blindado y **NUNCA** toca `/var/www/intranet_prod`.
2. **Dejar transacciones colgadas en PostgreSQL**: Siempre se deben terminar las sesiones inactivas antes de aplicar sentencias DDL para no bloquear Uvicorn.
3. **No validar sintaxis antes del push**: Siempre se ejecuta `py_compile` para evitar que código con errores llegue al repositorio remoto.

