import os
import mmap
import struct
import time

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
rsb_page = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f03000)
base = 0x400

def read_u32(off):
    return struct.unpack('<I', rsb_page[base+off:base+off+4])[0]

def write_u32(off, val):
    rsb_page[base+off:base+off+4] = struct.pack('<I', val)

RTADDR = 0x2d

def rsb_read_reg(reg):
    write_u32(0x10, reg)
    write_u32(0x30, RTADDR << 16)
    write_u32(0x2c, 0x8b) # RD8
    write_u32(0x00, 0x80) # START_TRANS
    t0 = time.time()
    while time.time() - t0 < 0.1:
        st = read_u32(0x0c)
        if st & 0x1:
            write_u32(0x0c, st)
            return read_u32(0x1c) & 0xff
        if st & 0x2:
            write_u32(0x0c, st)
            return None
        time.sleep(0.001)
    return None

def rsb_write_reg(reg, val):
    write_u32(0x10, reg)
    write_u32(0x1c, val)
    write_u32(0x30, RTADDR << 16)
    write_u32(0x2c, 0x4e) # WR8
    write_u32(0x00, 0x80) # START_TRANS
    t0 = time.time()
    while time.time() - t0 < 0.1:
        st = read_u32(0x0c)
        if st & 0x1:
            write_u32(0x0c, st)
            return True
        if st & 0x2:
            write_u32(0x0c, st)
            return False
        time.sleep(0.001)
    return False

print("=== Setting all LDOs to 3.3V (0x1a) ===")
# Set voltages: 0x1a = 3.3V (700mV + 26*100mV = 3300mV)
for reg, name in [(0x15, "DLDO1"), (0x16, "DLDO2"), (0x17, "DLDO3"), (0x18, "DLDO4"),
                  (0x19, "ELDO1"), (0x1b, "ELDO3")]:
    rsb_write_reg(reg, 0x1a)
    print(f"  {name} (0x{reg:02x}) set to 3.3V")

# Enable all outputs in PWR_CTRL2 (0x12): DC1SW, DLDO4, DLDO3, DLDO2, DLDO1, ELDO3, ELDO2, ELDO1
pwr2 = rsb_read_reg(0x12) | 0xff
rsb_write_reg(0x12, pwr2)
print(f"  PWR_CTRL2 (0x12) now: 0x{rsb_read_reg(0x12):02x}")

# Enable ALDO3 and ELDOs in PWR_CTRL3 (0x13)
pwr3 = rsb_read_reg(0x13) | 0x87
rsb_write_reg(0x13, pwr3)
print(f"  PWR_CTRL3 (0x13) now: 0x{rsb_read_reg(0x13):02x}")

rsb_page.close()
os.close(fd)

print("\nWaiting 2 seconds to observe dmesg...")
time.sleep(2)
lines = os.popen("dmesg | tail -n 5").read().strip().split("\n")
for l in lines:
    print("  dmesg:", l)
