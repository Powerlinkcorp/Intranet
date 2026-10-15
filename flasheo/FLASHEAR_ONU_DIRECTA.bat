@echo off
chcp 65001 >nul
title Flasheo Directo ONU VSOL V2801 (Powerlink)
color 0E

echo ======================================================================
echo           ESTACIÓN DE FLASHEO - VSOL V2801 (Powerlink)
echo ======================================================================
echo  Este programa flasheará la ONU conectada por cable en 192.168.1.1
echo  con el firmware: V2801D-B_all_V6.1.4-260914_powerlink_GPON.bin
echo.
echo  Pasos automatizados:
echo   1. Detección y login administrativo.
echo   2. Carga del firmware customizado Powerlink.
echo   3. Reinicio y restablecimiento a valores de fábrica.
echo   4. Validación de usuario 'Powerlink' y clave 'Powerlink2026*'.
echo   5. Verificación de la VLAN 3 (1_TR069_INTERNET_R_VID_3).
echo   6. Registro local y sincronización con la Intranet.
echo ======================================================================
echo.

pause

python flasheo_directo_v2801.py

echo.
echo ======================================================================
echo Proceso finalizado. Presiona cualquier tecla para salir.
echo ======================================================================
pause >nul
