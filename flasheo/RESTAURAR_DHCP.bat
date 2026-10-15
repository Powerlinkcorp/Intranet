@echo off
setlocal
title RESTAURAR DHCP EN ETHERNET 3

echo ========================================================================
echo   RESTAURANDO DHCP AUTOMATICO EN ETHERNET 3
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
echo Configurando "%ADAPTER%" en DHCP automatico...
netsh interface ipv4 set address name="%ADAPTER%" source=dhcp
netsh interface ipv4 set dnsservers name="%ADAPTER%" source=dhcp

echo.
echo ========================================================================
echo [OK] "%ADAPTER%" restaurada a DHCP automatico.
echo ========================================================================
echo.
pause
endlocal
