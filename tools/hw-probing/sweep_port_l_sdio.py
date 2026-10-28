#!/usr/bin/env python3
import os
import mmap
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# Open Port L
rpio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f02000)
base_l = 0xc00
cfg0 = (struct.unpack('<I', rpio[base_l:base_l+4])[0] & 0x000000ff) | 0x11111100
cfg1 = (struct.unpack('<I', rpio[base_l+4:base_l+8])[0] & 0xffff0000) | 0x00001111
rpio[base_l:base_l+4] = struct.pack('<I', cfg0)
rpio[base_l+4:base_l+8] = struct.pack('<I', cfg1)

def set_pl(val):
    # val is bitmask for PL0..PL11
    # Preserve PL0, PL1 (RSB)
    cur = struct.unpack('<I', rpio[base_l+0x10:base_l+0x14])[0] & 0x3
    rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', (val & ~0x3) | cur)

# MMC1 setup
mmc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c10000)
def mr(off): return struct.unpack('<I', mmc[off:off+4])[0]
def mw(off, val): mmc[off:off+4] = struct.pack('<I', val)

def test_cmd5():
    # CMD0 (80 clocks)
    mw(0x38, 0xffffffff)
    mw(0x1c, 0)
    mw(0x18, 0x80008000)
    time.sleep(0.01)
    # CMD5
    mw(0x38, 0xffffffff)
    mw(0x1c, 0)
    mw(0x18, 0x80000045)
    t0 = time.time()
    while time.time() - t0 < 0.05:
        rintr = mr(0x38)
        if rintr & 0x100: return False, rintr, 0
        if rintr & 0x004: return True, rintr, mr(0x20)
        time.sleep(0.001)
    return False, mr(0x38), 0

print("=== SWEEPING PORT L PINS FOR SDIO ACK ===")

# Test 1: Each pin pulled LOW while all other PL pins are HIGH
for pin in range(2, 12):
    mask = 0x0ffc & ~(1 << pin)
    set_pl(mask)
    time.sleep(0.02)
    ok, rintr, resp0 = test_cmd5()
    print(f"PL{pin}=LOW (others HIGH): ok={ok}, RINTR=0x{rintr:08x}, RESP0=0x{resp0:08x}")
    if ok or resp0:
        print(f"🎉 FOUND WORKING PIN: PL{pin}=LOW enables SDIO! 🎉")
        break

# Test 2: Each pin driven HIGH while all other PL pins are LOW
print("\n--- Testing each pin HIGH while others LOW ---")
for pin in range(2, 12):
    mask = (1 << pin)
    set_pl(mask)
    time.sleep(0.02)
    ok, rintr, resp0 = test_cmd5()
    print(f"PL{pin}=HIGH (others LOW): ok={ok}, RINTR=0x{rintr:08x}, RESP0=0x{resp0:08x}")
    if ok or resp0:
        print(f"🎉 FOUND WORKING PIN: PL{pin}=HIGH enables SDIO! 🎉")
        break

# Restore all HIGH
set_pl(0x0ffc)

mmc.close()
rpio.close()
os.close(fd_mem)
