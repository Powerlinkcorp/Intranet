@echo off
:: Comprobar permisos de administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Solicitando permisos de administrador...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs"
    exit /b
)

echo ========================================================
echo   CONFIGURANDO ETHERNET 3 PARA CONEXION DIRECTA A ONU
echo ========================================================
echo Asignando IP estatica: 192.168.1.100 / Mascara: 255.255.255.0
netsh interface ipv4 set address name="Ethernet 3" source=static address=192.168.1.100 mask=255.255.255.0

echo.
echo Estado actual del adaptador:
netsh interface ipv4 show addresses name="Ethernet 3"
echo ========================================================
echo Configuracion aplicada con exito.
timeout /t 3
