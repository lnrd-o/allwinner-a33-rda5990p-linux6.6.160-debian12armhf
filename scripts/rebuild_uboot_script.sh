#!/bin/bash
set -e

cd /root/a33-build/u-boot
export ARCH=arm
export CROSS_COMPILE=arm-linux-gnueabihf-

git checkout configs/q8_a33_tablet_1024x600_defconfig
git checkout arch/arm/dts/sun8i-a33-q8-tablet.dts

# Add broken-cd to U-Boot DT for mmc0
cat << 'EOF' >> arch/arm/dts/sun8i-a33-q8-tablet.dts

&mmc0 {
	vmmc-supply = <&reg_dcdc1>;
	bus-width = <4>;
	broken-cd;
	status = "okay";
};
EOF

# Replace CONFIG_CONS_INDEX=5 with CONS_INDEX=1 so PB0 is not driven high by UART
sed -i 's/CONFIG_CONS_INDEX=5/CONFIG_CONS_INDEX=1/' configs/q8_a33_tablet_1024x600_defconfig

cat << 'EOF' >> configs/q8_a33_tablet_1024x600_defconfig
CONFIG_MMC_BROKEN_CD=y
# CONFIG_CMD_PXE is not set
# CONFIG_CMD_DHCP is not set
# CONFIG_CMD_NET is not set
# CONFIG_NET is not set
CONFIG_USE_PREBOOT=y
CONFIG_PREBOOT="gpio clear PB0; gpio clear PB1; gpio clear PB7"
CONFIG_USE_BOOTCOMMAND=y
CONFIG_BOOTCOMMAND="source 0x43100000 || bootz 0x41000000 0x44000000 0x43000000 || if mmc rescan; then echo MMC detected; fi; if load mmc 0:1 0x43100000 boot.scr; then echo Running boot.scr...; source 0x43100000; fi; if load mmc 0:1 0x41000000 zImage && load mmc 0:1 0x43000000 sun8i-a33-et-q8-v1.6.dtb; then echo Booting zImage directly...; setenv bootargs console=tty1 console=ttyS0,115200 console=ttyGS0,115200 root=/dev/mmcblk0p2 rootwait rw panic=10; bootz 0x41000000 - 0x43000000; fi; run distro_bootcmd"
CONFIG_USE_BOOTARGS=y
CONFIG_BOOTARGS="console=tty1 console=ttyS0,115200 console=ttyGS0,115200 root=/dev/mmcblk0p2 rootwait rw panic=10"
EOF

make q8_a33_tablet_1024x600_defconfig
make -j16

cp u-boot-sunxi-with-spl.bin "/mnt/c/Users/leona/Code/A33 Linux/output/u-boot-sunxi-with-spl.bin"
cp u-boot-sunxi-with-spl.bin "/mnt/c/Users/leona/Code/A33 Linux/sd_install/u-boot-sunxi-with-spl.bin"
cp u-boot-sunxi-with-spl.bin "/root/a33-build/debian-rootfs/root/sd_install/u-boot-sunxi-with-spl.bin" 2>/dev/null || true

echo "=== U-Boot updated successfully with MMC_BROKEN_CD and robust bootcmd ==="
ls -lh "/mnt/c/Users/leona/Code/A33 Linux/output/u-boot-sunxi-with-spl.bin"
