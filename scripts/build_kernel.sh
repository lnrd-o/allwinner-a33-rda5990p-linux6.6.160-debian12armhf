#!/bin/bash
set -e
cd /root/a33-build/linux
export ARCH=arm
export CROSS_COMPILE=arm-linux-gnueabihf-

echo "=== Building Kernel zImage and DTBs with 16 threads ==="
make -j16 zImage dtbs modules_prepare

echo "=== Copying artifacts to output folder ==="
mkdir -p "/mnt/c/Users/leona/Code/A33 Linux/output"
cp arch/arm/boot/zImage "/mnt/c/Users/leona/Code/A33 Linux/output/zImage"
cp arch/arm/boot/dts/allwinner/sun8i-a33-et-q8-v1.6.dtb "/mnt/c/Users/leona/Code/A33 Linux/output/sun8i-a33-et-q8-v1.6.dtb"

echo "=== Build finished successfully! ==="
ls -lh "/mnt/c/Users/leona/Code/A33 Linux/output"
