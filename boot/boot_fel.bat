@echo off
echo ===================================================
echo   Allwinner A33 Tablet FEL Bootloader
echo ===================================================
echo Waiting for Allwinner USB FEL device...
:wait_loop
output\sunxi-fel.exe version >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

echo FEL device detected!
echo Loading U-Boot, Kernel, DTB, and Initrd into RAM...
output\sunxi-fel.exe uboot output\u-boot-sunxi-with-spl.bin write 0x41000000 output\zImage write 0x43000000 output\sun8i-a33-et-q8-v1.6.dtb write 0x43100000 output\boot.scr write 0x44000000 output\uInitrd
if errorlevel 1 (
    echo Boot failed!
    pause
    exit /b 1
)

echo Booting complete! Waiting for CDC ACM serial on COM22...
pause
