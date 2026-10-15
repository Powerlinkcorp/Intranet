@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title INSTALADOR Y CONFIGURACION - Estacion de Flasheo ONUs
cls

echo ============================================================================
echo   ESTACION DE FLASHEO ONUs VSOL - PREPARACION DE NUEVA LAPTOP / PC
echo ============================================================================
echo.
echo  Este asistente configurara automaticamente las librerias y el navegador
echo  necesario (Playwright Chromium) para que la estacion funcione en este equipo.
echo.

REM 1. Buscar interprete de Python
set "PYCMD="
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYCMD=py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        py -3 --version >nul 2>nul && set "PYCMD=py -3" || set "PYCMD=python"
    )
)

if not defined PYCMD (
    if exist "%LocalAppData%\Programs\Python\Launcher\py.exe" (
        set "PYCMD="%LocalAppData%\Programs\Python\Launcher\py.exe""
    ) else if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "PYCMD="%LocalAppData%\Programs\Python\Python312\python.exe""
    ) else if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PYCMD="%LocalAppData%\Programs\Python\Python311\python.exe""
    ) else if exist "%ProgramFiles%\Python312\python.exe" (
        set "PYCMD="%ProgramFiles%\Python312\python.exe""
    ) else if exist "%ProgramFiles%\Python311\python.exe" (
        set "PYCMD="%ProgramFiles%\Python311\python.exe""
    )
)

if not defined PYCMD (
    echo [ERROR] No se encontro Python en esta laptop.
    echo.
    echo Por favor:
    echo  1. Descarga e instala Python 3.11 o 3.12 desde:
    echo     https://www.python.org/downloads/
    echo  2. MUY IMPORTANTE: Durante la instalacion, marca la casilla:
    echo     "[X] Add python.exe to PATH"
    echo  3. Una vez instalado Python, vuelve a hacer doble clic a este archivo.
    echo.
    pause
    exit /b 1
)

echo [1/3] Python detectado: %PYCMD%
%PYCMD% --version
echo.

echo [2/3] Instalando dependencias requeridas (playwright, librouteros, openpyxl)...
%PYCMD% -m pip install --upgrade pip --quiet
%PYCMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [ADVERTENCIA] Hubo un error con pip. Reintentando instalacion basica...
    %PYCMD% -m pip install playwright librouteros openpyxl fastapi "uvicorn[standard]" sqlalchemy pydantic python-multipart websockets
)
echo      -^> Librerias instaladas con exito.
echo.

echo [3/3] Instalando motor de navegador Chromium para automatizacion (Playwright)...
%PYCMD% -m playwright install chromium
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo descargar Chromium automaticamente.
    echo Asegurate de tener conexion a Internet durante esta primera instalacion.
    pause
    exit /b 1
)
echo      -^> Motor Chromium instalado correctamente.
echo.

echo ============================================================================
echo   VERIFICACION FINAL DEL SISTEMA
echo ============================================================================
%PYCMD% -c "import playwright, librouteros, openpyxl, fastapi, uvicorn, sqlalchemy; print('  [OK] Todas las librerias Python funcionan perfectamente.')"
if %errorlevel% neq 0 (
    echo [ERROR] Algo fallo en la verificacion de librerias.
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo   TODO LISTO Y CONFIGURADO CON EXITO
echo ============================================================================
echo.
echo  Ya puedes iniciar la estacion de flasheo ejecutando:
echo    * "web_panel.bat"  para abrir el Panel de Control Web (Recomendado)
echo    * "flasheo.bat"    para la consola interactiva por terminal
echo.
echo  RECORDATORIO DE RED:
echo  Recuerda conectar el cable Ethernet de esta laptop y asignarle la IP:
echo    - Para ONU Directa: IP 192.168.1.50 (Mascara 255.255.255.0)
echo    - Para Switch 20P:  IP 10.100.0.100 (Mascara 255.255.0.0)
echo.
pause
endlocal
