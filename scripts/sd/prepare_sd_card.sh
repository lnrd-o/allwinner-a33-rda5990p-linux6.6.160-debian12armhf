#!/bin/bash
# ==============================================================================
# Allwinner A33 Tablet (ET_F900_V1.6 / Q8) Host-Side SD Preparation Script
# For WSL Ubuntu or native Linux PC with an SD card in a USB Card Reader.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DEV="$1"

echo "================================================================="
echo "   Allwinner A33 Tablet Host MicroSD Card Preparation Script     "
echo "   Board: ET_F900_V1.6 (MID-756 / Q8 layout, 1024x600 LCD)      "
echo "================================================================="

# Check root privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "[-] Error: This script must be run as root (use sudo)."
    echo "    Example: sudo ./prepare_sd_card.sh /dev/sdb"
    exit 1
fi

# If target device is not provided, list available disks
if [ -z "$TARGET_DEV" ]; then
    echo ""
    echo "[!] No target block device specified."
    echo "Available block devices on this system:"
    echo "-----------------------------------------------------------------"
    lsblk -d -o NAME,SIZE,TYPE,TRAN,RM,MODEL 2>/dev/null || fdisk -l 2>/dev/null | grep "Disk /dev"
    echo "-----------------------------------------------------------------"
    echo ""
    read -p "Enter target block device (e.g. /dev/sdb or /dev/sdc): " TARGET_DEV
fi

# Verify device node
if [ ! -b "$TARGET_DEV" ]; then
    echo "[-] Error: '$TARGET_DEV' is not a valid block device!"
    exit 1
fi

# CRITICAL SAFETY CHECK: Never touch system partitions
ROOT_PART=$(findmnt -n -o SOURCE / 2>/dev/null || df / | tail -1 | awk '{print $1}')
if [[ "$ROOT_PART" == "$TARGET_DEV"* ]]; then
    echo "[-] CRITICAL ERROR: '$TARGET_DEV' contains the current running root filesystem ($ROOT_PART)!"
    echo "    Refusing to overwrite host operating system."
    exit 1
fi

# Locate boot and rootfs files
UBOOT_BIN="$SCRIPT_DIR/u-boot-sunxi-with-spl.bin"
KERNEL_BIN="$SCRIPT_DIR/zImage"
DTB_BIN="$SCRIPT_DIR/sun8i-a33-et-q8-v1.6.dtb"
BOOT_SCR="$SCRIPT_DIR/boot.scr"
BOOT_CMD="$SCRIPT_DIR/boot.cmd"
ROOTFS_TAR="$SCRIPT_DIR/rootfs.tar.gz"

for f in "$UBOOT_BIN" "$KERNEL_BIN" "$DTB_BIN" "$BOOT_SCR" "$ROOTFS_TAR"; do
    if [ ! -f "$f" ]; then
        echo "[-] Error: Missing required file: $f"
        exit 1
    fi
done

# Check required tools
for tool in dd parted mkfs.vfat mkfs.ext4 tar; do
    if ! command -v "$tool" &>/dev/null; then
        echo "[-] Missing required host tool: $tool"
        echo "    Install with: apt-get install -y parted dosfstools e2fsprogs tar"
        exit 1
    fi
done

# Disk information and confirmation
DEV_SIZE=$(lsblk -bno SIZE "$TARGET_DEV" 2>/dev/null | head -1)
DEV_SIZE_GB=$(awk "BEGIN {printf \"%.2f\", $DEV_SIZE/1073741824}")

echo ""
echo "================================================================="
echo "  TARGET DEVICE : $TARGET_DEV"
echo "  CAPACITY      : $DEV_SIZE_GB GB"
echo "  MODEL         : $(lsblk -dno MODEL "$TARGET_DEV" 2>/dev/null || echo 'Unknown')"
echo "================================================================="
echo "[!] WARNING: ALL PARTITIONS AND DATA ON $TARGET_DEV WILL BE DESTROYED!"
echo "================================================================="
echo ""
read -p "Type 'yes' to confirm and write to $TARGET_DEV: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Operation aborted by user."
    exit 0
fi

# Step 1: Unmount all existing partitions on target
echo ""
echo "[*] Step 1: Unmounting all partitions on $TARGET_DEV..."
for part in $(ls ${TARGET_DEV}* 2>/dev/null); do
    if mount | grep -q "^$part "; then
        echo "    Unmounting $part..."
        umount -f "$part" || true
    fi
done

# Step 2: Clear first 4MB (MBR, partition tables, SPL area)
echo "[*] Step 2: Clearing initial 4MB of the disk..."
dd if=/dev/zero of="$TARGET_DEV" bs=1M count=4 conv=fsync status=none

# Step 3: Partition device into MBR DOS table
# Partition 1: 2048s (1MB) to 264191s (128MB), FAT32, Bootable
# Partition 2: 264192s to 100%, ext4 (rootfs)
echo "[*] Step 3: Partitioning disk (Partition 1: 128MB FAT32 Bootable, Partition 2: Remainder ext4)..."
parted -s "$TARGET_DEV" mklabel msdos
parted -s "$TARGET_DEV" mkpart primary fat32 2048s 264191s
parted -s "$TARGET_DEV" set 1 boot on
parted -s "$TARGET_DEV" mkpart primary ext4 264192s 100%

# Step 4: Write Allwinner U-Boot SPL bootloader at offset 8KB (8192 bytes = seek 8, bs 1024)
# Must be written AFTER parted so parted does not zero out the sector 1-2047 gap
echo "[*] Step 4: Flashing U-Boot SPL (u-boot-sunxi-with-spl.bin) at offset 8KB..."
dd if="$UBOOT_BIN" of="$TARGET_DEV" bs=1024 seek=8 conv=notrunc,fsync status=progress

sync
partprobe "$TARGET_DEV" 2>/dev/null || blockdev --rereadpt "$TARGET_DEV" 2>/dev/null || true
sleep 2

# Identify partition nodes
if [[ "$TARGET_DEV" =~ [0-9]$ ]]; then
    PART_BOOT="${TARGET_DEV}p1"
    PART_ROOT="${TARGET_DEV}p2"
else
    PART_BOOT="${TARGET_DEV}1"
    PART_ROOT="${TARGET_DEV}2"
fi

if [ ! -b "$PART_BOOT" ] || [ ! -b "$PART_ROOT" ]; then
    echo "[-] Error: Partition block devices ($PART_BOOT, $PART_ROOT) not detected!"
    exit 1
fi

# Step 5: Format partitions
echo "[*] Step 5: Formatting Partition 1 as FAT32 (BOOT)..."
mkfs.vfat -F 32 -n "BOOT" "$PART_BOOT"

echo "[*] Step 6: Formatting Partition 2 as ext4 (rootfs)..."
mkfs.ext4 -F -L "rootfs" "$PART_ROOT"

# Step 6: Populate Boot Partition
MOUNT_BOOT="/tmp/sd_boot_mnt_$$"
mkdir -p "$MOUNT_BOOT"
mount "$PART_BOOT" "$MOUNT_BOOT"

echo "[*] Step 7: Copying kernel, DTB, and boot scripts to $PART_BOOT..."
cp -v "$BOOT_SCR" "$MOUNT_BOOT/"
if [ -f "$BOOT_CMD" ]; then cp -v "$BOOT_CMD" "$MOUNT_BOOT/"; fi
cp -v "$KERNEL_BIN" "$MOUNT_BOOT/"
cp -v "$DTB_BIN" "$MOUNT_BOOT/"

sync
umount "$MOUNT_BOOT"
rmdir "$MOUNT_BOOT"

# Step 7: Populate Root Partition
MOUNT_ROOT="/tmp/sd_root_mnt_$$"
mkdir -p "$MOUNT_ROOT"
mount "$PART_ROOT" "$MOUNT_ROOT"

echo "[*] Step 8: Extracting complete Debian 12 rootfs onto $PART_ROOT..."
echo "    Extracting rootfs.tar.gz (this may take 15-30 seconds)..."
tar -xzf "$ROOTFS_TAR" -C "$MOUNT_ROOT" --numeric-owner

echo "[*] Step 9: Verifying /etc/fstab and system configuration..."
cat << 'EOF' > "$MOUNT_ROOT/etc/fstab"
# /etc/fstab: static file system information for Allwinner A33 SD installation
# <file system>             <mount point>   <type>  <options>                  <dump>  <pass>
/dev/mmcblk0p2              /               ext4    noatime,errors=remount-ro  0       1
/dev/mmcblk0p1              /boot           vfat    defaults,noatime,umask=022 0       2
tmpfs                       /tmp            tmpfs   defaults,nosuid,nodev      0       0
EOF

# Ensure essential mountpoints exist
mkdir -p "$MOUNT_ROOT"/{boot,dev,proc,sys,run,tmp,mnt,media,root,home}
chmod 1777 "$MOUNT_ROOT/tmp"

echo "a33-server" > "$MOUNT_ROOT/etc/hostname"

echo "[*] Step 10: Syncing disk caches to MicroSD card..."
sync

umount "$MOUNT_ROOT"
rmdir "$MOUNT_ROOT"
sync

echo ""
echo "================================================================="
echo "   [✓] SUCCESS: MicroSD Card is Prepared & Ready!               "
echo "================================================================="
echo "Autonomous Boot Instructions:"
echo "  1. Safely eject the MicroSD card from your PC."
echo "  2. Insert the MicroSD card into the tablet's TF slot."
echo "  3. Disconnect USB OTG cable (or leave connected to observe COM22)."
echo "  4. Press and hold the Power button for 3 seconds."
echo "  5. The tablet will boot autonomously into Debian 12!"
echo "  6. The 1024x600 LCD will display the live system dashboard."
echo "================================================================="
