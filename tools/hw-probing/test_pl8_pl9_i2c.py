import mmap
import os
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 1. Ensure RTC 32kHz clock fanout is ON
rtc = mmap.mmap(fd_mem, 4096, offset=0x01f00000)
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()

# 2. RSB: Ensure DLDO1, DLDO2 are 3.3V and ON
rsb_page = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f03000)
base = 0x400
def write_u32(off, val): rsb_page[base+off:base+off+4] = struct.pack('<I', val)
def read_u32(off): return struct.unpack('<I', rsb_page[base+off:base+off+4])[0]
RTADDR = 0x2d
def rsb_write_reg(reg, val):
    write_u32(0x10, reg); write_u32(0x1c, val); write_u32(0x30, RTADDR << 16)
    write_u32(0x2c, 0x4e); write_u32(0x00, 0x80)
    t0 = time.time()
    while time.time() - t0 < 0.1:
        st = read_u32(0x0c)
        if st & 0x1: write_u32(0x0c, st); return True
        if st & 0x2: write_u32(0x0c, st); return False
        time.sleep(0.001)
    return False

rsb_write_reg(0x15, 0x1a) # DLDO1 3.3V
rsb_write_reg(0x16, 0x1a) # DLDO2 3.3V
rsb_write_reg(0x12, 0xff)
rsb_page.close()

# 3. Port L mmap
rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base = 0xc00

def r32(off): return struct.unpack('<I', rpio[base + off:base + off + 4])[0]
def w32(off, val): rpio[base + off:base + off + 4] = struct.pack('<I', val)

# Configure pull-ups for PL8 and PL9
pull = r32(0x1c) | (1 << 16) | (1 << 18)
w32(0x1c, pull)

# Power and reset pins: PL2, PL3, PL4, PL5, PL6, PL7, PL10, PL11 = Output HIGH
cfg0 = 0x11111122 # PL0/1=2(RSB), PL2..7=1(out)
w32(0x00, cfg0)

cfg1 = r32(0x04)
cfg1 = (cfg1 & ~(0x7 << 8))  | (1 << 8)  # PL10 out
cfg1 = (cfg1 & ~(0x7 << 12)) | (1 << 12) # PL11 out
w32(0x04, cfg1)

dat = r32(0x10) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 6) | (1 << 7) | (1 << 10) | (1 << 11)
w32(0x10, dat)

# I2C Bit-Bang on PL8 (SCL) and PL9 (SDA)
def scl_high():
    c = r32(0x04) & ~(0x7 << 0)
    w32(0x04, c)

def scl_low():
    d = r32(0x10) & ~(1 << 8)
    w32(0x10, d)
    c = (r32(0x04) & ~(0x7 << 0)) | (1 << 0)
    w32(0x04, c)

def sda_high():
    c = r32(0x04) & ~(0x7 << 4)
    w32(0x04, c)

def sda_low():
    d = r32(0x10) & ~(1 << 9)
    w32(0x10, d)
    c = (r32(0x04) & ~(0x7 << 4)) | (1 << 4)
    w32(0x04, c)

def sda_read():
    return bool(r32(0x10) & (1 << 9))

def i2c_delay():
    for _ in range(50): pass

def i2c_start():
    sda_high(); scl_high(); i2c_delay(); sda_low(); i2c_delay(); scl_low(); i2c_delay()

def i2c_stop():
    sda_low(); i2c_delay(); scl_high(); i2c_delay(); sda_high(); i2c_delay()

def i2c_write_byte(b):
    for i in range(8):
        if b & (0x80 >> i): sda_high()
        else: sda_low()
        i2c_delay(); scl_high(); i2c_delay(); scl_low(); i2c_delay()
    sda_high(); i2c_delay(); scl_high(); i2c_delay()
    ack = not sda_read()
    scl_low(); i2c_delay()
    return ack

print("=== Scanning PL8(SCL) / PL9(SDA) I2C with PL02-PL11 HIGH ===")
scl_high(); sda_high(); time.sleep(0.01)

acks = []
for addr in range(0x08, 0x78):
    i2c_start()
    ack = i2c_write_byte((addr << 1) | 0)
    i2c_stop()
    if ack:
        acks.append(hex(addr))
        print(f"  [+] Found ACK at 0x{addr:02x}!")

print("PL8/PL9 Scan Complete! Found addresses:", acks)

rpio.close()
os.close(fd_mem)
