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
print("[✓] PMIC Rails & 32kHz Clock locked.")

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
print("[✓] Hardware lines asserted (PL06, PL11, PL08).")

# 4. Bit-bang I2C on PB03 (SCL) and PB02 (SDA)
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
base_pio = 0x800
# Pull-ups on PB2 and PB3
pull = (struct.unpack('<I', pio[base_pio+0x44:base_pio+0x48])[0] & ~0x000000f0) | 0x00000050
pio[base_pio+0x44:base_pio+0x48] = struct.pack('<I', pull)

# Mux PG0..PG5 to MMC1 (function 2) with pull-ups
pio[0x8d8:0x8dc] = struct.pack('<I', 0x77222222)
pio[0x8f4:0x8f8] = struct.pack('<I', 0x00000555)

# CCU MMC1 ungate & 400kHz
pio[0x60:0x64] = struct.pack('<I', struct.unpack('<I', pio[0x60:0x64])[0] | (1 << 9))
pio[0x2c0:0x2c4] = struct.pack('<I', struct.unpack('<I', pio[0x2c0:0x2c4])[0] | (1 << 9))
pio[0x8c:0x90] = struct.pack('<I', 0x8022020e)

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
    (0x3f, 0x0000),
    (0x06, 0x0101), (0x07, 0x0101), (0x08, 0x0101), (0x09, 0x0101),
    (0x0A, 0x002C), (0x0D, 0x0507), (0x0E, 0x2300), (0x0F, 0x5689),
    (0x10, 0x0f78), (0x11, 0x0602), (0x13, 0x0652), (0x14, 0x8886),
    (0x15, 0x0990), (0x16, 0x049f), (0x17, 0x0990), (0x18, 0x049F),
    (0x19, 0x3C01), (0x1C, 0x0934), (0x1D, 0xFF00), (0x1F, 0x0300),
    (0x20, 0x06E4), (0x21, 0x0ACF), (0x22, 0x24DC), (0x23, 0x23FF),
    (0x24, 0x00FC), (0x26, 0x004F), (0x27, 0x171D), (0x28, 0x031D),
    (0x2A, 0x2860), (0x2B, 0x0800), (0x32, 0x8a08),
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
print("[✓] RDA5990 Silicon Power-Up & Wakeup Sequence Complete!")

# 5. SDIO Probe
print("\n" + "=" * 65)
print("  PROBING SDIO BUS (CMD5 Inquiry & Voltage)")
print("=" * 65)

mmc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c10000)
def mr(off): return struct.unpack('<I', mmc[off:off+4])[0]
def mw(off, val): mmc[off:off+4] = struct.pack('<I', val)

# Controller Soft Reset
mw(0x00, 0x7)
time.sleep(0.01)
mw(0x00, 0x110)
mw(0x08, 0xffffffff) # Max timeout
mw(0x0c, 0)          # 1-bit
mw(0x04, 0x00010000) # Enable card clock
mw(0x18, 0x80202000) # Clock update
time.sleep(0.01)

def send_cmd(cmd_idx, arg, resp_type=0, init_seq=False):
    mw(0x38, 0xffffffff)
    mw(0x1c, arg)
    val = 0x80000000 | (cmd_idx & 0x3f)
    if init_seq: val |= (1 << 15)
    if resp_type != 0: val |= (1 << 6)
    mw(0x18, val)
    t0 = time.time()
    while time.time() - t0 < 0.3:
        st = mr(0x38)
        if st & 0x100: return False, st, 0
        if st & 0x004: return True, st, mr(0x20)
        time.sleep(0.001)
    return False, mr(0x38), 0

# Send 80 clocks (CMD0 with SEND_INIT_SEQUENCE)
send_cmd(0, 0, resp_type=0, init_seq=True)
time.sleep(0.02)

# Send CMD5 Inquiry (arg=0)
ok5, r5, resp5 = send_cmd(5, 0x00000000, resp_type=4)
print(f"  [>] CMD5 Inquiry (arg=0x00000000): ok={ok5}, RINTR=0x{r5:08x}, RESP0=0x{resp5:08x}")

# Send CMD5 Voltage (3.3V, arg=0x00ff8000)
ok5_v, r5_v, resp5_v = send_cmd(5, 0x00ff8000, resp_type=4)
print(f"  [>] CMD5 Voltage (arg=0x00ff8000): ok={ok5_v}, RINTR=0x{r5_v:08x}, RESP0=0x{resp5_v:08x}")

if ok5 or ok5_v or resp5 != 0 or resp5_v != 0:
    print("\n" + "*" * 65)
    print("  🎉🎉🎉 THE RDA5990 CHIP ANSWERED CMD5 ON SDIO! 🎉🎉🎉")
    print(f"  RESP0 OCR = 0x{resp5_v if resp5_v else resp5:08x}")
    print("*" * 65)
else:
    print("\n[-] SDIO CMD5 still timed out.")

mmc.close()
pio.close()
os.close(fd_mem)
