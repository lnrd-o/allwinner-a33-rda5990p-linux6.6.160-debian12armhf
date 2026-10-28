@echo off
:: ==============================================================================
:: Allwinner A33 Tablet (ET_F900_V1.6 / Q8) Host SD Card Preparation Launcher
:: Automatically requests Administrator privileges and runs prepare_sd_card.py
:: ==============================================================================

setlocal EnableDelayedExpansion
title Allwinner A33 Tablet MicroSD Installer

:: Check for Administrator privileges
net session >nul 2>&1
if not %errorLevel% == 0 (
    echo =========================================================
    echo Requesting Administrator privileges to access physical disks...
    echo =========================================================
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

echo =================================================================
echo   Allwinner A33 Tablet Standalone MicroSD Installer
echo   Board: ET_F900_V1.6 (MID-756 / Q8 layout, 1024x600 LCD)
echo =================================================================
echo.

python prepare_sd_card.py

echo.
echo Press any key to exit...
pause >nul
