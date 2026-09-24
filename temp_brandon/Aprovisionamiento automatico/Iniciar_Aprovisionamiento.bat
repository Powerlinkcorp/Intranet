@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Aprovisionamiento Automatico de ONUs - Powerlink Corp

echo =========================================================================
echo   POWERLINK CORP - APROVISIONAMIENTO AUTOMATICO DE ONUs VSOL
echo =========================================================================
echo.
echo   Iniciando Servidor Web y Abriendo la Interfaz de Soporte...
echo.

REM Buscar interprete de Python de forma robusta
set "PYCMD="
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYCMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYCMD=python"
    )
)

if not defined PYCMD (
    if exist "%LocalAppData%\Programs\Python\Launcher\py.exe" (
        set "PYCMD=%LocalAppData%\Programs\Python\Launcher\py.exe"
    ) else if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "PYCMD=%LocalAppData%\Programs\Python\Python312\python.exe"
    ) else if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PYCMD=%LocalAppData%\Programs\Python\Python311\python.exe"
    ) else if exist "%ProgramFiles%\Python312\python.exe" (
        set "PYCMD=%ProgramFiles%\Python312\python.exe"
    ) else if exist "%ProgramFiles%\Python311\python.exe" (
        set "PYCMD=%ProgramFiles%\Python311\python.exe"
    )
)

if not defined PYCMD (
    echo [ERROR] No se encontro Python en el equipo.
    echo Por favor instale Python 3.10+ para ejecutar esta aplicacion.
    echo.
    pause
    exit /b 1
)

echo Usando: %PYCMD%
echo.

REM Verificar dependencias criticas
%PYCMD% -c "import playwright, openpyxl" >nul 2>nul
if %errorlevel% equ 0 goto START_APP

echo =========================================================================
echo   [CONFIGURACION INICIAL] Instalando librerias necesarias...
echo =========================================================================
%PYCMD% -m pip install -r requirements.txt
echo.
echo   Instalando motor de navegador Playwright...
%PYCMD% -m playwright install chromium
echo.
echo   Instalacion completada con exito.
echo =========================================================================
echo.

:START_APP
echo Servidor iniciando en: http://localhost:8088/
echo (Presione Ctrl+C para detener el servidor)
echo.

%PYCMD% main.py

echo.
echo [AVISO] El servidor se ha detenido.
pause
endlocal
