# Contexto de Sesión — Módulo de Documentación de Casos y Estadísticas de Soporte Remoto

**Rama:** `Segovia`  
**Usuario:** Daniel Segovia  
**Fecha de corte:** 21 de Octubre de 2026  

---

## 1. Resumen de Funcionalidades Implementadas

### A. Prioridad a la Dirección Oficial de la API de Rubpi
- Para todos los clientes cuya Cédula/RIF existe en el padrón de Rubpi (`static/uploads/last_snapshot.json` y `last_snapshot_corporativo.json`), se prioriza siempre la dirección física oficial, nombre del titular, ID de contrato y macro-zona normalizada.
- Se eliminaron las discrepancias de analistas que seleccionaban sub-sectores erróneos en el Google Sheet (ejemplo: Cédula `21119429` María Curvelo `#53031`, cuyos 19 casos históricos ahora muestran su dirección oficial en `Clavelito Sector la fila casa número 36`).
- **San Pedro** se encuentra unificado bajo la macro-zona **`LOS TEQUES`**.

### B. Normalización Inteligente de HUBs
- En clientes con una sola dirección física, el HUB se unifica automáticamente a la **moda/HUB dominante histórico** del cliente (ejemplo: María Curvelo normalizada 100% a `CUM`, corrigiendo registros erróneos donde se le había colocado `CMDP`).
- **Exclusión multi-servicio:** Clientes con 2 o más contratos de fibra en direcciones físicas distintas (`537` clientes) no se unifican para respetar que cada inmueble pueda pertenecer a un HUB diferente.
- Al documentar un caso nuevo, el sistema preselecciona automáticamente el HUB dominante histórico del cliente.

### C. Reporte de Coincidencia y Alarmas por Cliente (Semanal y Mensual)
- Ubicado en la sección **6 de Estadísticas de Soporte** (`#panelAlarmasReincidencia`).
- **Filtros:**
  - **Vista Semanal:** Evalúa coincidencias en los últimos 7 días.
  - **Vista Mensual:** Selector de mes (`Octubre 2026`, `Septiembre 2026`, etc.).
  - **Todo el Historial:** Análisis anual.
  - Filtro por HUB y buscador directo por Cédula/Nombre.
- **Semáforo de Alarmas:**
  - 🔴 **CRÍTICA:** $\ge 3$ reportes en 7 días o $\ge 5$ reportes en el mes.
  - 🟠 **ALTA:** $2$ reportes en 7 días o $3\text{--}4$ reportes en el mes.
  - 🟡 **OBSERVACIÓN:** Reincidencia moderada.
- **Ficha Simplificada del Cliente (`#modalDetalleReincidencia`):**
  - Al dar clic sobre cualquier cliente (ejemplo: `8680370` Elizabeth Galindez en Octubre 2026), la ficha se abre mostrando **exclusivamente lo ocurrido en el rango de alarma consultado**:
    1. Datos del cliente + total de reportes en el periodo.
    2. Conteo de Fallas Reportadas en el rango vs. Resoluciones Aplicadas en el rango.
    3. Detalle caso por caso de ese rango (Fecha, N° Caso, Falla Reportada, Resolución Aplicada, Analista).

### D. Otras Herramientas Activas
- **Generador de Corte WhatsApp (6:00 PM / 10:00 PM):** Conteo 100% automático de Rubpi, Llamadas y Taquilla, motivos ordenados A-Z, constructor de afectaciones (REALIZADA / EN PROCESO) y botón de 1 clic para copiar.
- **Creador Masivo de Tickets de Afectación:** Generación de 1 a 500 tickets consecutivos sin cédula (`S/C - AFECTACIÓN`) con catálogo oficial de 342 sub-sectores.

---

## 2. Instrucciones para Reanudar en PC de Casa
1. Abrir la terminal en la carpeta del proyecto y verificar estar en la rama `Segovia`:
   ```bash
   git pull origin Segovia
   ```
2. Iniciar el servidor local:
   ```bash
   python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```
3. Si los snapshots JSON no están descargados, presionar el botón **"Sincronizar Padrón de Clientes"** en el módulo para descargarlos desde Rubpi API.
4. En Antigravity, puedes indicarle al asistente:
   *"Continuemos con el proyecto de Intranet Soporte. Lee el archivo `CONTEXTO_SESION_SOPORTE.md` para retomar la lógica actual."*
