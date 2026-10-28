#!/usr/bin/env python3
import os
import mmap
import struct
import time

print("=======================================================")
print("  PRECISE COLD HARDWARE RESET & POWER-CYCLE PROBE      ")
print("=======================================================")

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# Step 1: Open RSB
rsb_page = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f03000)
base_rsb = 0x400

def wr_rsb(off, val): rsb_page[base_rsb+off:base_rsb+off+4] = struct.pack('<I', val)
def rd_rsb(off): return struct.unpack('<I', rsb_page[base_rsb+off:base_rsb+off+4])[0]

RTADDR = 0x2d

def rsb_w(reg, val):
    wr_rsb(0x10, reg); wr_rsb(0x1c, val); wr_rsb(0x30, RTADDR << 16)
    wr_rsb(0x2c, 0x4e); wr_rsb(0x00, 0x80)
    t0 = time.time()
    while time.time() - t0 < 0.1:
        st = rd_rsb(0x0c)
        if st & 0x1: wr_rsb(0x0c, st); return True
        if st & 0x2: wr_rsb(0x0c, st); return False
        time.sleep(0.001)
    return False

def rsb_r(reg):
    wr_rsb(0x10, reg); wr_rsb(0x30, RTADDR << 16); wr_rsb(0x2c, 0x8b); wr_rsb(0x00, 0x80)
    t0 = time.time()
    while time.time() - t0 < 0.1:
        st = rd_rsb(0x0c)
        if st & 0x1: wr_rsb(0x0c, st); return rd_rsb(0x1c) & 0xff
        if st & 0x2: wr_rsb(0x0c, st); return None
        time.sleep(0.001)
    return None

# Step 2: Open PIO (Port G) and R_PIO (Port L)
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
rpio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f02000)
base_l = 0xc00
rtc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)

print("[1] Completely powering down Wi-Fi domain...")

# 1a. Drive Port G (PG0..PG5) and Port L (PL2..PL11) LOW to 0V (no parasitic leakage)
pio[0x8d8:0x8dc] = struct.pack('<I', 0x77111111) # PG0..5 output
pio[0x8e8:0x8ec] = struct.pack('<I', 0x00000000) # drive 0V
pio[0x8f4:0x8f8] = struct.pack('<I', 0x00000000) # no pull

cfg0 = struct.unpack('<I', rpio[base_l:base_l+4])[0]
cfg1 = struct.unpack('<I', rpio[base_l+4:base_l+8])[0]
cfg0 = (cfg0 & 0x000000ff) | 0x11111100 # PL2..7 out
cfg1 = (cfg1 & 0xffff0000) | 0x00001111 # PL8..11 out
rpio[base_l:base_l+4] = struct.pack('<I', cfg0)
rpio[base_l+4:base_l+8] = struct.pack('<I', cfg1)
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000000) # Drive PL2..11 to 0V

# 1b. Keep RTC on internal 32kHz RC oscillator and ensure LOSC_OUT is active
rtc[0x00:0x04] = struct.pack('<I', (0x16aa << 16) | (1 << 15))
rtc[0x60:0x64] = struct.pack('<I', 1)

# 1c. Cut DLDO1 (bit 3), DLDO2 (bit 4), LDO_IO0 (reg 0x90), LDO_IO1 (reg 0x92)
pwr2 = rsb_r(0x12)
rsb_w(0x12, pwr2 & ~(0x18)) # Disable DLDO1 and DLDO2
rsb_w(0x90, 0x00) # LDO_IO0 floating / off
rsb_w(0x92, 0x00) # LDO_IO1 floating / off

print("[2] Discharging caps for 600ms...")
time.sleep(0.6)

print("[3] Powering UP sequence...")
# 3a. Re-enable RTC 32kHz (Internal RC oscillator with security key)
rtc[0x00:0x04] = struct.pack('<I', (0x16aa << 16) | (1 << 15))
rtc[0x60:0x64] = struct.pack('<I', 1)

# 3b. Turn ON DLDO1 & DLDO2 at 3.3V
rsb_w(0x15, 0x1a) # 3.3V
rsb_w(0x16, 0x1a) # 3.3V
rsb_w(0x12, pwr2 | 0x18) # Enable DLDO1 and DLDO2
# 3c. Turn ON LDO_IO0 & LDO_IO1 at 3.3V
rsb_w(0x91, 0x1a)
rsb_w(0x90, 0x03) # LDO mode ON
rsb_w(0x93, 0x1a)
rsb_w(0x92, 0x03)

print("    Voltages applied. Waiting 100ms for power rails to stabilize...")
time.sleep(0.1)

# 3d. Restore Port G to MMC1 (func 2) with pull-ups
pio[0x8d8:0x8dc] = struct.pack('<I', 0x77222222)
pio[0x8f4:0x8f8] = struct.pack('<I', 0x00000555)

# Ungate CCU clocks
pio[0x60:0x64] = struct.pack('<I', struct.unpack('<I', pio[0x60:0x64])[0] | (1 << 9))
pio[0x2c0:0x2c4] = struct.pack('<I', struct.unpack('<I', pio[0x2c0:0x2c4])[0] | (1 << 9))
pio[0x8c:0x90] = struct.pack('<I', 0x8022020e) # 400kHz

# 3e. Release RESET (Drive PL2..PL11 HIGH)
print("[4] Deasserting RESET and waking chip (PL2..PL11 -> HIGH)...")
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000ffc)
time.sleep(0.15) # 150ms for chip internal PLL and crystal to lock

# Step 4: MMC1 Init
mmc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c10000)
def mr(off): return struct.unpack('<I', mmc[off:off+4])[0]
def mw(off, val): mmc[off:off+4] = struct.pack('<I', val)

mw(0x00, 0x7)
t0 = time.time()
while time.time() - t0 < 0.1:
    if (mr(0x00) & 0x7) == 0: break
    time.sleep(0.001)

mw(0x00, 0x110)
mw(0x08, 0xffffffff)
mw(0x0c, 0)
mw(0x04, 0x00010000)
mw(0x18, 0x80202000)
t0 = time.time()
while time.time() - t0 < 0.2:
    if not (mr(0x18) & 0x80000000): break
    time.sleep(0.001)

def cmd(opcode, arg, resp=0, init=False):
    mw(0x38, 0xffffffff)
    mw(0x1c, arg)
    val = 0x80000000 | (opcode & 0x3f)
    if init: val |= (1 << 15)
    if resp: val |= (1 << 6)
    mw(0x18, val)
    t0 = time.time()
    while time.time() - t0 < 0.3:
        rintr = mr(0x38)
        if rintr & 0x100: return False, rintr, 0
        if rintr & 0x004: return True, rintr, mr(0x20)
        time.sleep(0.001)
    return False, mr(0x38), 0

print("[5] Sending 80 initialization clocks (CMD0 with init_seq)...")
ok0, r0, resp0 = cmd(0, 0, init=True)
time.sleep(0.02)

print("[6] Probing SDIO CMD5...")
ok5_0, r5_0, resp5_0 = cmd(5, 0x00000000, resp=4)
print(f"  CMD5 Inquiry (arg=0):    ok={ok5_0}, RINTR=0x{r5_0:08x}, RESP0=0x{resp5_0:08x}")

ok5_v, r5_v, resp5_v = cmd(5, 0x00ff8000, resp=4)
print(f"  CMD5 Voltage (arg=3.3V): ok={ok5_v}, RINTR=0x{r5_v:08x}, RESP0=0x{resp5_v:08x}")

if ok5_0 or ok5_v or resp5_0 != 0 or resp5_v != 0:
    print("\n🎉🎉🎉 SUCCESS! WIRELESS CHIP RESPONDED ON SDIO! 🎉🎉🎉")
else:
    print("\nNo SDIO response on 400kHz. Testing lower frequencies...")
    for n, m, freq_str in [(1, 14, "200kHz"), (2, 14, "100kHz"), (3, 14, "50kHz")]:
        reg_val = 0x80220000 | (n << 8) | m
        pio[0x8c:0x90] = struct.pack('<I', reg_val)
        mw(0x18, 0x80202000)
        time.sleep(0.01)
        ok, r, resp = cmd(5, 0x00000000, resp=4)
        print(f"  CMD5 @ {freq_str}: ok={ok}, RINTR=0x{r:08x}, RESP0=0x{resp:08x}")
        if ok or resp != 0:
            print(f"🎉 SUCCESS AT {freq_str}! 🎉")
            break

mmc.close()
pio.close()
rpio.close()
rtc.close()
rsb_page.close()
os.close(fd_mem)
