# Allwinner A33 Tablet (ET_F900_V1.6 / Q8) SD Installation Work Log & Handoff Document

This document records the complete architecture, findings, problem diagnosis, fixes applied, and next steps for the autonomous MicroSD card boot setup on the **Allwinner A33 Tablet** (`ET_F900_V1.6 140928` motherboard, MID-756 / Q8 layout, 1024x600 LCD, 1GB DDR3 RAM).

---

## 1. Executive Summary

- **Goal**: Enable the tablet to boot autonomously from a MicroSD card (`mmc0` / `1c0f000.mmc`) directly into Debian 12 (Bookworm) armhf and Mainline Linux 6.6 LTS, with persistent storage and LCD console dashboard, without needing a PC or FEL mode.
- **Previous State**: Tablet only booted via USB FEL mode over OTG (`sunxi-fel.exe` pushing U-Boot, zImage, DTB, and a 130MB `uInitrd` ramdisk).
- **Current State**: Full standalone SD installation suite created in `c:\Users\leona\Code\A33 Linux\sd_install\`, complete with:
  1. Ready-to-flash 1GB raw disk images (`a33_debian12_sdcard.img` & `a33_debian12_sdcard.img.gz`).
  2. Target-side automated installer script (`install_to_sd.sh`).
  3. Host-side WSL / Linux script (`prepare_sd_card.sh`).
  4. Windows double-clickable launcher (`prepare_sd_card.bat` / `prepare_sd_card.py`).
  5. Standalone image builder (`build_sd_image.sh`).

---

## 2. Diagnosis & Root Cause of the "No ethernet found" Error

When the user first flashed the SD card and powered on the tablet, U-Boot stopped and printed:
```text
No ethernet found.
No ethernet found.
=>
```

### Why this occurred:
1. **Card Detect (CD) GPIO Failure**:
   - In U-Boot's default device tree (`arch/arm/dts/sun8i-reference-design-tablet.dtsi`), `&mmc0` had:
     ```dts
     cd-gpios = <&pio 1 4 GPIO_ACTIVE_LOW>; /* PB4 */
     ```
   - In U-Boot's configuration, `CONFIG_MMC_BROKEN_CD` was **not set**.
   - On the `ET_F900_V1.6` tablet motherboard, the TF card socket's mechanical Card Detect switch is either not connected to PB4, oxidized, or active-high.
   - When U-Boot ran `mmc dev 0`, `sunxi_mmc_getcd()` queried PB4, which read `0` (not grounded), causing U-Boot to report `MMC: no card present` (`-ENOMEDIUM`).
2. **Distro Boot Fallthrough**:
   - U-Boot's `distro_bootcmd` scans targets in order: `fel mmc0 usb0 pxe dhcp`.
   - `fel`: Skipped (not booted over USB FEL).
   - `mmc0`: Skipped because `mmc dev 0` reported no card.
   - `usb0`: Skipped (no USB mass storage attached).
   - `pxe`: Tried to boot via network PXE -> invoked `dhcp`.
   - `dhcp`: Tried to initialize network hardware. Because the A33 tablet has no on-board Ethernet chip or RJ-45 jack, `net/eth-uclass.c` logged `No ethernet found.`.
   - U-Boot halted at the interactive prompt `=>`.

---

## 3. Fixes Implemented

### Fix A: U-Boot Device Tree Update
In `/root/a33-build/u-boot/arch/arm/dts/sun8i-a33-q8-tablet.dts`:
Added `broken-cd;` to `&mmc0`:
```dts
&mmc0 {
	vmmc-supply = <&reg_dcdc1>;
	bus-width = <4>;
	broken-cd;
	status = "okay";
};
```
This instructs U-Boot's MMC driver to bypass GPIO pin PB4 and directly poll/probe the card via CLK/CMD/DAT lines.

### Fix B: U-Boot Defconfig Hardening
In `/root/a33-build/u-boot/configs/q8_a33_tablet_1024x600_defconfig`:
1. **Enabled Broken CD**:
   ```ini
   CONFIG_MMC_BROKEN_CD=y
   ```
2. **Disabled Network Booting Completely**:
   ```ini
   # CONFIG_CMD_PXE is not set
   # CONFIG_CMD_DHCP is not set
   # CONFIG_CMD_NET is not set
   # CONFIG_NET is not set
   ```
   Removing PXE/DHCP ensures U-Boot never attempts network queries on this hardware.
3. **Hardened Multi-Stage Boot Command (`CONFIG_BOOTCOMMAND`)**:
   ```ini
   CONFIG_USE_BOOTCOMMAND=y
   CONFIG_BOOTCOMMAND="if test -n ${fel_booted}; then source 0x43100000 || bootz 0x42000000 0x44000000 0x43000000; fi; if mmc rescan; then echo MMC detected; fi; if load mmc 0:1 0x43100000 boot.scr; then echo Running boot.scr...; source 0x43100000; fi; if load mmc 0:1 0x42000000 zImage && load mmc 0:1 0x43000000 sun8i-a33-et-q8-v1.6.dtb; then echo Booting zImage directly...; setenv bootargs console=tty1 console=ttyS0,115200 console=ttyGS0,115200 root=/dev/mmcblk0p2 rootwait rw panic=10; bootz 0x42000000 - 0x43000000; fi; run distro_bootcmd"
   ```
   - **Stage 1 (FEL Mode)**: If booted via FEL, immediately sources script at `0x43100000` (preserves existing PC FEL boot).
   - **Stage 2 (SD Boot)**: Rescans MMC with broken-cd, loads `/boot.scr` from `mmc 0:1`, and executes it.
   - **Stage 3 (Direct Fallback)**: If `boot.scr` is missing/corrupted, directly loads `zImage` and `sun8i-a33-et-q8-v1.6.dtb` and boots into `root=/dev/mmcblk0p2`.
   - **Stage 4 (Distro Fallback)**: Runs `distro_bootcmd`.
4. **Bootargs**:
   ```ini
   CONFIG_USE_BOOTARGS=y
   CONFIG_BOOTARGS="console=tty1 console=ttyS0,115200 console=ttyGS0,115200 root=/dev/mmcblk0p2 rootwait rw panic=10"
   ```

### Fix C: Recompiled U-Boot
U-Boot was recompiled with `make -j16`.
New binary generated:
- Size: 516,776 bytes (~505 KB).
- Copied to:
  - `c:\Users\leona\Code\A33 Linux\output\u-boot-sunxi-with-spl.bin`
  - `c:\Users\leona\Code\A33 Linux\sd_install\u-boot-sunxi-with-spl.bin`
  - WSL `/root/a33-build/debian-rootfs/root/sd_install/u-boot-sunxi-with-spl.bin`

### Fix D: Regenerated Ready-to-Flash Disk Images
Re-ran `build_sd_image.sh` with the new U-Boot binary:
- `sd_install/a33_debian12_sdcard.img` (1,073,741,824 bytes = 1.0 GB)
- `sd_install/a33_debian12_sdcard.img.gz` (150,801,775 bytes = 143.8 MB)

Verified Image Layout:
- Sector 0: MBR DOS Partition Table
- Sector 16 (8 KB offset): SPL bootloader with valid `eGON.BT0` magic header
- Sector 2048 (1 MB offset): Partition 1 (`BOOT`, FAT32, 128 MB, Bootable) containing `boot.scr`, `boot.cmd`, `zImage`, `sun8i-a33-et-q8-v1.6.dtb`
- Sector 264192 (129 MB offset): Partition 2 (`rootfs`, ext4, 895 MB) containing full Debian 12 rootfs + `/etc/fstab`

---

## 4. Manifest of Files in `c:\Users\leona\Code\A33 Linux\sd_install\`

| File | Size | Description |
| :--- | :--- | :--- |
| `a33_debian12_sdcard.img` | 1.0 GB | Uncompressed raw disk image ready for direct flashing |
| `a33_debian12_sdcard.img.gz`| 143.8 MB | Gzip compressed disk image (Rufus / BalenaEtcher compatible) |
| `u-boot-sunxi-with-spl.bin` | 505 KB | New U-Boot binary with `CONFIG_MMC_BROKEN_CD=y` |
| `zImage` | 5.8 MB | Linux 6.6.160 LTS mainline kernel (built-in MMC & ext4) |
| `sun8i-a33-et-q8-v1.6.dtb` | 24.9 KB | Compiled Device Tree (MMC0 broken-cd + simplefb 1024x600) |
| `boot.cmd` | 1.6 KB | U-Boot script source |
| `boot.scr` | 1.7 KB | Compiled U-Boot script (`mkimage -T script`) |
| `rootfs.tar.gz` | 118.8 MB | Full Debian 12 armhf rootfs archive |
| `install_to_sd.sh` | 9.0 KB | Target-side installation script (runs on tablet) |
| `prepare_sd_card.sh` | 7.7 KB | Host-side installation script (WSL / Linux) |
| `prepare_sd_card.py` | 8.1 KB | Cross-platform Python flasher |
| `prepare_sd_card.bat` | 1.1 KB | Windows double-clickable launcher with UAC auto-elevation |
| `build_sd_image.sh` | 4.9 KB | Standalone script to regenerate `a33_debian12_sdcard.img` |
| `README.md` | 5.6 KB | Comprehensive guide and reference |

---

## 5. Next Steps to Complete the Installation

The next agent or the user can choose either of the following two quick paths:

### Path 1: Re-flash the MicroSD Card (Recommended, Cleanest & Easiest)
1. Insert the MicroSD card into the PC using a USB card reader.
2. Open **Rufus**, **BalenaEtcher**, or **Raspberry Pi Imager** (or run `sd_install\prepare_sd_card.bat` as Administrator).
3. Select `c:\Users\leona\Code\A33 Linux\sd_install\a33_debian12_sdcard.img.gz` (or `.img`).
4. Flash the card.
5. Insert the card into the tablet's TF slot and power on!

### Path 2: In-Place Patching of the Existing SD Card
If the user's SD card is already formatted and partitioned from earlier, only the U-Boot bootloader at offset 8KB needs to be updated:
- In WSL / Linux:
  ```bash
  sudo dd if="/mnt/c/Users/leona/Code/A33 Linux/sd_install/u-boot-sunxi-with-spl.bin" of=/dev/sdX bs=1024 seek=8 conv=notrunc,fsync
  ```
  *(replace `/dev/sdX` with the SD card device node)*
- Also ensure `sd_install/boot.scr` is copied into Partition 1 (`BOOT`).

### Verification Once Booted:
1. Boot messages and systemd log will scroll directly on the **1024x600 LCD screen**.
2. If USB OTG is connected to PC, a serial terminal opens on **COM22** (baud 115200, login: `root`, with the password you set in build_rootfs.sh (ROOT_PASSWORD)).
3. To expand the root partition to full card size:
   ```bash
   parted /dev/mmcblk0 resizepart 2 100%
   resize2fs /dev/mmcblk0p2
   ```
