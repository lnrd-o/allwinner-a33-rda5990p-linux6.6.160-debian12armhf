#!/usr/bin/env python3
import os
import mmap
import struct
import time

print("==================================================")
print("  TEST RDA5990 I2C WITH ACTIVE 32kHz RC CLOCK     ")
print("==================================================")

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 1. RTC: Ensure Internal 32kHz RC oscillator + LOSC_OUT
rtc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)
rtc[0x00:0x04] = struct.pack('<I', (0x16aa << 16) | (1 << 15)) # Key + Internal RC
rtc[0x60:0x64] = struct.pack('<I', 1) # LOSC_OUT
rtc.close()

# 2. RSB: Ensure DLDO1 & DLDO2 are 3.3V
rsb_page = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f03000)
base_rsb = 0x400
def wr_rsb(off, val): rsb_page[base_rsb+off:base_rsb+off+4] = struct.pack('<I', val)
def rd_rsb(off): return struct.unpack('<I', rsb_page[base_rsb+off:base_rsb+off+4])[0]
RTADDR = 0x2d
def rsb_set(reg, val):
    wr_rsb(0x10, reg); wr_rsb(0x1c, val); wr_rsb(0x30, RTADDR << 16)
    wr_rsb(0x2c, 0x4e); wr_rsb(0x00, 0x80)
    t0 = time.time()
    while time.time() - t0 < 0.1:
        st = rd_rsb(0x0c)
        if st & 0x1: wr_rsb(0x0c, st); return True
        if st & 0x2: wr_rsb(0x0c, st); return False
        time.sleep(0.001)
    return False

rsb_set(0x10, 0xff)
rsb_set(0x12, 0xff)
rsb_set(0x15, 0x1a) # DLDO1 3.3V
rsb_set(0x16, 0x1a) # DLDO2 3.3V
rsb_set(0x90, 0x03); rsb_set(0x91, 0x1a)
rsb_set(0x92, 0x03); rsb_set(0x93, 0x1a)
rsb_page.close()

# 3. Port L: Release PL2..PL11 HIGH
rpio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f02000)
base_l = 0xc00
cfg0 = (struct.unpack('<I', rpio[base_l:base_l+4])[0] & 0x000000ff) | 0x11111100
cfg1 = (struct.unpack('<I', rpio[base_l+4:base_l+8])[0] & 0xffff0000) | 0x00001111
rpio[base_l:base_l+4] = struct.pack('<I', cfg0)
rpio[base_l+4:base_l+8] = struct.pack('<I', cfg1)
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000ffc)
rpio.close()

# 4. Port B: PB2 (SCL) and PB3 (SDA) bit-bang I2C
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
base_b = 0x800

def r32_pio(off): return struct.unpack('<I', pio[base_b+off:base_b+off+4])[0]
def w32_pio(off, val): pio[base_b+off:base_b+off+4] = struct.pack('<I', val)

# Enable pull-ups on PB2 and PB3
pull = r32_pio(0x40) | (1 << 4) | (1 << 6)
w32_pio(0x40, pull)

def scl_high():
    c = r32_pio(0x24) & ~(0x7 << 8) # in
    w32_pio(0x24, c)

def scl_low():
    d = r32_pio(0x34) & ~(1 << 2)
    w32_pio(0x34, d)
    c = (r32_pio(0x24) & ~(0x7 << 8)) | (1 << 8) # out
    w32_pio(0x24, c)

def sda_high():
    c = r32_pio(0x24) & ~(0x7 << 12) # in
    w32_pio(0x24, c)

def sda_low():
    d = r32_pio(0x34) & ~(1 << 3)
    w32_pio(0x34, d)
    c = (r32_pio(0x24) & ~(0x7 << 12)) | (1 << 12) # out
    w32_pio(0x24, c)

def sda_read():
    return bool(r32_pio(0x34) & (1 << 3))

def scl_read():
    return bool(r32_pio(0x34) & (1 << 2))

def i2c_delay():
    time.sleep(0.00001)

def i2c_start():
    sda_high(); scl_high(); i2c_delay()
    sda_low(); i2c_delay()
    scl_low(); i2c_delay()

def i2c_stop():
    sda_low(); i2c_delay()
    scl_high(); i2c_delay()
    sda_high(); i2c_delay()

def i2c_write_byte(byte):
    for i in range(8):
        if byte & (0x80 >> i):
            sda_high()
        else:
            sda_low()
        i2c_delay(); scl_high(); i2c_delay(); scl_low(); i2c_delay()
    # Read ACK
    sda_high(); i2c_delay(); scl_high(); i2c_delay()
    ack = not sda_read()
    scl_low(); i2c_delay()
    return ack

print(f"Pin states: PB2(SCL)={scl_read()}, PB3(SDA)={sda_read()}")

# Scan all 7-bit addresses (0x08..0x77)
print("Scanning I2C on PB02/PB03 with active 32kHz clock...")
found = []
for addr in range(0x08, 0x78):
    i2c_start()
    ack_wr = i2c_write_byte(addr << 1)
    i2c_stop()
    if ack_wr: found.append(f"0x{addr:02x}(WR)")
    i2c_start()
    ack_rd = i2c_write_byte((addr << 1) | 1)
    i2c_stop()
    if ack_rd: found.append(f"0x{addr:02x}(RD)")

print(f"Discovery on PB02/PB03: {found}")

pio.close()
os.close(fd_mem)
