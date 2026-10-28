#!/usr/bin/env python3
# rda5990-wake.py - power and wake the RDA5990P Wi-Fi/BT combo chip (A33 Q8 tablet, ET_F900_V1.6)
# Sequence (verified on hardware, WLAN version reg 0x21 = 0x0045 -> "verE" RF tables):
#   1. RTC 32.768 kHz fanout (LOSC_OUT) on, internal RC oscillator
#   2. AXP223 rails DLDO1/DLDO2 = 3.3 V (direct RSB), PL06/PL11 (and PL02-04) high, PL08 reset released
#   3. Vendor I2C wake-up, bit-banged on PB2 (SDA) / PB3 (SCL), slave 0x14
# After this the kernel's periodic mmc1 rescan finds the SDIO card (5449:0145) and rda5890 binds.
# Must run on every boot (the chip has no persistent state).
import os, sys, time, mmap, struct

print("=" * 65)
print("  RDA5990 I2C SILICON WAKEUP & SDIO ENUMERATION PROBE")
print("=" * 65)

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 1. 32kHz Clock
rtc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)
rtc[0x00:0x04] = struct.pack('<I', (0x16aa << 16) | (1 << 15))
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()

# 2. PMIC Rails
rsb = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f03000)
def rsb_w(reg, val):
    rsb[0x410:0x414] = struct.pack('<I', reg); rsb[0x41c:0x420] = struct.pack('<I', val)
    rsb[0x430:0x434] = struct.pack('<I', 0x2d << 16); rsb[0x42c:0x430] = struct.pack('<I', 0x4e)
    rsb[0x400:0x404] = struct.pack('<I', 0x80)
    t0 = time.time()
    while time.time() - t0 < 0.05:
        st = struct.unpack('<I', rsb[0x40c:0x410])[0]
        if st & 0x1: rsb[0x40c:0x410] = struct.pack('<I', st); return True
        if st & 0x2: rsb[0x40c:0x410] = struct.pack('<I', st); return False
        time.sleep(0.001)
    return False

rsb_w(0x10, 0xff)
rsb_w(0x12, 0xff)
rsb_w(0x15, 0x1a) # DLDO1 = 3.3V
rsb_w(0x16, 0x1a) # DLDO2 = 3.3V
rsb_w(0x90, 0x03); rsb_w(0x91, 0x1a)
rsb_w(0x92, 0x03); rsb_w(0x93, 0x1a)
rsb.close()
print("[OK] PMIC Rails & 32kHz Clock locked.")

# 3. Port L Pins
rpio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f02000)
base_l = 0xc00
rpio[base_l:base_l+4] = struct.pack('<I', 0x11111100)
rpio[base_l+4:base_l+8] = struct.pack('<I', 0x00001111)

# Cold discharge
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0)
time.sleep(0.1)

# Assert Enables (PL06, PL11, PL02, PL03, PL04)
en_mask = (1 << 6) | (1 << 11) | (1 << 2) | (1 << 3) | (1 << 4)
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', en_mask)
time.sleep(0.05)

# Release Reset (PL08)
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', en_mask | (1 << 8))
time.sleep(0.1)
rpio.close()
print("[OK] Hardware lines asserted (PL06, PL11, PL08).")

# 4. Bit-bang I2C on PB03 (SCL) and PB02 (SDA)
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
base_pio = 0x800
# Pull-ups on PB2 and PB3
pull = (struct.unpack('<I', pio[base_pio+0x44:base_pio+0x48])[0] & ~0x000000f0) | 0x00000050
pio[base_pio+0x44:base_pio+0x48] = struct.pack('<I', pull)

# PB03 = SCL, PB02 = SDA
def set_scl(val):
    cfg = struct.unpack('<I', pio[base_pio+0x24:base_pio+0x28])[0]
    if val:
        cfg = cfg & ~(7 << 12) # PB3 input
        pio[base_pio+0x24:base_pio+0x28] = struct.pack('<I', cfg)
    else:
        dat = struct.unpack('<I', pio[base_pio+0x34:base_pio+0x38])[0] & ~(1 << 3)
        pio[base_pio+0x34:base_pio+0x38] = struct.pack('<I', dat)
        cfg = (cfg & ~(7 << 12)) | (1 << 12) # PB3 output low
        pio[base_pio+0x24:base_pio+0x28] = struct.pack('<I', cfg)

def set_sda(val):
    cfg = struct.unpack('<I', pio[base_pio+0x24:base_pio+0x28])[0]
    if val:
        cfg = cfg & ~(7 << 8) # PB2 input
        pio[base_pio+0x24:base_pio+0x28] = struct.pack('<I', cfg)
    else:
        dat = struct.unpack('<I', pio[base_pio+0x34:base_pio+0x38])[0] & ~(1 << 2)
        pio[base_pio+0x34:base_pio+0x38] = struct.pack('<I', dat)
        cfg = (cfg & ~(7 << 8)) | (1 << 8) # PB2 output low
        pio[base_pio+0x24:base_pio+0x28] = struct.pack('<I', cfg)

def get_sda():
    return (struct.unpack('<I', pio[base_pio+0x34:base_pio+0x38])[0] >> 2) & 1

def i2c_d(): time.sleep(0.00002)

def i2c_start():
    set_sda(1); set_scl(1); i2c_d()
    set_sda(0); i2c_d()
    set_scl(0); i2c_d()

def i2c_stop():
    set_sda(0); i2c_d()
    set_scl(1); i2c_d()
    set_sda(1); i2c_d()

def i2c_wb(b):
    for i in range(8):
        bit = (b >> (7 - i)) & 1
        set_sda(bit); i2c_d()
        set_scl(1); i2c_d()
        set_scl(0); i2c_d()
    set_sda(1); i2c_d()
    set_scl(1); i2c_d()
    ack = (get_sda() == 0)
    set_scl(0); i2c_d()
    return ack

def i2c_rb(ack_bit):
    set_sda(1); i2c_d()
    byte = 0
    for i in range(8):
        set_scl(1); i2c_d()
        bit = get_sda()
        byte = (byte << 1) | bit
        set_scl(0); i2c_d()
    set_sda(0 if ack_bit else 1); i2c_d()
    set_scl(1); i2c_d()
    set_scl(0); i2c_d()
    set_sda(1); i2c_d()
    return byte

# 1-addr, 2-data write (RDA vendor protocol)
def rda_i2c_write(addr7, reg8, val16):
    i2c_start()
    if not i2c_wb((addr7 << 1) | 0):
        i2c_stop(); return False
    if not i2c_wb(reg8):
        i2c_stop(); return False
    if not i2c_wb((val16 >> 8) & 0xff):
        i2c_stop(); return False
    if not i2c_wb(val16 & 0xff):
        i2c_stop(); return False
    i2c_stop()
    return True

# 1-addr, 2-data read
def rda_i2c_read(addr7, reg8):
    i2c_start()
    if not i2c_wb((addr7 << 1) | 0):
        i2c_stop(); return None
    if not i2c_wb(reg8):
        i2c_stop(); return None
    # Restart
    i2c_start()
    if not i2c_wb((addr7 << 1) | 1):
        i2c_stop(); return None
    b1 = i2c_rb(ack_bit=True)
    b2 = i2c_rb(ack_bit=False)
    i2c_stop()
    return (b1 << 8) | b2

CHIP_ADDR = 0x14 # RDA_WIFI_RF

print("\n[+] Reading RDA5990 Silicon Identification...")
v_init = rda_i2c_read(CHIP_ADDR, 0x20)
print(f"    RF Reg 0x20: {hex(v_init) if v_init is not None else 'None'}")

# --- Step A: wifi_en_data ---
print("[+] Executing RDA vendor wifi_en_data sequence...")
wifi_en_data = [
    (0x3f, 0x0001), # Page 1
    (0x23, 0x8FA1), # DCDC AVDD higher voltage
    (0x31, 0x0B40), # Power off wifi logic first
    (0x24, 0x80C8), # freq_osc_in
    (0x27, 0x4925), # txswitch
    (0x31, 0x8140), # ENABLE WIFI
    (0x32, 0x0113), # Turn on internal LDO (rden4in_ldoon_wf=1)
    (0x3F, 0x0000), # Page 0
]
for reg, val in wifi_en_data:
    ok = rda_i2c_write(CHIP_ADDR, reg, val)
    if reg == 0x31: time.sleep(0.01)

# --- Step B: rda5990_wf_setup_A2_power ---
print("[+] Setting up A2 Power and reading WLAN version...")
rda_i2c_write(CHIP_ADDR, 0x3f, 0x0001)
a2_val = rda_i2c_read(CHIP_ADDR, 0x22) or 0
a2_val = (a2_val | 0x0200) & ~(1 << 14)
rda_i2c_write(CHIP_ADDR, 0x22, a2_val)
wlan_version = rda_i2c_read(CHIP_ADDR, 0x21) or 0
print(f"    WLAN Version: 0x{wlan_version:04x}")

# --- Step C: wifi_rf_init_data ---
print("[+] Initializing RF synthesizer and baseband PLL...")
wifi_rf_init_data = [
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
for reg, val in wifi_rf_init_data:
    rda_i2c_write(CHIP_ADDR, reg, val)
time.sleep(0.005)

# --- Step D: wifi_dc_cal_data ---
wifi_dc_cal_data = [
    (0x3f, 0x0000),
    (0x30, 0x0248), (0x30, 0x0249),
]
for reg, val in wifi_dc_cal_data:
    rda_i2c_write(CHIP_ADDR, reg, val)
time.sleep(0.05)

# --- Step E: wifi_dig_reset ---
print("[+] Executing digital core reset...")
wifi_dig_reset_data = [
    (0x3F, 0x0001),
    (0x31, 0x8D40),
    (0x31, 0x8F40),
    (0x31, 0x8b40),
    (0x3F, 0x0000),
]
for reg, val in wifi_dig_reset_data:
    rda_i2c_write(CHIP_ADDR, reg, val)
time.sleep(0.05)
print("[OK] RDA5990 Silicon Power-Up & Wakeup Sequence Complete!")


pio.close()
os.close(fd_mem)
