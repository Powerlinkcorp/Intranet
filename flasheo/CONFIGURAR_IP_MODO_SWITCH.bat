@echo off
setlocal
title CONFIGURAR IP MODO SWITCH - 10.100.0.100 / 255.255.0.0

echo ========================================================================
echo   CONFIGURANDO ETHERNET PARA MODO SWITCH 20 PUERTOS (10.100.0.100)
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
echo.
echo Aplicando IP 10.100.0.100, Mascara 255.255.0.0 y Gateway 10.100.0.1...
netsh interface ipv4 set address name="%ADAPTER%" source=static address=10.100.0.100 mask=255.255.0.0 gateway=10.100.0.1 gwmetric=25

echo Agregando ruta especifica para 10.100.0.0/16...
route add 10.100.0.0 mask 255.255.0.0 10.100.0.1 metric 5 >nul 2>&1

echo.
echo ========================================================================
echo Estado de la tarjeta "%ADAPTER%":
netsh interface ipv4 show addresses name="%ADAPTER%"
echo ========================================================================
echo [OK] Configuracion aplicada con exito.
echo Todos los puertos 10.100.1.1 hasta 10.100.20.1 ahora son alcanzables.
echo.
pause
endlocal
