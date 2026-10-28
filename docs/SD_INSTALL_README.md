# Allwinner A33 Tablet (ET_F900_V1.6 / Q8) Autonomous MicroSD Installation Guide

Complete standalone local storage installation suite for the **Allwinner A33 Quad-Core Tablet** (Motherboard: `ET_F900_V1.6 140928`, MID-756 / Q8 layout, 1024x600 LCD, 1GB DDR3 RAM).

Once installed, the tablet boots Debian 12 (Bookworm) and Mainline Linux 6.6 LTS autonomously from the MicroSD card without requiring a PC, USB OTG cable, or FEL mode.

---

## SD Card Layout Architecture

Allwinner Sunxi SoCs have a hardwired Boot ROM (BROM) execution sequence. The SD card is partitioned and populated according to the mainline sunxi specification:

| Offset / Sector | Size / Range | Purpose / Content | Filesystem |
| :--- | :--- | :--- | :--- |
| **0 - 512 B** (Sector 0) | 512 Bytes | Master Boot Record (MBR DOS Partition Table) | Raw Binary |
| **8 KB** (Sector 16) | 32 KB | **U-Boot SPL (Secondary Program Loader)** with eGON header | Raw Binary |
| **40 KB** (Sector 80) | ~520 KB | **U-Boot Proper** (`u-boot-sunxi-with-spl.bin`) | Raw Binary |
| **1 MB** (Sector 2048) | 128 MB | **Partition 1 (BOOT, Active/Bootable)**: `boot.scr`, `boot.cmd`, `zImage`, `sun8i-a33-et-q8-v1.6.dtb` | FAT32 (`vfat`) |
| **129 MB** (Sector 264192)| Remainder | **Partition 2 (ROOTFS)**: Persistent Debian 12 rootfs + `/etc/fstab` | `ext4` |

---

## 3 Installation Methods

Choose whichever method best fits your current setup:

### Method 1: One-Click GUI Flashing on Windows (Easiest & Fastest)
You can flash the pre-built disk image directly using any standard imaging utility:

1. Insert your MicroSD card into your PC via a USB card reader.
2. Open **Rufus**, **BalenaEtcher**, or **Raspberry Pi Imager**.
3. Select the pre-generated image:
   - `a33_debian12_sdcard.img` (or compressed `a33_debian12_sdcard.img.gz`).
4. Select your MicroSD card as the target and click **Write / Flash**.
5. Alternatively, right-click `prepare_sd_card.bat` and select **Run as Administrator** to launch the interactive flasher.
6. Once complete, insert the MicroSD card into the tablet and power it on!

---

### Method 2: Host-Side Installation via WSL / Linux (`prepare_sd_card.sh`)
If you prefer preparing the SD card from the command line in WSL or native Linux:

1. Insert the MicroSD card into your PC's USB card reader.
2. In WSL Ubuntu or Linux terminal, check the device name:
   ```bash
   lsblk -d -o NAME,SIZE,MODEL,TRAN,RM
   ```
   *(e.g. `/dev/sdb` or `/dev/sdc`)*
3. Run the automated host preparation script with `sudo`:
   ```bash
   cd "/mnt/c/Users/leona/Code/A33 Linux/sd_install"
   sudo ./prepare_sd_card.sh /dev/sdX
   ```
4. The script will:
   - Clear existing partition tables
   - Partition the card (128MB FAT32 bootable + remaining ext4)
   - Write U-Boot SPL at 8KB offset
   - Format both partitions
   - Populate Partition 1 with `zImage`, `dtb`, `boot.scr`
   - Extract `rootfs.tar.gz` into Partition 2 and configure `/etc/fstab`
5. Eject the card and insert it into the tablet TF slot.

---

### Method 3: Target-Side Installation on Tablet (`install_to_sd.sh`)
If the tablet is already running live Debian over USB FEL mode:

1. Plug the MicroSD card directly into the tablet's TF card slot.
2. Open your serial console on **COM22** (or SSH into `192.168.7.2`):
   ```bash
   cd /root/sd_install
   ./install_to_sd.sh /dev/mmcblk0
   ```
3. Type `yes` to confirm. The tablet will:
   - Zero out the card header
   - Partition `/dev/mmcblk0` into `p1` (BOOT) and `p2` (ROOTFS)
   - Flash U-Boot SPL to sector 16
   - Format `BOOT` (FAT32) and `rootfs` (ext4)
   - Copy boot files and extract or clone the live rootfs directly to `/dev/mmcblk0p2`
   - Display progress on the live LCD dashboard!
4. When complete, power off the tablet:
   ```bash
   poweroff
   ```
5. Unplug the USB OTG cable. Hold the Power button for 3 seconds. The tablet boots autonomously from the SD card!

---

## Bootloader & Kernel Configuration Details

### Boot Arguments (`bootargs`)
Defined in `boot.cmd` and compiled into `boot.scr`:
```text
console=ttyS0,115200 console=tty1 console=ttyGS0,115200 root=/dev/mmcblk0p2 rootwait rw panic=10
```
- **`console=tty1`**: Connects Linux VT console to the 1024x600 LCD simple-framebuffer (`/dev/fb0`).
- **`console=ttyS0,115200`**: UART0 serial debug output.
- **`console=ttyGS0,115200`**: USB OTG CDC-ACM serial terminal (`COM22` on Windows).
- **`root=/dev/mmcblk0p2 rootwait rw`**: Directly mounts the ext4 second partition of the MicroSD card as persistent root.
- **`panic=10`**: Automatically reboots after 10 seconds if a kernel panic occurs.

### File System Table (`/etc/fstab`)
Configured automatically in Partition 2:
```text
/dev/mmcblk0p2   /      ext4   noatime,errors=remount-ro  0  1
/dev/mmcblk0p1   /boot  vfat   defaults,noatime,umask=022 0  2
tmpfs            /tmp   tmpfs  defaults,nosuid,nodev      0  0
```

---

## Expanding Partition 2 to Full SD Card Capacity

If your MicroSD card is larger than the 1GB image (e.g. 8GB, 16GB, 32GB, 64GB):
1. After booting into Debian on the tablet, run `parted` or `fdisk` to resize the partition:
   ```bash
   parted /dev/mmcblk0 resizepart 2 100%
   resize2fs /dev/mmcblk0p2
   ```
2. Verify the expanded capacity:
   ```bash
   df -h /
   ```

---

## Summary of Files in `sd_install/`

- `a33_debian12_sdcard.img` : Ready-to-flash 1GB raw disk image.
- `a33_debian12_sdcard.img.gz` : Compressed image for fast writing with Rufus / BalenaEtcher.
- `install_to_sd.sh` : Target-side installation script (runs on tablet).
- `prepare_sd_card.sh` : Host-side script for Linux / WSL.
- `prepare_sd_card.bat` : Windows double-clickable launcher with UAC elevation.
- `prepare_sd_card.py` : Cross-platform host utility.
- `build_sd_image.sh` : Re-builds `a33_debian12_sdcard.img` anytime from sources.
- `boot.cmd` / `boot.scr` : U-Boot boot script for standalone MicroSD boot.
- `rootfs.tar.gz` : Complete Debian 12 rootfs archive with tools and drivers.
- `u-boot-sunxi-with-spl.bin` : Allwinner A33 U-Boot bootloader with SPL.
- `zImage` : Mainline Linux 6.6.160 LTS kernel with built-in MMC/ext4.
- `sun8i-a33-et-q8-v1.6.dtb` : Compiled Device Tree with MMC0 broken-cd and display timings.
