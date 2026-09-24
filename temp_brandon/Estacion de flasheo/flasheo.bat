@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title FLASHEO ONUs VSOL - Powerlink
echo.
echo  ============================================================
echo   FLASHEO DE ONUs VSOL V2804AX30-H (Powerlink)
echo  ============================================================
echo.

REM Buscar interprete de Python: py (launcher) o python
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
    echo  ERROR No se encontro Python.
    echo.
    echo  En una PC Windows 11 nueva instala Python 3.11+ desde:
    echo    https://www.python.org/downloads/windows/
    echo  IMPORTANTE: marca la casilla "Add python.exe to PATH" al instalar.
    echo  Luego vuelve a ejecutar este .bat.
    echo.
    pause
    exit /b 1
)

REM Verificar si las librerias y dependencias estan listas
%PYCMD% -c "import playwright, librouteros, openpyxl" >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo  [AVISO] Es la primera vez que se ejecuta en esta laptop o faltan librerias.
    echo  Iniciando configuracion automatica...
    echo.
    call "%~dp0PREPARAR_NUEVA_PC.bat"
)

echo  Usando: %PYCMD%
%PYCMD% flasheo.py
echo.
echo  Proceso terminado.
pause
endlocal