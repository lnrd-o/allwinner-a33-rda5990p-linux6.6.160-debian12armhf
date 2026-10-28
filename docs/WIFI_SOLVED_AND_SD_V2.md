# A33 Tablet (ET_F900_V1.6 / Q8): Wi-Fi solved, SD image v2

Status as of 2026-10-28. This supersedes the Wi-Fi conclusions in `PROGRESS_REPORT.md` and
`DIAGNOSTIC_REPORT_RDA5990_MAINLINE.md`.

## 1. Result

| Item | State |
|---|---|
| RDA5990P enumerates on SDIO (`5449:0145`, mmc1) | Works |
| `rda5890` driver binds, `wlan0` appears | Works |
| Scan (SSID, channel, **dBm**) | Works (verified: phone hotspot, ch 11, about -62 to -81 dBm) |
| WPA2-PSK association + DHCP + internet (apt reached Debian) | Works (verified live, hand-started) |
| LCD dashboard with Wi-Fi state/SSID/dBm/networks | Works (verified live) |
| Automatic at boot (SD image v2) | **Built, not yet booted on the tablet** |
| USB networking / SSH over USB (RNDIS gadget) | **Built into new kernel, not yet tested** |

## 2. What was actually wrong (root causes)

1. **No wake-up on a clean boot.** The chip does not answer SDIO `CMD5` until it is powered, clocked
   and sent the vendor I2C wake-up. Nothing did that, so the kernel's 1 Hz mmc1 rescan always timed
   out (`err=-110`). Earlier "needs I2C" theory was right; the missing piece was doing it at boot.
   Working sequence (`sd_install/overlay/usr/local/sbin/rda5990-wake.py`):
   - RTC `LOSC_OUT` 32.768 kHz on (internal RC oscillator).
   - AXP223 DLDO1/DLDO2 = 3.3 V (direct RSB), PL06 / PL11 (and PL02-04) high, PL08 reset released.
   - Vendor I2C wake-up, **bit-banged on PB2 (SDA) / PB3 (SCL), slave 0x14** (not a hardware TWI
     bus). WLAN version register 0x21 reads 0x0045, so the "verE" RF tables apply.
   - The deployed DTB already has `mmc-pwrseq` removed, so the kernel does not reset the chip.
2. **Scan results discarded by the ported driver.** The firmware returns **60-byte** scan entries;
   the driver's `struct rda5890_bss_descriptor` was 46 bytes, so every reply was rejected
   ("Scan Result len not correct"). Added `u8 fw_extra[14]`.
3. **Stack buffer overflows** in `rda5890_wid.c`: `wid_req[12]` written 16 deep in
   `rda5890_start_scan*`, and `wid_req[14]` written 19 deep in `rda5890_set_scan_timeout` (the
   compiler could drop or reorder those stores). Sizes fixed to 16 and 19.
4. **Scan mode.** `GET_SCAN_FROM_NETWORK_INFO` is now disabled (site-survey scan is used).
5. **Not causes:** the antenna/RF registers (all read back correctly), the crystal-output bit, `0x24`
   oscillator value, SDIO bus timing.

Driver sources fixed in `rda5990_ported/` (originals in `rda5990_ported/orig_before_fix/`):
`rda5890_wid.c`, `rda5890_dev.h`, `rda5890_defs.h`.

## 3. Other findings

- **FEL boot "No ethernet found"**: `boot.scr` loads the initramfs from `0x44000000`, but
  `boot_fel.bat` uploaded `uInitrd` to `0x4B000000`. Upload it to `0x44000000` and trim it to
  `64 + header size` bytes (`uInitrd` has about 47 MB of trailing data that would overwrite U-Boot).
  `boot_fel.bat` itself is **not yet fixed**.
- `test_direct_rda_sdio.py` (and `diag_wifi.py`, `probe_sdio_and_bt.py`) write the MMC1 clock to CCU
  `0x64`; on the A33 it is `0x8c`.
- `sd_install/sun8i-a33-et-q8-v1.6.dtb` was outdated (still had the RTC `clocks` property). It was
  replaced with the current `output/` DTB (old one kept as `.before_v2`).
- The tablet has **no battery-backed clock**: it boots in the past, and apt refuses "not valid yet"
  repositories. `a33-timesync` sets the date from an HTTP header.
- Serial uploads over COM22 stall unless the tablet's echo is off and the host reads while writing
  (`stty -echo` + drain).
- The original working copy of `PROGRESS_REPORT.md` and the stock `wifi-connect.sh` contained a
  Wi-Fi password in plain text; it is redacted here. Never commit real credentials.

## 4. USB networking / SSH over USB

The previous kernel only had `g_serial` (the COM22 console). The new kernel
(`output/zImage_usbnet`, also used by the v2 image) has USB configfs with ACM + RNDIS + ECM + NCM.
`usb-gadget.service` creates one composite gadget: **RNDIS network + ACM serial**.

- Tablet side: `usb0` = `192.168.7.2/24`, systemd-networkd DHCP server hands the PC an address.
- PC side: Windows should bind the in-box RNDIS driver automatically (MS OS descriptors). If not,
  `output/rndis_win11.inf` is the previous workaround. The serial console gets a **new COM number**
  (new USB ID), look in Device Manager.
- SSH: `ssh root@192.168.7.2`. `sshd` is enabled and `PermitRootLogin yes` is set, with the root
  password you set when building the rootfs (`ROOT_PASSWORD` in `scripts/build_rootfs.sh`). Use a
  strong password (`passwd`) or switch to key login, since the same SSH port is also reachable over Wi-Fi.
- If USB networking fails, the LCD dashboard and Wi-Fi/SSH still work, and `output\boot_fel_sd.bat`
  boots the same kernel via FEL with the root filesystem on the SD card.

## 5. Using SD image v2

Build (WSL, root): `sd_install/build_sd_image_v2.sh` (does not touch the v1 script or images).
Output: `sd_install/a33_debian12_sdcard_v2.img` and `.img.gz` (flash with Rufus / BalenaEtcher).

On the SD card, at boot: `usb-gadget` -> `rda5990-wake` (modprobes `rda5890`) -> `a33-wifi`
(wpa_supplicant WEXT + DHCP) -> `a33-timesync`; `wifi-status` + `lcd-dashboard` draw the LCD.

**The v2 overlay stores no Wi-Fi password**, but the base rootfs still contains the old, now-unused
home-network config (`/etc/wpa_supplicant/wpa_supplicant.conf`, plus `/usr/local/bin/wifi-connect.sh`),
because it is copied from `/root/a33-build/debian-rootfs`. The old `wifi-connect` and generic
`wpa_supplicant` services are disabled in the image. Delete those two files from the rootfs if you
want the card free of credentials before sharing it. After first boot, from the console or SSH:

    a33-wifi-setup "Your SSID"      # asks for the password, input hidden

then it reconnects at every boot. Brightness is set to the maximum (10/10).

## 6. Installing to the internal storage (NAND)

Not recommended right now:

- The A33 Q8 tablets use **raw NAND** (Allwinner NAND controller), not eMMC. Nothing like
  `/dev/mmcblk1` exists.
- The current kernel has **no MTD/NAND support at all** (`CONFIG_MTD_RAW_NAND` etc. unset).
- Booting Linux from the NAND would also need U-Boot SPL written in the NAND boot format with the
  right page size / ECC / randomizer, plus UBI/UBIFS. A wrong write can leave the tablet unable to
  boot from NAND and **overwrites the stock Android irreversibly**. The SD card (and FEL recovery)
  keep working either way, because the BROM boots from SD / FEL first.
- A safe first step would be dumping the NAND (read-only) with `sunxi-fel` before any experiment.

## 7. Not verified yet

- SD image v2 booting on the tablet (U-Boot-from-SD path has not been seen to work end to end).
- The USB RNDIS gadget on the PC, and SSH over `usb0`.
- The services starting in the right order on a cold boot (especially `rda5990-wake` vs the mmc1
  rescan), and Wi-Fi reconnecting automatically.
- The 1 Hz `MMC_DEBUG` kernel prints (from the debug instrumentation in `drivers/mmc/core`) still
  spam `dmesg`.
