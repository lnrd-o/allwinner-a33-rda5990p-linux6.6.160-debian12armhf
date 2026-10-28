#!/bin/bash
set -e

ROOTFS="/root/a33-build/debian-rootfs"
OUTPUT="/mnt/c/Users/leona/Code/A33 Linux/output"

echo "=== 1. Bootstrapping Debian 12 (Bookworm) armhf rootfs ==="
rm -rf "$ROOTFS"
mkdir -p "$ROOTFS"

debootstrap --arch=armhf --foreign --variant=minbase bookworm "$ROOTFS" http://deb.debian.org/debian

echo "=== 2. Setting up QEMU emulation for second stage ==="
cp /usr/bin/qemu-arm "$ROOTFS/usr/bin/qemu-arm"
cp /usr/bin/qemu-arm "$ROOTFS/usr/bin/qemu-arm-static"
cp /etc/resolv.conf "$ROOTFS/etc/resolv.conf"

echo "=== 3. Completing second stage debootstrap ==="
chroot "$ROOTFS" /debootstrap/debootstrap --second-stage

echo "=== 4. Configuring Debian system and installing packages ==="
cat << 'EOF' > "$ROOTFS/etc/apt/sources.list"
deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware
deb http://deb.debian.org/debian bookworm-updates main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware
EOF

cat << 'EOF' > "$ROOTFS/setup_chroot.sh"
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

apt-get update
apt-get install -y --no-install-recommends \
    net-tools \
    iproute2 \
    openssh-server \
    python3 \
    python3-pip \
    sudo \
    kmod \
    udev \
    systemd-sysv

# Set the root password from the environment (never commit a real one): ROOT_PASSWORD='...' ./build_rootfs.sh
: "${ROOT_PASSWORD:?set ROOT_PASSWORD before running}"
echo "root:${ROOT_PASSWORD}" | chpasswd

# Configure SSH for root login
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/#PermitRootLogin yes/PermitRootLogin yes/' /etc/ssh/sshd_config

# Set Hostname
echo "a33-server" > /etc/hostname
cat << 'EHOST' > /etc/hosts
127.0.0.1   localhost
127.0.1.1   a33-server
EHOST

# Set up automatic network on USB OTG (usb0) and Ethernet (eth0)
cat << 'ENET' > /etc/network/interfaces
auto lo
iface lo inet loopback

allow-hotplug eth0
iface eth0 inet dhcp

allow-hotplug usb0
iface usb0 inet static
    address 192.168.7.2
    netmask 255.255.255.0
ENET

# Clean up apt caches to minimize image size
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
EOF

chmod +x "$ROOTFS/setup_chroot.sh"
chroot "$ROOTFS" /setup_chroot.sh
rm -f "$ROOTFS/setup_chroot.sh"

echo "=== 5. Installing kernel modules and ported RDA Wi-Fi driver ==="
cd /root/a33-build/linux
make modules_install ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- INSTALL_MOD_PATH="$ROOTFS"

mkdir -p "$ROOTFS/lib/modules/6.6.160-dirty/extra"
cp /root/a33-build/rda5990_ported/rda5890.ko "$ROOTFS/lib/modules/6.6.160-dirty/extra/"
depmod -b "$ROOTFS" 6.6.160-dirty

# Clean up QEMU binary from final rootfs
rm -f "$ROOTFS/usr/bin/qemu-arm" "$ROOTFS/usr/bin/qemu-arm-static"

# Create /init symlink to systemd
ln -sf /lib/systemd/systemd "$ROOTFS/init"

echo "=== 6. Packaging into initramfs.cpio.gz ==="
cd "$ROOTFS"
mkdir -p "$OUTPUT"
find . -print0 | cpio --null -H newc -o | gzip -9 > "$OUTPUT/initramfs.cpio.gz"

echo "=== Done! Generated initramfs.cpio.gz successfully ==="
ls -lh "$OUTPUT/initramfs.cpio.gz"
