@echo off
echo ===================================================
echo  A33 tablet: FEL-boot new kernel, rootfs on the SD card
echo  (insert the v2 SD card first; put tablet in FEL mode)
echo ===================================================
:wait_loop
output\sunxi-fel.exe version >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)
output\sunxi-fel.exe uboot output\u-boot-sunxi-with-spl.bin write 0x41000000 output\zImage_usbnet write 0x43000000 output\sun8i-a33-et-q8-v1.6.dtb write 0x43100000 output\boot_fel_sd.scr
if errorlevel 1 ( echo Boot failed! & pause & exit /b 1 )
echo Booting. The LCD dashboard should appear in about 30 seconds.
pause
