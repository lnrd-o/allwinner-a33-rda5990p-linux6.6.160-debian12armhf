# allwinner-a33-rda5990p-linux6.6.160-debian12armhf

Mainline **Linux 6.6.160 LTS + Debian 12 (armhf)** on an **Allwinner A33 Q8 tablet** (`ET_F900_V1.6`,
1024x600 RGB LCD, 1 GB DDR3, AXP223 PMIC) with working **RDA5990P Wi-Fi** on SDIO.

Verified on hardware: SDIO enumeration, `wlan0`, scanning with dBm, WPA2-PSK association, DHCP and
internet access, plus an LCD status dashboard. Not yet verified: the automatic-at-boot SD image
(v2) and USB gadget networking (see [docs/WIFI_SOLVED_AND_SD_V2.md](docs/WIFI_SOLVED_AND_SD_V2.md)).

## What was wrong with the Wi-Fi (short version)

1. The chip answers SDIO only after power, a 32.768 kHz clock and a vendor **I2C wake-up**
   (bit-banged on PB2/PB3, slave `0x14`). Nothing did that on a clean boot.
   See [`overlay/usr/local/sbin/rda5990-wake.py`](overlay/usr/local/sbin/rda5990-wake.py).
2. The ported `rda5890` driver rejected every scan result: the firmware sends 60-byte entries, the
   struct was 46 bytes.
3. Two stack buffers in `rda5890_wid.c` were too small (undefined behaviour).

Fixes: [`driver/`](driver/) (originals in `driver/orig_before_fix/`).

## Layout

| Path | Content |
|---|---|
| `docs/` | Findings and how-to; `docs/history/` has the earlier (partly superseded) reports |
| `driver/rda5990_ported/` | Fixed `rda5890` SDIO Wi-Fi driver (GPL, builds as an out-of-tree module) |
| `overlay/` | Files copied into the rootfs: wake-up script, systemd services, USB gadget, Wi-Fi helper, LCD dashboard |
| `scripts/` | Kernel / rootfs / U-Boot / SD image build scripts (`scripts/sd/build_sd_image_v2.sh`) |
| `boot/` | U-Boot boot script source and FEL boot helpers |
| `dts/`, `kernel/`, `u-boot/` | Device tree, kernel config (with USB gadget networking), local patches |
| `tools/hw-probing/` | The register-level probing scripts used during bring-up (`/dev/mem`, I2C, SDIO) |
| `tools/serial/` | Helpers for driving the tablet's USB serial console |

No binaries or disk images are committed (kernel, DTB, U-Boot, SD image): build them with the scripts.

## Quick start (build the SD image)

    # WSL / Linux, as root; needs the kernel tree, U-Boot and the Debian rootfs described in scripts/
    ROOT_PASSWORD='choose-one' ./scripts/build_rootfs.sh
    ./scripts/build_kernel.sh
    ./scripts/sd/build_sd_image_v2.sh

After first boot set your Wi-Fi once (the password is hidden and never stored in the image):

    a33-wifi-setup "Your SSID"

## Notes and warnings

- Credentials are intentionally not in this repository. Set `ROOT_PASSWORD` yourself; the rootfs
  allows root SSH, so use a strong password or key login.
- Many paths in the scripts are specific to the original working machine (WSL and a Windows
  project folder); adjust them.
- Installing to the internal NAND is **not** supported: the kernel has no NAND driver and it would
  erase Android. See section 6 of the main doc.
- Licensed GPL-2.0 (see `LICENSE`). The `rda5890` driver derives from the vendor SDIO driver and
  declares `MODULE_LICENSE("GPL")`.
