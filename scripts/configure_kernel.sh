#!/bin/bash
set -e
cd /root/a33-build/linux
export ARCH=arm
export CROSS_COMPILE=arm-linux-gnueabihf-

make sunxi_defconfig

./scripts/config --enable CONFIG_SUNXI_RSB
./scripts/config --enable CONFIG_MFD_AXP20X
./scripts/config --enable CONFIG_MFD_AXP20X_RSB
./scripts/config --enable CONFIG_REGULATOR_AXP20X
./scripts/config --enable CONFIG_AXP20X_POWER
./scripts/config --enable CONFIG_AXP20X_ADC
./scripts/config --enable CONFIG_INPUT_AXP20X_PEK
./scripts/config --enable CONFIG_MMC
./scripts/config --enable CONFIG_MMC_SUNXI
./scripts/config --enable CONFIG_NET_CORE
./scripts/config --enable CONFIG_WIRELESS
./scripts/config --enable CONFIG_CFG80211
./scripts/config --enable CONFIG_CFG80211_WEXT
./scripts/config --enable CONFIG_MAC80211
./scripts/config --enable CONFIG_WEXT_CORE
./scripts/config --enable CONFIG_WEXT_PROC
./scripts/config --enable CONFIG_WEXT_PRIV
./scripts/config --enable CONFIG_USB_NET_DRIVERS
./scripts/config --enable CONFIG_USB_RTL8152
./scripts/config --enable CONFIG_USB_NET_AX88179_178A
./scripts/config --enable CONFIG_USB_NET_SMSC95XX
./scripts/config --enable CONFIG_USB_ETH
./scripts/config --enable CONFIG_R8188EU
./scripts/config --enable CONFIG_RTL8XXXU
./scripts/config --disable CONFIG_DRM
./scripts/config --disable CONFIG_DRM_SUN4I
./scripts/config --disable CONFIG_FB
./scripts/config --disable CONFIG_SOUND
./scripts/config --disable CONFIG_SND
./scripts/config --disable CONFIG_MEDIA_SUPPORT
./scripts/config --disable CONFIG_MEDIA_CAMERA_SUPPORT
./scripts/config --disable CONFIG_STAGING
./scripts/config --enable CONFIG_SERIAL_8250
./scripts/config --enable CONFIG_SERIAL_8250_CONSOLE
./scripts/config --enable CONFIG_SERIAL_8250_SUNXI
./scripts/config --enable CONFIG_SERIAL_OF_PLATFORM
./scripts/config --set-val CONFIG_CMDLINE '"console=ttyS0,115200 earlyprintk rootwait"'

make olddefconfig
echo "=== Kernel configured successfully ==="
