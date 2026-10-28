#!/usr/bin/env python3
import os
import mmap
import struct
import time

print("=======================================================")
print("  TESTING ACTIVE-LOW PMOS POWER GATE ON GPIO0/1 & PL02 ")
print("=======================================================")

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# RSB setup
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

# Ensure main rails are ON
rsb_w(0x10, 0xff) # DCDC1..5 ON
rsb_w(0x12, 0xff) # DLDO1..4, ELDO ON
rsb_w(0x15, 0x1a) # DLDO1 3.3V
rsb_w(0x16, 0x1a) # DLDO2 3.3V

# RTC 32k ON
rtc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc[0x00:0x04] = struct.pack('<I', 0x00008001)
rtc.close()

# Port G MMC1
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
pio[0x8d8:0x8dc] = struct.pack('<I', 0x77222222)
pio[0x8f4:0x8f8] = struct.pack('<I', 0x00000555)
pio[0x60:0x64] = struct.pack('<I', struct.unpack('<I', pio[0x60:0x64])[0] | (1 << 9))
pio[0x2c0:0x2c4] = struct.pack('<I', struct.unpack('<I', pio[0x2c0:0x2c4])[0] | (1 << 9))
pio[0x8c:0x90] = struct.pack('<I', 0x8022020e) # 400kHz

# Port L
rpio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f02000)
base_l = 0xc00
cfg0 = (struct.unpack('<I', rpio[base_l:base_l+4])[0] & 0x000000ff) | 0x11111100
cfg1 = (struct.unpack('<I', rpio[base_l+4:base_l+8])[0] & 0xffff0000) | 0x00001111
rpio[base_l:base_l+4] = struct.pack('<I', cfg0)
rpio[base_l+4:base_l+8] = struct.pack('<I', cfg1)

# MMC1 controller
mmc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c10000)
def mr(off): return struct.unpack('<I', mmc[off:off+4])[0]
def mw(off, val): mmc[off:off+4] = struct.pack('<I', val)

def reset_and_send_cmd5():
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
    # CMD0 with init seq (80 clocks)
    mw(0x38, 0xffffffff)
    mw(0x1c, 0)
    mw(0x18, 0x80008000)
    time.sleep(0.02)
    # CMD5 inquiry
    mw(0x38, 0xffffffff)
    mw(0x1c, 0)
    mw(0x18, 0x80000045)
    t0 = time.time()
    while time.time() - t0 < 0.2:
        rintr = mr(0x38)
        if rintr & 0x100: return False, rintr, 0
        if rintr & 0x004: return True, rintr, mr(0x20)
        time.sleep(0.001)
    return False, mr(0x38), 0

# Test combinations of GPIO0, GPIO1, and PL02
combos = [
    # (name, reg90, reg92, pl_dat)
    ("GPIO0=LOW (PMOS ON), GPIO1=LDO 3.3V, PL2=HIGH", 0x00, 0x03, 0x0ffc),
    ("GPIO0=LOW (PMOS ON), GPIO1=LOW (PMOS ON), PL2=HIGH", 0x00, 0x00, 0x0ffc),
    ("GPIO0=LOW (PMOS ON), GPIO1=LOW (PMOS ON), PL2=LOW", 0x00, 0x00, 0x0ff8),
    ("GPIO0=LDO 3.3V, GPIO1=LOW (PMOS ON), PL2=HIGH", 0x03, 0x00, 0x0ffc),
    ("GPIO0=LDO 3.3V, GPIO1=LDO 3.3V, PL2=LOW", 0x03, 0x03, 0x0ff8),
    ("GPIO0=LDO 3.3V, GPIO1=LDO 3.3V, PL2=HIGH, PL3=LOW", 0x03, 0x03, 0x0ff4),
    ("GPIO0=LOW, GPIO1=LOW, PL2=HIGH, PL3=LOW", 0x00, 0x00, 0x0ff4),
    ("GPIO0=LOW, GPIO1=LOW, PL2=HIGH, PL4=LOW", 0x00, 0x00, 0x0fec),
]

for label, g0, g1, pldat in combos:
    rsb_w(0x90, g0)
    rsb_w(0x92, g1)
    rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', pldat)
    time.sleep(0.05)
    ok, rintr, resp0 = reset_and_send_cmd5()
    print(f"[{'SUCCESS' if ok or resp0 else 'FAIL'}] {label}")
    print(f"      RINTR=0x{rintr:08x}, RESP0=0x{resp0:08x}")
    if ok or resp0:
        print("\n🎉🎉🎉 SDIO RESPONSE RECEIVED! 🎉🎉🎉\n")
        break

# Restore
rsb_w(0x90, 0x03)
rsb_w(0x92, 0x03)
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x0ffc)

mmc.close()
pio.close()
rpio.close()
rsb_page.close()
os.close(fd_mem)
