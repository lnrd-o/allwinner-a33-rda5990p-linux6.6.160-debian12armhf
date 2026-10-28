#!/bin/bash
# ==============================================================================
# Allwinner A33 Tablet (ET_F900_V1.6 / Q8) Autonomous SD Image Generator
# Builds a ready-to-flash 1GB raw disk image (a33_debian12_sdcard.img)
# that can be written directly to any MicroSD card via Rufus, BalenaEtcher,
# Win32DiskImager, Raspberry Pi Imager, or dd.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMG_FILE="$SCRIPT_DIR/a33_debian12_sdcard.img"
ROOTFS_DIR="/root/a33-build/debian-rootfs"

echo "================================================================="
echo "   Allwinner A33 Tablet Standalone SD Card Image Generator       "
echo "   Board: ET_F900_V1.6 (MID-756 / Q8 layout, 1024x600 LCD)      "
echo "================================================================="

if [ "$(id -u)" -ne 0 ]; then
    echo "[-] Error: This script must be run as root (use sudo)."
    exit 1
fi

UBOOT_BIN="$SCRIPT_DIR/u-boot-sunxi-with-spl.bin"
KERNEL_BIN="$SCRIPT_DIR/zImage"
DTB_BIN="$SCRIPT_DIR/sun8i-a33-et-q8-v1.6.dtb"
BOOT_SCR="$SCRIPT_DIR/boot.scr"
BOOT_CMD="$SCRIPT_DIR/boot.cmd"

for f in "$UBOOT_BIN" "$KERNEL_BIN" "$DTB_BIN" "$BOOT_SCR"; do
    if [ ! -f "$f" ]; then
        echo "[-] Error: Missing required file: $f"
        exit 1
    fi
done

if [ ! -d "$ROOTFS_DIR" ]; then
    echo "[-] Error: Debian rootfs directory ($ROOTFS_DIR) not found!"
    exit 1
fi

echo "[*] Step 1: Creating 1024 MiB (1GB) blank image file..."
rm -f "$IMG_FILE"
truncate -s 1024M "$IMG_FILE"

echo "[*] Step 2: Partitioning image with MBR DOS partition table..."
# Partition 1: Start 2048s (1MB), Size 128MB (264191s), FAT32, Bootable
# Partition 2: Start 264192s, Remainder (100%), ext4
parted -s "$IMG_FILE" mklabel msdos
parted -s "$IMG_FILE" mkpart primary fat32 2048s 264191s
parted -s "$IMG_FILE" set 1 boot on
parted -s "$IMG_FILE" mkpart primary ext4 264192s 100%

echo "[*] Step 3: Writing U-Boot SPL bootloader at 8KB offset (seek=8, bs=1024)..."
# Must be written AFTER parted so parted does not zero out the sector 1-2047 gap
dd if="$UBOOT_BIN" of="$IMG_FILE" bs=1024 seek=8 conv=notrunc status=none

echo "[*] Step 4: Setting up loop device with partition scanning..."
LOOP_DEV=$(losetup -fP --show "$IMG_FILE")
echo "    Assigned loop device: $LOOP_DEV"

# Ensure loop partitions exist
sleep 1
PART_BOOT="${LOOP_DEV}p1"
PART_ROOT="${LOOP_DEV}p2"

if [ ! -b "$PART_BOOT" ] || [ ! -b "$PART_ROOT" ]; then
    echo "[-] Error: Loop partitions ($PART_BOOT, $PART_ROOT) not detected!"
    losetup -d "$LOOP_DEV"
    exit 1
fi

echo "[*] Step 5: Formatting Partition 1 (FAT32 BOOT)..."
mkfs.vfat -F 32 -n "BOOT" "$PART_BOOT"

echo "[*] Step 6: Formatting Partition 2 (ext4 rootfs)..."
mkfs.ext4 -F -L "rootfs" "$PART_ROOT"

# Step 7: Populate Boot Partition
MOUNT_BOOT="/tmp/img_boot_mnt_$$"
mkdir -p "$MOUNT_BOOT"
mount "$PART_BOOT" "$MOUNT_BOOT"

echo "[*] Step 7: Populating boot partition (zImage, DTB, boot scripts)..."
cp -v "$BOOT_SCR" "$MOUNT_BOOT/"
if [ -f "$BOOT_CMD" ]; then cp -v "$BOOT_CMD" "$MOUNT_BOOT/"; fi
cp -v "$KERNEL_BIN" "$MOUNT_BOOT/"
cp -v "$DTB_BIN" "$MOUNT_BOOT/"

sync
umount "$MOUNT_BOOT"
rmdir "$MOUNT_BOOT"

# Step 8: Populate Root Partition
MOUNT_ROOT="/tmp/img_root_mnt_$$"
mkdir -p "$MOUNT_ROOT"
mount "$PART_ROOT" "$MOUNT_ROOT"

echo "[*] Step 8: Copying Debian 12 rootfs into Partition 2..."
cp -a "$ROOTFS_DIR"/. "$MOUNT_ROOT/"

echo "[*] Step 9: Finalizing /etc/fstab and permissions..."
cat << 'EOF' > "$MOUNT_ROOT/etc/fstab"
# /etc/fstab: static file system information for Allwinner A33 SD installation
# <file system>             <mount point>   <type>  <options>                  <dump>  <pass>
/dev/mmcblk0p2              /               ext4    noatime,errors=remount-ro  0       1
/dev/mmcblk0p1              /boot           vfat    defaults,noatime,umask=022 0       2
tmpfs                       /tmp            tmpfs   defaults,nosuid,nodev      0       0
EOF

mkdir -p "$MOUNT_ROOT"/{boot,dev,proc,sys,run,tmp,mnt,media,root,home}
chmod 1777 "$MOUNT_ROOT/tmp"
echo "a33-server" > "$MOUNT_ROOT/etc/hostname"

sync
umount "$MOUNT_ROOT"
rmdir "$MOUNT_ROOT"

echo "[*] Step 10: Detaching loop device..."
losetup -d "$LOOP_DEV"
sync

echo ""
echo "================================================================="
echo "   [✓] SUCCESS: Image Generated Successfully!                   "
echo "   Image Path: $IMG_FILE"
echo "   File Size : $(ls -lh "$IMG_FILE" | awk '{print $5}')"
echo "================================================================="
echo "Flashing Instructions:"
echo "  Windows: Use Rufus, BalenaEtcher, or Raspberry Pi Imager to flash"
echo "           a33_debian12_sdcard.img directly to your MicroSD card."
echo "  Linux  : sudo dd if=a33_debian12_sdcard.img of=/dev/sdX bs=4M status=progress conv=fsync"
echo "================================================================="
