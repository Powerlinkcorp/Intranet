@echo off
chcp 65001 > nul
title POWER LINK CORP. - Intranet Server
echo.
echo ============================================
echo   POWER LINK CORP. - Servidor de Intranet Corporativa
echo ============================================
echo.
echo [*] Iniciando servidor FastAPI en http://127.0.0.1:8000
echo [*] Presiona CTRL+C para detener el servidor
echo.

cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo [*] Entorno virtual no encontrado. Creando entorno virtual 'venv'...
    python -m venv venv
    if errorlevel 1 (
        echo [!] Error creando entorno virtual. Verifica que Python este instalado y en el PATH.
        pause
        exit /b 1
    )
    echo [*] Instalando dependencias de requirements.txt...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo [*] Verificando base de datos...
python init_db.py

echo.
echo [*] Iniciando servidor...
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
