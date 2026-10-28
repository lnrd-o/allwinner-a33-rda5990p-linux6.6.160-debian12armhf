#!/bin/bash
# ==============================================================================
# Allwinner A33 Tablet (ET_F900_V1.6 / Q8) Target-Side SD Installation Script
# Installs U-Boot SPL, Mainline Linux Kernel 6.6 LTS, and Debian 12 (Bookworm)
# directly onto a MicroSD card (/dev/mmcblk0) from the running tablet.
# ==============================================================================

set -e

# Default to mmc0 (/dev/mmcblk0) if not specified
TARGET_DEV="${1:-/dev/mmcblk0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================================="
echo "   Allwinner A33 Tablet Autonomous MicroSD Installation Script   "
echo "   Board: ET_F900_V1.6 (MID-756 / Q8 layout, 1024x600 LCD)      "
echo "================================================================="
echo "Target Device: $TARGET_DEV"
echo "Source Directory: $SCRIPT_DIR"
echo "================================================================="

# Check root privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "[-] Error: This script must be run as root (use sudo)."
    exit 1
fi

# Verify target device exists and is a block device
if [ ! -b "$TARGET_DEV" ]; then
    echo "[-] Error: Target block device $TARGET_DEV does not exist!"
    echo "    Please verify that the MicroSD card is firmly inserted into the TF slot."
    echo "    Check 'dmesg | tail' or 'cat /proc/partitions' for available block devices."
    exit 1
fi

# Safety check: Prevent overwriting current active root device
ROOT_DEV=$(mount | grep ' on / ' | awk '{print $1}')
if [[ "$ROOT_DEV" == "$TARGET_DEV"* ]]; then
    echo "[-] CRITICAL ERROR: Target device $TARGET_DEV is currently mounted as root ($ROOT_DEV)!"
    echo "    Refusing to overwrite active running system."
    exit 1
fi

# Locate required boot files
UBOOT_BIN="$SCRIPT_DIR/u-boot-sunxi-with-spl.bin"
KERNEL_BIN="$SCRIPT_DIR/zImage"
DTB_BIN="$SCRIPT_DIR/sun8i-a33-et-q8-v1.6.dtb"
BOOT_SCR="$SCRIPT_DIR/boot.scr"
BOOT_CMD="$SCRIPT_DIR/boot.cmd"
ROOTFS_TAR="$SCRIPT_DIR/rootfs.tar.gz"

for f in "$UBOOT_BIN" "$KERNEL_BIN" "$DTB_BIN" "$BOOT_SCR"; do
    if [ ! -f "$f" ]; then
        echo "[-] Error: Missing required boot file: $f"
        exit 1
    fi
done

# Check required partitioning and filesystem tools
for cmd in dd parted mkfs.vfat mkfs.ext4; do
    if ! command -v "$cmd" &>/dev/null; then
        # Try fdisk if parted is missing
        if [ "$cmd" = "parted" ] && command -v sfdisk &>/dev/null; then
            continue
        fi
        echo "[-] Missing required utility: $cmd"
        echo "    Attempting to install missing utilities via apt-get..."
        apt-get update && apt-get install -y parted dosfstools e2fsprogs fdisk rsync || {
            echo "[-] Error: Could not install required tools. Aborting."
            exit 1
        }
        break
    fi
done

# Confirm with warning
echo ""
echo "[!] WARNING: ALL DATA ON $TARGET_DEV WILL BE PERMANENTLY ERASED!"
echo "    Size of target: $(blockdev --getsize64 "$TARGET_DEV" 2>/dev/null | awk '{printf "%.2f GB\n", $1/1073741824}')"
echo ""
if [ -t 0 ]; then
    read -p "Type 'yes' to proceed with full installation: " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Installation aborted by user."
        exit 0
    fi
fi

# Update LCD dashboard if present
if [ -x /usr/local/bin/lcd_dashboard.py ]; then
    python3 /usr/local/bin/lcd_dashboard.py "INSTALLING DEBIAN TO MICROSD CARD" 10 2>/dev/null || true
fi

# 1. Unmount any currently mounted partitions on the target device
echo "[*] Step 1: Unmounting any active partitions on $TARGET_DEV..."
for part in $(ls ${TARGET_DEV}* 2>/dev/null); do
    if mount | grep -q "^$part "; then
        echo "    Unmounting $part..."
        umount -f "$part" || true
    fi
done

# 2. Clear first 4MB of the card (MBR, partition tables, and SPL offset)
echo "[*] Step 2: Clearing initial 4MB of SD card..."
dd if=/dev/zero of="$TARGET_DEV" bs=1M count=4 conv=fsync status=none

# 3. Partition the MicroSD Card
# Partition 1: Start 2048s (1MB offset), Size 128MB (264191s), Type FAT32 (0x0c), Bootable
# Partition 2: Start 264192s, End 100%, Type Linux (0x83)
echo "[*] Step 3: Creating partition table (MBR / DOS)..."
if command -v parted &>/dev/null; then
    parted -s "$TARGET_DEV" mklabel msdos
    parted -s "$TARGET_DEV" mkpart primary fat32 2048s 264191s
    parted -s "$TARGET_DEV" set 1 boot on
    parted -s "$TARGET_DEV" mkpart primary ext4 264192s 100%
elif command -v sfdisk &>/dev/null; then
    sfdisk "$TARGET_DEV" << 'EOF'
2048,262144,0x0c,*
,,0x83
EOF
else
    echo "[-] Error: Neither parted nor sfdisk is available to partition $TARGET_DEV!"
    exit 1
fi

# 4. Write Allwinner U-Boot SPL and U-Boot proper at offset 8KB (seek=8, bs=1024)
# Sector 16 = 8KB offset where the Allwinner A33 BROM reads SPL header
# Must be written AFTER parted so parted does not clear sector 1-2047 gap
echo "[*] Step 4: Flashing U-Boot SPL bootloader (offset 8KB / seek=8)..."
dd if="$UBOOT_BIN" of="$TARGET_DEV" bs=1024 seek=8 conv=notrunc,fsync status=none

# Re-read partition table
sync
partprobe "$TARGET_DEV" 2>/dev/null || blockdev --rereadpt "$TARGET_DEV" 2>/dev/null || true
sleep 2

# Identify partition device nodes
if [[ "$TARGET_DEV" =~ [0-9]$ ]]; then
    PART_BOOT="${TARGET_DEV}p1"
    PART_ROOT="${TARGET_DEV}p2"
else
    PART_BOOT="${TARGET_DEV}1"
    PART_ROOT="${TARGET_DEV}2"
fi

if [ ! -b "$PART_BOOT" ] || [ ! -b "$PART_ROOT" ]; then
    echo "[-] Error: Partitions ($PART_BOOT, $PART_ROOT) not detected by kernel after partitioning!"
    exit 1
fi

echo "    Boot partition: $PART_BOOT"
echo "    Root partition: $PART_ROOT"

# 5. Format Partitions
echo "[*] Step 5: Formatting Partition 1 as FAT32 (BOOT)..."
mkfs.vfat -F 32 -n "BOOT" "$PART_BOOT"

echo "[*] Step 6: Formatting Partition 2 as ext4 (rootfs)..."
mkfs.ext4 -F -L "rootfs" "$PART_ROOT"

# Update LCD dashboard
if [ -x /usr/local/bin/lcd_dashboard.py ]; then
    python3 /usr/local/bin/lcd_dashboard.py "COPYING BOOTLOADER & KERNEL TO SD" 45 2>/dev/null || true
fi

# 6. Populate Boot Partition
MOUNT_BOOT="/tmp/sd_boot_mnt"
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

# Update LCD dashboard
if [ -x /usr/local/bin/lcd_dashboard.py ]; then
    python3 /usr/local/bin/lcd_dashboard.py "INSTALLING DEBIAN ROOTFS TO SD" 65 2>/dev/null || true
fi

# 7. Populate Root Partition
MOUNT_ROOT="/tmp/sd_root_mnt"
mkdir -p "$MOUNT_ROOT"
mount "$PART_ROOT" "$MOUNT_ROOT"

echo "[*] Step 8: Installing Debian 12 rootfs onto $PART_ROOT..."
if [ -f "$ROOTFS_TAR" ]; then
    echo "    Extracting rootfs archive ($ROOTFS_TAR)..."
    tar -xzf "$ROOTFS_TAR" -C "$MOUNT_ROOT" --numeric-owner
else
    echo "    rootfs.tar.gz not found; cloning current running live system..."
    rsync -aHAX --info=progress2 \
        --exclude=/proc/* \
        --exclude=/sys/* \
        --exclude=/dev/* \
        --exclude=/run/* \
        --exclude=/tmp/* \
        --exclude=/mnt/* \
        --exclude=/lost+found \
        / "$MOUNT_ROOT/"
fi

# Ensure essential mountpoints exist
mkdir -p "$MOUNT_ROOT"/{boot,dev,proc,sys,run,tmp,mnt,media,root,home}
chmod 1777 "$MOUNT_ROOT/tmp"

# Configure persistent /etc/fstab
echo "[*] Step 9: Writing /etc/fstab..."
cat << 'EOF' > "$MOUNT_ROOT/etc/fstab"
# /etc/fstab: static file system information for Allwinner A33 SD installation
# <file system>             <mount point>   <type>  <options>                  <dump>  <pass>
/dev/mmcblk0p2              /               ext4    noatime,errors=remount-ro  0       1
/dev/mmcblk0p1              /boot           vfat    defaults,noatime,umask=022 0       2
tmpfs                       /tmp            tmpfs   defaults,nosuid,nodev      0       0
EOF

# Ensure hostname is set
echo "a33-server" > "$MOUNT_ROOT/etc/hostname"

# Sync disk buffers
echo "[*] Step 10: Syncing all data to MicroSD card..."
sync

umount "$MOUNT_ROOT"
rmdir "$MOUNT_ROOT"
sync

echo "================================================================="
echo "   [✓] SUCCESS: MicroSD Installation Finished Completely!       "
echo "================================================================="
echo "The MicroSD card is now ready for autonomous standalone booting:"
echo "  1. Shut down the tablet: 'poweroff'"
echo "  2. Disconnect the USB OTG cable from the PC."
echo "  3. Press and hold the Power button for 3 seconds."
echo "  4. The tablet will boot directly from the SD card into Debian 12."
echo "  5. The LCD dashboard will appear automatically on the 1024x600 screen."
echo "================================================================="

if [ -x /usr/local/bin/lcd_dashboard.py ]; then
    python3 /usr/local/bin/lcd_dashboard.py "SD INSTALL COMPLETE! READY TO REBOOT" 100 2>/dev/null || true
fi
