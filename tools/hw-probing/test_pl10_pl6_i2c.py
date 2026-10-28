import mmap
import os
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# Port L: 0x01f02c00
# CFG0: 0x00
# CFG1: 0x04
# DAT:  0x10
# PULL: 0x1c

rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base = 0xc00

def r32(off):
    return struct.unpack('<I', rpio[base + off:base + off + 4])[0]

def w32(off, val):
    rpio[base + off:base + off + 4] = struct.pack('<I', val)

# SCL on PL10 (CFG1 bits [10:8])
# SDA on PL06 (CFG0 bits [26:24])

# Pull up on PL6 and PL10
# PULL (0x1c): PL6 is bits [13:12], PL10 is bits [21:20]
pull = r32(0x1c) | (1 << 12) | (1 << 20)
w32(0x1c, pull)

def scl_high():
    c = r32(0x04) & ~(0x7 << 8) # in
    w32(0x04, c)

def scl_low():
    d = r32(0x10) & ~(1 << 10)
    w32(0x10, d)
    c = (r32(0x04) & ~(0x7 << 8)) | (1 << 8) # out
    w32(0x04, c)

def sda_high():
    c = r32(0x00) & ~(0x7 << 24) # in
    w32(0x00, c)

def sda_low():
    d = r32(0x10) & ~(1 << 6)
    w32(0x10, d)
    c = (r32(0x00) & ~(0x7 << 24)) | (1 << 24) # out
    w32(0x00, c)

def sda_read():
    return bool(r32(0x10) & (1 << 6))

def i2c_delay():
    for _ in range(100):
        pass

def i2c_start():
    sda_high()
    scl_high()
    i2c_delay()
    sda_low()
    i2c_delay()
    scl_low()
    i2c_delay()

def i2c_stop():
    sda_low()
    i2c_delay()
    scl_high()
    i2c_delay()
    sda_high()
    i2c_delay()

def i2c_write_byte(b):
    for i in range(8):
        if b & (0x80 >> i):
            sda_high()
        else:
            sda_low()
        i2c_delay()
        scl_high()
        i2c_delay()
        scl_low()
        i2c_delay()
    # Read ACK
    sda_high()
    i2c_delay()
    scl_high()
    i2c_delay()
    ack = not sda_read()
    scl_low()
    i2c_delay()
    return ack

print("=== Testing I2C on PL10(SCL) and PL06(SDA) ===")
scl_high()
sda_high()
time.sleep(0.01)

acks = []
for addr in range(0x08, 0x78):
    i2c_start()
    ack = i2c_write_byte((addr << 1) | 0)
    i2c_stop()
    if ack:
        acks.append(hex(addr))
        print(f"  [+] Found ACK at 0x{addr:02x}!")

print(f"PL10/PL06 Scan Results: {acks}")

rpio.close()
os.close(fd_mem)
