#!/bin/bash
set -e

echo "=== 1. Updating Device Tree for PB0, PB1, PB7 LED Off ==="
cd /root/a33-build/linux
export ARCH=arm
export CROSS_COMPILE=arm-linux-gnueabihf-

cat << 'EOF' > arch/arm/boot/dts/allwinner/sun8i-a33-et-q8-v1.6.dts
// SPDX-License-Identifier: (GPL-2.0+ OR MIT)
/dts-v1/;
#include "sun8i-a33-q8-tablet.dts"

/ {
	model = "ET Q8 A33 v1.6 Tablet";
	compatible = "allwinner,sun8i-a33-et-q8-v1.6", "allwinner,q8-a33", "allwinner,sun8i-a33";

	leds {
		compatible = "gpio-leds";

		flash_pb0 {
			label = "q8:flash:pb0";
			gpios = <&pio 1 0 GPIO_ACTIVE_HIGH>; /* PB0 */
			default-state = "off";
		};

		flash_pb1 {
			label = "q8:flash:pb1";
			gpios = <&pio 1 1 GPIO_ACTIVE_HIGH>; /* PB1 */
			default-state = "off";
		};

		flash_pb7 {
			label = "q8:flash:pb7";
			gpios = <&pio 1 7 GPIO_ACTIVE_HIGH>; /* PB7 */
			default-state = "off";
		};
	};
};
EOF

make -j16 dtbs
cp arch/arm/boot/dts/allwinner/sun8i-a33-et-q8-v1.6.dtb "/mnt/c/Users/leona/Code/A33 Linux/output/sun8i-a33-et-q8-v1.6.dtb"

echo "=== 2. Rebuilding U-Boot without CONS_INDEX=5 and with all flash pins cleared ==="
cd /root/a33-build/u-boot
git checkout configs/q8_a33_tablet_1024x600_defconfig

# Replace CONFIG_CONS_INDEX=5 with CONS_INDEX=1 (standard PF2/PF4 so PB0/PB1 are not driven high)
sed -i 's/CONFIG_CONS_INDEX=5/CONFIG_CONS_INDEX=1/' configs/q8_a33_tablet_1024x600_defconfig

cat << 'EOF' >> configs/q8_a33_tablet_1024x600_defconfig
CONFIG_USE_PREBOOT=y
CONFIG_PREBOOT="gpio clear PB0; gpio clear PB1; gpio clear PB7"
CONFIG_BOOTCOMMAND="gpio clear PB0; gpio clear PB1; gpio clear PB7; bootz 0x42000000 0x43300000 0x43000000"
CONFIG_USE_BOOTARGS=y
CONFIG_BOOTARGS="console=tty0 console=ttyS0,115200 earlyprintk rootwait panic=10"
EOF

make q8_a33_tablet_1024x600_defconfig
make -j16
cp u-boot-sunxi-with-spl.bin "/mnt/c/Users/leona/Code/A33 Linux/output/u-boot-sunxi-with-spl.bin"

echo "=== All output artifacts ready ==="
ls -lh "/mnt/c/Users/leona/Code/A33 Linux/output"
