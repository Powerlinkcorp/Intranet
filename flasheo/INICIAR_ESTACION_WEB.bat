@echo off
setlocal
cd /d "%~dp0"
title ESTACION DE FLASHEO ONUS - Powerlink Pro 3.0

echo.
echo ========================================================================
echo   POWERLINK - ESTACION DE FLASHEO PROFESIONAL DE ONUS
echo ========================================================================
echo   Panel Web Centralizado con Trazabilidad de Lotes y API REST
echo ========================================================================
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
    echo [ERROR] No se encontro Python en el sistema.
    echo Instala Python 3.11 o 3.12 y asegurate de marcar Add to PATH.
    pause
    exit /b 1
)

REM 2. Comprobar dependencias criticas
%PYCMD% -c "import fastapi, uvicorn, playwright, sqlalchemy, openpyxl" >nul 2>nul
if %errorlevel% neq 0 (
    echo [AVISO] Verificando e instalando dependencias necesarias...
    if exist "%~dp0PREPARAR_NUEVA_PC.bat" (
        call "%~dp0PREPARAR_NUEVA_PC.bat"
    ) else (
        %PYCMD% -m pip install -r "%~dp0requirements.txt"
    )
)

echo [OK] Entorno verificado.
echo [OK] Iniciando Servidor Web FastAPI en http://localhost:8080/ ...
echo.
echo ------------------------------------------------------------------------
echo  Accede desde cualquier navegador a:
echo  - Dashboard Web Principal: http://localhost:8080/
echo  - Documentacion OpenAPI:   http://localhost:8080/docs
echo ------------------------------------------------------------------------
echo.

%PYCMD% web_station.py 8080

echo.
echo Servidor finalizado.
pause
endlocal
