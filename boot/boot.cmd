# Allwinner A33 Tablet (ET_F900_V1.6 / Q8) Autonomous SD Boot Script
# Generated for Debian 12 (Bookworm) armhf & Linux 6.6.160 LTS

setenv fdt_high ffffffff
setenv initrd_high ffffffff

# Set kernel console and root partition arguments
# console=tty1: Direct LCD console (1024x600 simplefb VT)
# console=ttyS0,115200: UART debug console
# console=ttyGS0,115200: USB CDC-ACM gadget serial console (COM22)
setenv bootargs console=ttyS0,115200 console=tty1 console=ttyGS0,115200 root=/dev/mmcblk0p2 rootwait rw panic=10

echo "=== Booting Debian 12 from MicroSD Card (mmc0) ==="

# Set fallback addresses if not defined
if test -z "${kernel_addr_r}"; then setenv kernel_addr_r 0x42000000; fi
if test -z "${fdt_addr_r}"; then setenv fdt_addr_r 0x43000000; fi
if test -z "${ramdisk_addr_r}"; then setenv ramdisk_addr_r 0x43400000; fi
if test -z "${devtype}"; then setenv devtype mmc; fi
if test -z "${devnum}"; then setenv devnum 0; fi

echo "Loading kernel zImage..."
load ${devtype} ${devnum}:1 ${kernel_addr_r} zImage || load ${devtype} ${devnum}:1 ${kernel_addr_r} /boot/zImage

echo "Loading device tree (sun8i-a33-et-q8-v1.6.dtb)..."
load ${devtype} ${devnum}:1 ${fdt_addr_r} sun8i-a33-et-q8-v1.6.dtb || load ${devtype} ${devnum}:1 ${fdt_addr_r} /boot/sun8i-a33-et-q8-v1.6.dtb

# Check for optional uInitrd; boot directly if not present
if test -e ${devtype} ${devnum}:1 uInitrd; then
    echo "Optional uInitrd detected, loading..."
    load ${devtype} ${devnum}:1 ${ramdisk_addr_r} uInitrd
    bootz ${kernel_addr_r} ${ramdisk_addr_r} ${fdt_addr_r}
else
    echo "Booting kernel directly to root=/dev/mmcblk0p2..."
    bootz ${kernel_addr_r} - ${fdt_addr_r}
fi
