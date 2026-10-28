import mmap
import os
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# PIO base: 0x01c20800
# Port B:
# CFG0: 0x24
# DAT:  0x34
# PULL0: 0x40

pio = mmap.mmap(fd_mem, 4096, offset=0x01c20000)
base = 0x800

def r32(off):
    return struct.unpack('<I', pio[base + off:base + off + 4])[0]

def w32(off, val):
    pio[base + off:base + off + 4] = struct.pack('<I', val)

cfg0 = r32(0x24)
dat  = r32(0x34)
pull = r32(0x40)
print(f"Port B CFG0=0x{cfg0:08x}, DAT=0x{dat:08x}, PULL0=0x{pull:08x}")
print(f"  PB2: cfg={hex((cfg0 >> 8) & 0x7)}, dat={bool(dat & (1 << 2))}")
print(f"  PB3: cfg={hex((cfg0 >> 12) & 0x7)}, dat={bool(dat & (1 << 3))}")

# Pull up PB2 and PB3
# PULL0: 2 bits per pin. PB2 is bits [5:4], PB3 is bits [7:6]
pull |= (1 << 4) | (1 << 6) # Pull up
w32(0x40, pull)

# Bit-bang I2C functions on PB2 (SCL) and PB3 (SDA)
# Driving low: CFG=out (1), DAT=0
# Releasing high: CFG=in (0)

def scl_high():
    c = r32(0x24) & ~(0x7 << 8) # in
    w32(0x24, c)

def scl_low():
    d = r32(0x34) & ~(1 << 2)
    w32(0x34, d)
    c = (r32(0x24) & ~(0x7 << 8)) | (1 << 8) # out
    w32(0x24, c)

def sda_high():
    c = r32(0x24) & ~(0x7 << 12) # in
    w32(0x24, c)

def sda_low():
    d = r32(0x34) & ~(1 << 3)
    w32(0x34, d)
    c = (r32(0x24) & ~(0x7 << 12)) | (1 << 12) # out
    w32(0x24, c)

def sda_read():
    return bool(r32(0x34) & (1 << 3))

def i2c_delay():
    for _ in range(50):
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

print("\n=== Testing I2C on PB2(SCL) and PB3(SDA) ===")
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

print(f"PB2/PB3 Scan Results: {acks}")

pio.close()
os.close(fd_mem)
