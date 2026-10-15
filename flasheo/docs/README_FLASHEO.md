# ESTACIÓN DE FLASHEO MULTI-MODELO DE ONUs (Powerlink)

Lanzadores principales en el directorio raíz (1 solo clic):
- **`web_panel.bat`**: **Panel de Control Web y Dashboard en Vivo** (`http://localhost:8080/`).
- **`flasheo.bat`**: **Menú de Consola Interactivo Automatizado**.

---

## 📁 Estructura Modular de Carpetas

El proyecto está organizado de manera modular y desacoplada para facilitar su escalamiento (agregar nuevos fabricantes, módulos OLT, TR-069, etc.):

```text
Estacion de flasheo/
├── flasheo.bat                    <-- Lanzador principal por consola (1-clic)
├── web_panel.bat                  <-- Lanzador de la interfaz web (1-clic)
├── main.py                        <-- Punto de entrada general de Python
│
├── config/                        <-- Configuraciones y perfiles
│   ├── onu_profiles.json          (Perfiles, credenciales y firmwares de ONUs)
│   ├── mikrotik_config.json       (Configuración RouterOS Switch MikroTik)
│   └── onus_list.csv              (Lista de mapeo de puertos predefinidos)
│
├── firmwares/                     <-- Almacén central de binarios de firmware (.bin)
│   ├── V2801D-B_all_V6.1.4-260805_powerlink_GPON.bin (6.2 MB)
│   └── HG3232AXT-H_all_V1.1.00-20260610_LupoverPowerlinkver.bin (30.2 MB)
│
├── core/                          <-- Motores de automatización y lógica central
│   ├── profiles.py                (Gestor de perfiles y resolución de firmwares)
│   ├── vsol_autopilot.py          (Motor Playwright / Automatización de flasheo)
│   ├── mikrotik.py                (Módulo RouterOS API / Switch / Puertos)
│   └── network_diag.py            (Diagnóstico de red y auto-configuración de IP)
│
├── web/                           <-- Módulo del servidor web y panel dashboard
│   ├── web_station.py             (Servidor HTTP nativo, API REST y Dashboard SPA)
│   └── onu_web_proxy.py           (Proxy reverso HTTP para ONUs)
│
├── cli/                           <-- Interfaces de terminal y TUI
│   ├── flasheo.py                 (Lanzador interactivo de consola)
│   ├── fleet_monitor.py           (Monitor rápido de estado)
│   └── tui_flasheo.py             (Dashboard TUI en consola)
│
├── logs/                          <-- Registros, estados e historiales
│   ├── continuo.log               (Log de salida en tiempo real)
│   ├── estado.json                (Estado en vivo de los puertos)
│   ├── registro_flasheo.csv       (Historial CSV de flasheos)
│   └── registro_flasheo.xlsx      (Historial Excel con formato)
│
├── capturas/                      <-- Capturas automáticas de verificación
│   └── *.png
│
├── docs/                          <-- Documentación y manuales
│   └── README_FLASHEO.md
│
└── requirements.txt               <-- Dependencias de Python
```

---

## 📦 Modelos de ONU Soportados y Firmwares

| Modelo | Nombre Comercial | Hardware | Firmware Asignado | Ubicación | Credenciales Iniciales |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`V2801S-B`** | VSOL V2801S-B / V2801D-B | 1GE G/EPON (Bridge/Router) | `V2801D-B_all_V6.1.4-260805_powerlink_GPON.bin` | `firmwares/` | `admin` / `Redes2010` o `stdONU101` |
| **`V2804AX30-H`** | VSOL V2804AX30-H / HG3232AXT-H | Wi-Fi 6 AX3000 (4GE+1POTS) | `HG3232AXT-H_all_V1.1.00-20260610_LupoverPowerlinkver.bin` | `firmwares/` | `admin` / `stdONU101` (Wizard) |

---

## 🚀 Cómo Agregar un Nuevo Modelo de ONU

1. Coloca el archivo `.bin` de firmware en la carpeta **`firmwares/`**.
2. Abre el archivo **`config/onu_profiles.json`** y añade la nueva sección de modelo:
```json
"NUEVO_MODELO": {
  "id": "NUEVO_MODELO",
  "name": "Nombre Comercial del Fabricante",
  "hardware_type": "G/EPON o Wi-Fi",
  "icon": "⚡",
  "firmware": "archivo_firmware.bin",
  "default_user": "admin",
  "default_pass": "password_de_fabrica",
  "candidate_credentials": [
    ["admin", "password_de_fabrica"],
    ["admin", "admin123"],
    ["Powerlink", "Powerlink2026*"]
  ],
  "final_user": "Powerlink",
  "final_pass": "Powerlink2026*",
  "has_wizard": false,
  "target_vlan_id": "3"
}
```
3. ¡Listo! El modelo aparecerá automáticamente en el Selector Visual de la Web y en la Consola CLI.