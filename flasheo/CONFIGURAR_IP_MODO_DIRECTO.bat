@echo off
setlocal
title CONFIGURAR IP MODO DIRECTO - 192.168.1.100

echo ========================================================================
echo   CONFIGURANDO ETHERNET 3 PARA MODO DIRECTO (192.168.1.100)
echo ========================================================================
echo.

REM Comprobar permisos de administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Este comando requiere permisos de Administrador.
    echo Solicitando elevacion...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

REM Detectar adaptador Ethernet activo o conectado
set "ADAPTER=Ethernet 3"
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "(Get-NetAdapter | Where-Object Status -eq 'Up' | Where-Object Name -like '*Ethernet*' | Select-Object -ExpandProperty Name -First 1)"`) do (
    if not "%%A"=="" set "ADAPTER=%%A"
)

echo Adaptador detectado: "%ADAPTER%"
echo Aplicando IP estatica 192.168.1.100 y mascara 255.255.255.0 en "%ADAPTER%"...
netsh interface ipv4 set address name="%ADAPTER%" source=static address=192.168.1.100 mask=255.255.255.0

echo.
echo ========================================================================
echo Estado de la tarjeta "%ADAPTER%":
netsh interface ipv4 show addresses name="%ADAPTER%"
echo ========================================================================
echo [OK] Configuracion aplicada con exito.
echo Ya puedes volver al navegador y pulsar 'Iniciar Flasheo'.
echo.
pause
endlocal
