#!/bin/bash
# ==============================================================================
# A33 tablet SD image v2: fixed Wi-Fi (RDA5990P wake + driver), USB RNDIS+ACM gadget,
# SSH, LCD dashboard with Wi-Fi dBm, clock sync. Does NOT touch the v1 builder/images.
# Run as root in WSL:  sudo ./build_sd_image_v2.sh
# ==============================================================================
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOTFS=/root/a33-build/debian-rootfs
KDIR=/root/a33-build/linux
MOD=/root/rda_final/rda5890.ko
WORK=/root/a33_img_v2
IMG=$WORK/a33_debian12_sdcard_v2.img
SIZE=1536M
[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }
for f in "$HERE/u-boot-sunxi-with-spl.bin" "$HERE/boot.scr" "$HERE/sun8i-a33-et-q8-v1.6.dtb" "$KDIR/arch/arm/boot/zImage" "$MOD" "$ROOTFS" "$HERE/overlay"; do
  [ -e "$f" ] || { echo "missing: $f"; exit 1; }
done
KREL=$(ls "$ROOTFS/lib/modules" | head -1)
mkdir -p "$WORK"; rm -f "$IMG"; truncate -s $SIZE "$IMG"
parted -s "$IMG" mklabel msdos
parted -s "$IMG" mkpart primary fat32 2048s 264191s
parted -s "$IMG" set 1 boot on
parted -s "$IMG" mkpart primary ext4 264192s 100%
dd if="$HERE/u-boot-sunxi-with-spl.bin" of="$IMG" bs=1024 seek=8 conv=notrunc status=none
LOOP=$(losetup -fP --show "$IMG"); sleep 1
cleanup() { umount "$WORK/b" 2>/dev/null || true; umount "$WORK/r" 2>/dev/null || true; losetup -d "$LOOP" 2>/dev/null || true; }
trap cleanup EXIT
mkfs.vfat -F 32 -n BOOT "${LOOP}p1" >/dev/null
mkfs.ext4 -F -L rootfs "${LOOP}p2" >/dev/null
mkdir -p "$WORK/b" "$WORK/r"
mount "${LOOP}p1" "$WORK/b"; mount "${LOOP}p2" "$WORK/r"
echo "[*] boot partition"
cp "$HERE/boot.scr" "$WORK/b/"; [ -f "$HERE/boot.cmd" ] && cp "$HERE/boot.cmd" "$WORK/b/"
cp "$KDIR/arch/arm/boot/zImage" "$WORK/b/zImage"
cp "$HERE/sun8i-a33-et-q8-v1.6.dtb" "$WORK/b/"
echo "[*] rootfs (excluding /root/sd_install and stale module copies)"
tar -C "$ROOTFS" --exclude=./root/sd_install --exclude=./root/rda5890.ko --exclude='./proc/*' --exclude='./sys/*' --exclude='./dev/*' --exclude='./tmp/*' -cf - . | tar -C "$WORK/r" -xf -
mkdir -p "$WORK/r"/{boot,dev,proc,sys,run,tmp,mnt,media,root,home}; chmod 1777 "$WORK/r/tmp"
echo "[*] fixed Wi-Fi driver -> /lib/modules/$KREL/extra"
mkdir -p "$WORK/r/lib/modules/$KREL/extra"; cp "$MOD" "$WORK/r/lib/modules/$KREL/extra/rda5890.ko"
depmod -b "$WORK/r" "$KREL"
echo "[*] overlay (services, scripts)"
cp -a "$HERE/overlay/." "$WORK/r/"
W="$WORK/r/etc/systemd/system/multi-user.target.wants"
for s in rda5990-wake a33-wifi a33-timesync usb-gadget wifi-status lcd-dashboard; do ln -sf "/etc/systemd/system/$s.service" "$W/$s.service"; done
# retire the old hard-coded-SSID/pin-hack service and the generic wpa_supplicant unit (replaced by a33-wifi)
rm -f "$W/wifi-connect.service" "$W/wpa_supplicant.service"
cat > "$WORK/r/etc/fstab" <<'FST'
/dev/mmcblk0p2  /      ext4  noatime,errors=remount-ro   0 1
/dev/mmcblk0p1  /boot  vfat  defaults,noatime,umask=022  0 2
tmpfs           /tmp   tmpfs defaults,nosuid,nodev       0 0
FST
echo a33-server > "$WORK/r/etc/hostname"
sync; cleanup; trap - EXIT
cp "$IMG" "$HERE/a33_debian12_sdcard_v2.img"
gzip -kf "$HERE/a33_debian12_sdcard_v2.img"
ls -lh "$HERE"/a33_debian12_sdcard_v2.img*
echo "OK - flash a33_debian12_sdcard_v2.img(.gz) with Rufus/BalenaEtcher/Raspberry Pi Imager"
