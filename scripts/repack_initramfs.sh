#!/bin/bash
set -e

ROOTFS="/root/a33-build/debian-rootfs"
OUTPUT="/mnt/c/Users/leona/Code/A33 Linux/output"

echo "=== 1. Creating robust /init wrapper in Debian rootfs ==="
rm -f "$ROOTFS/init"
cat << 'EOF' > "$ROOTFS/init"
#!/bin/sh
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Mount essential pseudo-filesystems
mount -t proc proc /proc 2>/dev/null
mount -t sysfs sysfs /sys 2>/dev/null
mount -t devtmpfs devtmpfs /dev 2>/dev/null
mkdir -p /dev/pts /run /tmp
mount -t devpts devpts /dev/pts 2>/dev/null
mount -t tmpfs tmpfs /run 2>/dev/null
mount -t tmpfs tmpfs /tmp 2>/dev/null

# Force turn off any camera flash / torch pins (PB0=32, PB1=33, PB7=39)
for pin in 32 33 39; do
    echo $pin > /sys/class/gpio/export 2>/dev/null || true
    echo out > /sys/class/gpio/gpio${pin}/direction 2>/dev/null || true
    echo 0 > /sys/class/gpio/gpio${pin}/value 2>/dev/null || true
done

echo "============================================="
echo "   Welcome to Debian 12 (Bookworm) armhf!   "
echo "   Allwinner A33 Headless Linux Server      "
echo "============================================="

# Hand over to systemd / init
if [ -x /lib/systemd/systemd ]; then
    exec /lib/systemd/systemd --system
elif [ -x /sbin/init ]; then
    exec /sbin/init
fi

exec /bin/sh
EOF

chmod +x "$ROOTFS/init"

echo "=== 2. Re-packaging initramfs.cpio.gz ==="
cd "$ROOTFS"
find . -print0 | cpio --null -H newc -o | gzip -9 > "$OUTPUT/initramfs.cpio.gz"

echo "=== Done! initramfs.cpio.gz updated ==="
ls -lh "$OUTPUT/initramfs.cpio.gz"
