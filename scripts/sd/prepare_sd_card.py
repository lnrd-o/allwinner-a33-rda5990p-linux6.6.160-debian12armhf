#!/usr/bin/env python3
"""
==============================================================================
Allwinner A33 Tablet (ET_F900_V1.6 / Q8) Host SD Card Flasher & Helper
Cross-platform helper (Windows / Linux) to safely prepare, flash, and verify
the standalone MicroSD card for autonomous Debian 12 booting.
==============================================================================
"""

import os
import sys
import time
import json
import subprocess
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_FILE = os.path.join(SCRIPT_DIR, "a33_debian12_sdcard.img")
UBOOT_BIN = os.path.join(SCRIPT_DIR, "u-boot-sunxi-with-spl.bin")
BOOT_SCR = os.path.join(SCRIPT_DIR, "boot.scr")
KERNEL_BIN = os.path.join(SCRIPT_DIR, "zImage")
DTB_BIN = os.path.join(SCRIPT_DIR, "sun8i-a33-et-q8-v1.6.dtb")

def is_admin_windows():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def get_windows_disks():
    ps_cmd = (
        "Get-CimInstance Win32_DiskDrive | "
        "Select-Object Index, DeviceID, Model, Size, MediaType, InterfaceType | "
        "ConvertTo-Json"
    )
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
    if not res.stdout.strip():
        return []
    try:
        data = json.loads(res.stdout)
        if isinstance(data, dict):
            data = [data]
        return data
    except Exception as e:
        print(f"Error parsing disk list: {e}")
        return []

def get_linux_disks():
    res = subprocess.run(
        ["lsblk", "-J", "-d", "-o", "NAME,SIZE,TYPE,TRAN,RM,MODEL"],
        capture_output=True, text=True
    )
    if not res.stdout.strip():
        return []
    try:
        data = json.loads(res.stdout)
        return data.get("blockdevices", [])
    except Exception as e:
        print(f"Error parsing lsblk: {e}")
        return []

def flash_image_to_disk_windows(disk_index, img_path):
    device_path = f"\\\\.\\PhysicalDrive{disk_index}"
    img_size = os.path.getsize(img_path)
    
    print(f"\n[*] Preparing to flash {img_path} ({img_size / (1024*1024):.1f} MB)")
    print(f"[*] Target Physical Drive: {device_path}")
    print("[!] Clearing existing partitions using DiskPart...")

    # Clear disk with diskpart script
    dp_script = f"select disk {disk_index}\nclean\nrescan\n"
    dp_file = os.path.join(SCRIPT_DIR, "_temp_clean.txt")
    with open(dp_file, "w") as f:
        f.write(dp_script)
    subprocess.run(["diskpart", "/s", dp_file], check=True)
    try:
        os.remove(dp_file)
    except:
        pass
    time.sleep(2)

    print(f"[*] Writing raw image to {device_path} in 4MB chunks...")
    chunk_size = 4 * 1024 * 1024
    written = 0

    try:
        with open(img_path, "rb") as src, open(device_path, "r+b", buffering=0) as dst:
            while True:
                buf = src.read(chunk_size)
                if not buf:
                    break
                # Pad last chunk to 512-byte sector if needed
                if len(buf) % 512 != 0:
                    pad = 512 - (len(buf) % 512)
                    buf += b'\x00' * pad
                dst.write(buf)
                written += len(buf)
                pct = min(100.0, (written / img_size) * 100)
                sys.stdout.write(f"\r    Progress: [{int(pct // 5) * '#'}{int(20 - pct // 5) * '-'}] {pct:.1f}% ({written // (1024*1024)} MB)")
                sys.stdout.flush()
        print("\n[*] Write completed! Flushing disk caches...")
        time.sleep(1)
        # Rescan diskpart
        subprocess.run(["powershell", "-NoProfile", "-Command", "Update-HostStorageCache"], capture_output=True)
        print("[✓] Flashing finished successfully!")
        return True
    except PermissionError:
        print("\n[-] Error: Access Denied. Make sure to run this script as Administrator!")
        return False
    except Exception as e:
        print(f"\n[-] Error writing to disk: {e}")
        return False

def main():
    print("=" * 68)
    print("   Allwinner A33 Tablet MicroSD Flasher & Deployment Tool   ")
    print("   Board: ET_F900_V1.6 (MID-756 / Q8 layout, 1024x600 LCD)  ")
    print("=" * 68)

    # Check image availability
    if not os.path.isfile(IMG_FILE):
        print(f"[!] Pre-built disk image not found at:\n    {IMG_FILE}")
        print("[*] You can build it using WSL by running 'build_sd_image.sh'.")
    else:
        print(f"[✓] Pre-built disk image available: {IMG_FILE} ({os.path.getsize(IMG_FILE) // (1024*1024)} MB)")

    if sys.platform == "win32":
        if not is_admin_windows():
            print("\n[!] NOTICE: This tool requires Administrator privileges to access raw disks.")
            print("    Please right-click 'prepare_sd_card.bat' and select 'Run as administrator'.")
            input("\nPress Enter to view disk list anyway...")

        disks = get_windows_disks()
        if not disks:
            print("[-] No disk drives detected.")
            return

        print("\nDetected Disks on Windows:")
        print("-" * 68)
        print(f"{'#':<3} {'DeviceID':<22} {'Size (GB)':<12} {'Interface':<12} {'Model'}")
        print("-" * 68)
        
        removable_candidates = []
        for d in disks:
            idx = d.get("Index")
            dev_id = d.get("DeviceID", "")
            size_b = d.get("Size") or 0
            size_gb = f"{size_b / (1024**3):.1f}"
            intf = d.get("InterfaceType", "Unknown")
            model = d.get("Model", "Unknown")
            media = d.get("MediaType", "")
            
            is_usb = (intf.upper() == "USB") or ("removable" in media.lower())
            mark = " [REMOVABLE / SD]" if is_usb else " (Fixed Internal Disk)"
            print(f"{idx:<3} {dev_id:<22} {size_gb + ' GB':<12} {intf:<12} {model}{mark}")
            if is_usb:
                removable_candidates.append(idx)
        print("-" * 68)

        if not removable_candidates:
            print("[!] Note: No USB/Removable drives detected. Please insert your SD card reader.")
            return

        print("\nOptions:")
        print("  1. Flash 'a33_debian12_sdcard.img' directly to an SD Card")
        print("  2. Launch WSL to run full formatting script (prepare_sd_card.sh)")
        print("  3. Exit")

        choice = input("\nSelect option [1-3]: ").strip()
        if choice == "1":
            if not is_admin_windows():
                print("[-] Error: Writing raw disks requires Administrator privileges. Aborting.")
                return
            sel = input(f"Enter Disk # to flash ({removable_candidates}): ").strip()
            try:
                disk_idx = int(sel)
            except ValueError:
                print("[-] Invalid disk number.")
                return

            if disk_idx not in removable_candidates:
                print(f"[!] WARNING: Disk {disk_idx} is NOT marked as removable!")
                confirm = input("Are you ABSOLUTELY sure you want to erase this drive? Type 'YES': ").strip()
                if confirm != "YES":
                    print("Aborted.")
                    return

            confirm = input(f"Type 'yes' to confirm writing image to PhysicalDrive{disk_idx}: ").strip()
            if confirm == "yes":
                flash_image_to_disk_windows(disk_idx, IMG_FILE)
            else:
                print("Aborted.")
        elif choice == "2":
            print("[*] Launching WSL...")
            subprocess.run(["wsl", "-e", "sudo", f"{SCRIPT_DIR.replace('C:', '/mnt/c').replace(os.sep, '/')}/prepare_sd_card.sh"])

    else:
        # Linux / WSL
        if os.geteuid() != 0:
            print("[-] Error: Please run with sudo.")
            return
        disks = get_linux_disks()
        print("\nDetected Block Devices:")
        for d in disks:
            print(f"  /dev/{d['name']}: {d.get('size')} ({d.get('model', 'Generic')})")
        dev = input("\nEnter device to prepare (e.g. /dev/sdb): ").strip()
        if os.path.exists(dev):
            subprocess.run([os.path.join(SCRIPT_DIR, "prepare_sd_card.sh"), dev])

if __name__ == "__main__":
    main()
