#!/usr/bin/env python3
import os
import mmap
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# Open Port B
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
base_b = 0x800
# Save Port B CFG0, DAT, PULL
orig_cfg = struct.unpack('<I', pio[base_b+0x24:base_b+0x28])[0]
orig_dat = struct.unpack('<I', pio[base_b+0x34:base_b+0x38])[0]

# MMC1 setup
mmc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c10000)
def mr(off): return struct.unpack('<I', mmc[off:off+4])[0]
def mw(off, val): mmc[off:off+4] = struct.pack('<I', val)

def test_cmd5():
    mw(0x38, 0xffffffff)
    mw(0x1c, 0)
    mw(0x18, 0x80008000)
    time.sleep(0.01)
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

print("=== SWEEPING PORT B PINS FOR SDIO ACK ===")

# Test PB0, PB1, PB2, PB3, PB7 as output HIGH and LOW
# (Note: PB4 is sdc_det, PB5/PB6 are touchscreen/gsensor int)
for pin in [0, 1, 2, 3, 7]:
    # Configure pin as output
    cfg = orig_cfg & ~(0x7 << (pin * 4))
    cfg |= (1 << (pin * 4)) # output
    pio[base_b+0x24:base_b+0x28] = struct.pack('<I', cfg)
    
    # 1. Drive HIGH
    dat = struct.unpack('<I', pio[base_b+0x34:base_b+0x38])[0] | (1 << pin)
    pio[base_b+0x34:base_b+0x38] = struct.pack('<I', dat)
    time.sleep(0.02)
    ok, rintr, resp0 = test_cmd5()
    print(f"PB{pin}=HIGH: ok={ok}, RINTR=0x{rintr:08x}, RESP0=0x{resp0:08x}")
    if ok or resp0:
        print(f"🎉 FOUND WORKING PIN: PB{pin}=HIGH enables SDIO! 🎉")
        break
        
    # 2. Drive LOW
    dat = struct.unpack('<I', pio[base_b+0x34:base_b+0x38])[0] & ~(1 << pin)
    pio[base_b+0x34:base_b+0x38] = struct.pack('<I', dat)
    time.sleep(0.02)
    ok, rintr, resp0 = test_cmd5()
    print(f"PB{pin}=LOW:  ok={ok}, RINTR=0x{rintr:08x}, RESP0=0x{resp0:08x}")
    if ok or resp0:
        print(f"🎉 FOUND WORKING PIN: PB{pin}=LOW enables SDIO! 🎉")
        break

# Restore Port B
pio[base_b+0x24:base_b+0x28] = struct.pack('<I', orig_cfg)
pio[base_b+0x34:base_b+0x38] = struct.pack('<I', orig_dat)

mmc.close()
pio.close()
os.close(fd_mem)
