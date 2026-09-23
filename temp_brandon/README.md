# Aprovisionamiento Automático de ONUs — Powerlink Corp

Sistema web integral y automatizado para aprovisionamiento rápido, diagnóstico y configuración de parámetros de red (WAN, VLAN y Wi-Fi) en routers y ONUs de clientes.

---

## 📂 Arquitectura Modular y Escalable

```
Aprovisionamiento automatico/
├── core/
│   ├── models/                # Adaptadores de hardware por marca/modelo
│   │   ├── base_onu.py        # Clase base abstracta (BaseONU) para multi-marca
│   │   └── vsol_adapter.py    # Adaptador especializado para VSOL (V2804, HG3232, etc.)
│   ├── services/              # Lógica de negocio y orquestación
│   │   ├── provision_service.py   # Orquestador de trabajos (Jobs) y progreso
│   │   ├── credentials_service.py # Gestión y seguridad de credenciales
│   │   └── history_service.py     # Registro en Excel (.xlsx) y CSV
│   └── utils/
│       └── network_utils.py   # Sondas HTTP y utilidades de red
├── config/
│   ├── settings.json          # Configuración del servidor y presets de VLAN
│   └── credentials.json       # Diccionario protegido de credenciales maestras
├── web/
│   ├── server.py              # Servidor HTTP nativo multi-hilo
│   ├── routes/                # Controladores de endpoints REST
│   │   ├── api_provision.py   # Sondeo y Aprovisionamiento
│   │   ├── api_history.py     # Historial y exportación Excel
│   │   └── api_config.py      # Configuración del sistema
│   └── static/
│       ├── css/styles.css     # Estilos de la interfaz de usuario
│       ├── js/app.js          # Lógica interactiva, polling y stepper
│       └── index.html         # Interfaz ordenada según el flujo real
├── logs/
│   ├── registro_aprovisionamiento.xlsx  # Historial en Excel con formato
│   └── registro_aprovisionamiento.csv   # Historial plano
├── tests/
│   └── test_e2e.py            # Suite de pruebas de integración extremo a extremo
├── Iniciar_Aprovisionamiento.bat  # Lanzador para Windows (1-Clic)
├── main.py                    # Punto de entrada de Python
└── README.md
```

---

## 🚀 Flujo de Operación

1. **Paso 0: Conexión**: Se ingresa la IP y se consulta el estado de la ONU (Modelo, MAC, PON, Potencia Óptica $Rx\text{ dBm}$).
2. **Paso 1 (PRIMERO): Wi-Fi 2.4 GHz & 5 GHz**: Se definen los SSIDs y contraseñas seguras y se envían a la ONU.
3. **Paso 2 (SEGUNDO): Red WAN & VLAN**: Se crea el enlace `Nuevo` en modo `Route` con protocolo `IPv4 / DHCP`, se activa `NAT` y `VLAN Tagged` con el ID seleccionado.
4. **Paso 3: Verificación & Registro**: Se valida la persistencia y se registra la operación en el archivo Excel `logs/registro_aprovisionamiento.xlsx`.

---

## 💻 Inicio Rápido

Haz doble clic en **`Iniciar_Aprovisionamiento.bat`** o ejecuta:
```bash
python main.py
```
Accede a la interfaz en: `http://localhost:8088/`
