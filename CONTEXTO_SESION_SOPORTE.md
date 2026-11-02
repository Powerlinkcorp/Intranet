# Contexto de Sesión — Módulo de Documentación de Casos y Estadísticas de Soporte Remoto

**Rama:** `Segovia`  
**Usuario:** Daniel Segovia  
**Fecha de corte:** 22 de Octubre de 2026  
**Servidor local:** `http://127.0.0.1:8000/soporte/casos`

---

## 1. Resumen de Funcionalidades y Mejoras Implementadas

### A. Unificación y Normalización Geográfica de Macro-Zonas
- **Cumbre Roja y HUB `CUM` unificados en `LOS TEQUES`:**
  - Toda incidencia perteneciente a *Cumbre Roja*, *Caña Larga*, *El Trabuco*, *Los Amarillos*, *El Puinky* o atendida bajo el **HUB `CUM`** ahora clasifica y se lee directamente bajo la macro-zona **`LOS TEQUES`**.
  - Se actualizaron los 1.368 casos históricos de la base de datos a `LOS TEQUES`.
- **San Pedro de los Altos y Los Helechos en `LOS TEQUES`:**
  - Sub-sectores como *"San Pedro de los Altos, Sector Finca Minerva Los Helechos"* o *"Guaremal ... Los Helechos"* se clasifican estrictamente en **`LOS TEQUES`**.
  - La *Urb. Los Helechos* de Los Salias (HUB `RET` / `PAR`) permanece correctamente asignada a **`SAN ANTONIO`**.
- **Resolución de Colisiones por Subcadena:**
  - **`ARAGUANEY` vs. `ARAGUA`:** Edificios como *Edif. Araguaney* en Los Teques (Centro / El Encanto / Cabotaje) ya no se desvían a `TEJERIAS`; clasifican en **`LOS TEQUES`**.
  - **`CARRIZALITO` vs. `CARRIZAL`:** El sector *Carrizalito* (Carretera Vieja Caracas-Los Teques) clasifica en **`LOS TEQUES`**. A su vez, los contratos de *San Diego de los Altos* que en Rubpi tenían `city="Carrizal"` se asignan limpiamente a **`SAN DIEGO`**.
  - **`CARACAS` / `LIBERTADOR` / `LOS EUCALIPTOS` en Los Teques:** Sectores como *Carretera Vieja Caracas-Los Teques*, *Residencias Caracas (Los Teques)*, *Macarena Calle Libertador* y *El Nacional / Palo Alto Sector Los Eucaliptos* clasifican en **`LOS TEQUES`** en lugar de desviarse a `EL VALLE`.
  - **`VISTA HERMOSA` / `SAN JOSÉ`:** Casos de *El Vigía / Mal Paso / Lagunetica Urb. Vista Hermosa* y *Liceo San José (El Llano, Los Teques)* clasifican en **`LOS TEQUES`**.

### B. Enriquecimiento Automático de Direcciones Genéricas
- Para clientes cuyo campo `address` en Rubpi era genérico o incompleto (ej. `"Calle principal, Casa s/n"` o `"Sn"`), la función `_build_ubicacion_con_subsector` antepone automáticamente la urbanización y el sub-sector registrados en la base de datos (ej. `"La Vega, Sector LAS TORRES — Calle principal, Sn"`, `"Las Tejerias, Sector Casco Central — Calle principal, casa s/n"`).

### C. Catálogo Oficial de Sub-Sectores Autogenerado
- El archivo `static/uploads/catalogo_subsectores.json` se genera de forma 100% automática a partir de los snapshots de clientes si no existe en disco, poblando 262 sub-sectores reales mapeados a su macro-zona para el buscador de **Afectación Masiva**.

### D. Sincronización en Vivo con Google Sheets (F5 y Webhook)
- **Descarga incremental al pulsar F5:** Se consulta el CSV en vivo del Google Sheets oficial (`gid=246682208`) con un cooldown seguro de 5s, sincronizando tickets nuevos o editados en tiempo real (empatando 49.221 filas 1:1 con la hoja).
- **Envío hacia Google Sheets:** Tanto `crear_caso_soporte` como `crear_casos_afectacion_masivos` sincronizan primero para evitar colisiones en el consecutivo `N° Caso` y despachan los nuevos tickets al Webhook oficial de Apps Script.
- **Hora oculta en frontend:** Se ocultó el campo de hora en la tabla para coincidir con el formato de la hoja de cálculo.
- **Zona Horaria GMT-4:** Todo cálculo de fechas (`fecha_display`, `fecha_iso`, métricas y filtros) está garantizado bajo `America/Caracas` (GMT-4).

### E. Monitor de Reincidencias y Alarmas (Sección 6)
- **Filtros:** Semanal (últimos 7 días), Mensual (por selector dinámico de meses) y Todo el Historial.
- **Semáforo:** 🔴 Crítica ($\ge 3$ rep. en 7d o $\ge 5$ en el mes), 🟠 Alta ($2$ rep. en 7d o $3\text{--}4$ en el mes), 🟡 Observación.
- **Búsqueda Exacta:** Al buscar por cédula numérica, se exige coincidencia exacta de dígitos para no mezclar clientes con cédulas similares.
- **Ficha del Cliente:** Muestra exclusivamente los casos, motivos y resoluciones del rango de alarma seleccionado. El botón *"Ver Frecuencia Semanal/Mensual"* abre directamente la ficha sin colisiones de peticiones asíncronas.

---

## 2. Instrucciones para Reanudar en la PC del Trabajo

1. **Abrir la terminal en la carpeta del proyecto y verificar la rama:**
   ```bash
   git checkout Segovia
   git pull origin Segovia
   ```
2. **Activar el entorno virtual e iniciar el servidor:**
   ```bash
   .\venv\Scripts\activate
   python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```
3. **Descarga inicial de padrón (si es una instalación limpia o clon nuevo):**
   - Si no existen los archivos en `static/uploads/last_snapshot.json`, el sistema los descarga automáticamente de la API de Rubpi en la primera petición o al pulsar el botón *"Sincronizar Padrón de Clientes"*.
4. **Instrucción para el asistente en la PC de trabajo:**
   *"Continuemos con el proyecto de Intranet Soporte. Lee el archivo `CONTEXTO_SESION_SOPORTE.md` para retomar el estado actual en la rama Segovia."*
