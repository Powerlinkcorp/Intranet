@echo off
chcp 65001 >nul
title Flasheo Directo ONU VSOL V2801S-B
cd /d "%~dp0"

echo ===================================================================
echo     FLASHEO DIRECTO ONU VSOL V2801S-B (Firmware Customizado)
echo ===================================================================
echo.

:: 1. Verificar elevación para configurar la IP de red
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Solicitando permisos de Administrador para configurar la IP en Ethernet 3...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

echo [1/3] Configurando IP estatica 192.168.1.100 en Ethernet 3...
netsh interface ipv4 set address name="Ethernet 3" source=static address=192.168.1.100 mask=255.255.255.0

echo [2/3] Esperando enlace con la ONU en 192.168.1.1...
timeout /t 3 >nul

echo [3/3] Iniciando proceso de flasheo y validacion automatica...
python flasheo_directo_v2801.py

echo.
echo Presiona cualquier tecla para salir...
pause >nul
