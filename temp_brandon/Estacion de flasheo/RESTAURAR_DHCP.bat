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

echo Configurando Ethernet 3 en DHCP automatico...
netsh interface ipv4 set address name="Ethernet 3" source=dhcp
netsh interface ipv4 set dnsservers name="Ethernet 3" source=dhcp

echo.
echo ========================================================================
echo [OK] Ethernet 3 restaurada a DHCP automatico.
echo ========================================================================
echo.
pause
endlocal
