#!/usr/bin/env python3
import os
import fcntl
import struct
import time

def i2c_write(fd, reg, val):
    # reg is 1 byte, val is 2 bytes big-endian
    data = bytes([reg, (val >> 8) & 0xff, val & 0xff])
    os.write(fd, data)

def i2c_read(fd, reg):
    os.write(fd, bytes([reg]))
    buf = os.read(fd, 2)
    return (buf[0] << 8) | buf[1]

# RF Init Table
wifi_rf_init_data_verE = [
    (0x3f, 0x0000), (0x06, 0x0101), (0x07, 0x0101), (0x08, 0x0101), (0x09, 0x0101),
    (0x0a, 0x002c), (0x0d, 0x0507), (0x0e, 0x2300), (0x0f, 0x5689), (0x10, 0x0f78),
    (0x11, 0x0602), (0x13, 0x0652), (0x14, 0x8886), (0x15, 0x0990), (0x16, 0x049f),
    (0x17, 0x0990), (0x18, 0x049f), (0x19, 0x3c01), (0x1c, 0x0934), (0x1d, 0xff00),
    (0x20, 0x06e4), (0x21, 0x0acf), (0x22, 0x24dc), (0x23, 0x23ff), (0x24, 0x00fc),
    (0x26, 0x004f), (0x27, 0x171d), (0x28, 0x031d), (0x2a, 0x2860), (0x2b, 0x0800),
    (0x32, 0x8a08), (0x33, 0x1d02), (0x36, 0x02f4), (0x37, 0x01f4), (0x38, 0x21d4),
    (0x39, 0x25d4), (0x3a, 0x2584), (0x3b, 0x2dc4), (0x3c, 0x2d04), (0x3d, 0x2c02),
    (0x33, 0x1502), (0x1b, 0x0001), (0x30, 0x024d), (0x29, 0xd468), (0x29, 0x1468),
    (0x30, 0x0249), (0x3f, 0x0000)
]

def power_on_rda5990_i2c(bus_num, addr=0x14):
    dev = f'/dev/i2c-{bus_num}'
    print(f"[*] Executing rda_wifi_power_on() on {dev} at slave 0x{addr:02x}...")
    try:
        fd = os.open(dev, os.O_RDWR)
        fcntl.ioctl(fd, 0x0703, addr) # I2C_SLAVE
        
        # 1. wifi_en_data
        print("  1. Writing wifi_en_data...")
        i2c_write(fd, 0x3f, 0x0001)
        i2c_write(fd, 0x23, 0x8fa1)
        i2c_write(fd, 0x31, 0x0b40)
        i2c_write(fd, 0x24, 0x80c8)
        i2c_write(fd, 0x27, 0x4925)
        i2c_write(fd, 0x31, 0x8140) # enable wifi
        time.sleep(0.015)
        i2c_write(fd, 0x32, 0x0113)
        i2c_write(fd, 0x3f, 0x0000)
        
        # 2. rda5990_wf_setup_A2_power
        print("  2. Setting up A2 power...")
        i2c_write(fd, 0x3f, 0x0001)
        a2_val = i2c_read(fd, 0x22)
        print(f"     0xA2 readback: 0x{a2_val:04x}")
        a2_val |= 0x0200
        i2c_write(fd, 0x22, a2_val)
        wlan_ver = i2c_read(fd, 0x21)
        print(f"     WLAN Version: 0x{wlan_ver:04x}")
        i2c_write(fd, 0x3f, 0x0000)
        
        # 3. wifi_rf_init
        print("  3. Initializing RF registers...")
        for r, v in wifi_rf_init_data_verE:
            i2c_write(fd, r, v)
            
        # 4. wifi_dc_cal
        print("  4. Running DC calibration...")
        i2c_write(fd, 0x3f, 0x0000)
        i2c_write(fd, 0x30, 0x0248)
        i2c_write(fd, 0x30, 0x0249)
        time.sleep(0.02)
        
        # 5. wifi_dig_reset
        print("  5. Executing digital reset...")
        i2c_write(fd, 0x3f, 0x0001)
        i2c_write(fd, 0x31, 0x8d40)
        i2c_write(fd, 0x31, 0x8f40)
        i2c_write(fd, 0x31, 0x8b40)
        i2c_write(fd, 0x3f, 0x0000)
        time.sleep(0.02)
        
        os.close(fd)
        print("[+] rda_wifi_power_on() successfully completed!")
        return True
    except Exception as e:
        print(f"[-] Error writing to {dev} at 0x{addr:02x}: {e}")
        try:
            os.close(fd)
        except:
            pass
        return False

def scan_and_wake():
    print("=== Scanning All I2C Adapters for RDA5990 ===")
    found_target = False
    for bus in [0, 1, 2]:
        dev = f'/dev/i2c-{bus}'
        if not os.path.exists(dev):
            continue
        print(f"Checking {dev}...")
        for addr in [0x14, 0x15, 0x13, 0x16]:
            try:
                fd = os.open(dev, os.O_RDWR)
                fcntl.ioctl(fd, 0x0703, addr)
                os.write(fd, bytes([0x3f]))
                val = os.read(fd, 2)
                u16_val = (val[0] << 8) | val[1]
                print(f"[+] FOUND RDA5990 on {dev} at addr 0x{addr:02x} (Reg 0x3f = 0x{u16_val:04x})!")
                os.close(fd)
                power_on_rda5990_i2c(bus, addr)
                found_target = True
                break
            except Exception:
                try:
                    os.close(fd)
                except:
                    pass
        if found_target:
            break
            
    if not found_target:
        print("[-] Target address did not ACK on hardware I2C buses. Trying default on i2c-0...")
        power_on_rda5990_i2c(0, 0x14)

if __name__ == '__main__':
    scan_and_wake()
