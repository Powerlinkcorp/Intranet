# REGLAS Y FLUJO DE TRABAJO - DIXON IGLESIAS

## 1. Entorno Principal de Trabajo: Módulo de Operaciones v2
- **Ruta de Trabajo Exclusiva:** `C:\Users\diglesias\Desktop\pc dixon\intranet\modulo_de_operaciones_migrado\v2`
- **Principio Fundamental:** Todo cambio, diseño, corrección de reporte, mejora o nueva funcionalidad se construye, prueba y valida **PRIMERO Y EXCLUSIVAMENTE en `v2`**.
- El asistente no debe realizar modificaciones directas en la Intranet ni compilar a producción hasta que Dixon haya validado el resultado en `v2`.

## 2. Aprobación Previa Obligatoria para Integración
- Ningún código se traspasa a `C:\Users\diglesias\.gemini\antigravity\scratch\Intranet` ni se compila con `npm run build` sin la **autorización previa y explícita de Dixon**.
- Solo cuando a Dixon le convenza y le guste el funcionamiento en `v2`, se procederá a sincronizarlo con la Intranet.

## 3. Política Estricta de Git (Rama Dixon)
- Cuando Dixon autorice integrar y subir cambios:
  - Se trabaja, comitea y sube **ÚNICA Y EXCLUSIVAMENTE en la rama `dixon`** (`git push origin dixon`).
  - **PROHIBICIÓN ABSOLUTA:** Jamás hacer merge, checkout o push hacia `qa`, `pruebas` o `main`. El pase a `qa` o producción es una decisión exclusiva del equipo de trabajo de la empresa.
