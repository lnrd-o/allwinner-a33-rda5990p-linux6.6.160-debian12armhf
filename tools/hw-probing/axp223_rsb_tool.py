import os
import mmap
import struct
import time

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
# Page aligned: 0x01f03000, base=0x400
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
        st = read_u32(0x0c) # INTS
        if st & 0x1: # TRANS_OVER
            write_u32(0x0c, st) # clear
            data = read_u32(0x1c) & 0xff
            return data
        if st & 0x2: # TRANS_ERR
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

print("=== AXP223 PMIC Register Scan over RSB ===")
chip_id = rsb_read_reg(0x03)
print(f"AXP223 Chip ID (Reg 0x03): 0x{chip_id:02x}" if chip_id is not None else "Failed to read AXP223 Chip ID")

for reg, name in [(0x10, "PWR_CTRL1"), (0x12, "PWR_CTRL2"), (0x13, "PWR_CTRL3"),
                  (0x15, "DLDO1_VOL"), (0x16, "DLDO2_VOL"), (0x17, "DLDO3_VOL"), (0x18, "DLDO4_VOL"),
                  (0x19, "ELDO1_VOL"), (0x1a, "ELDO2_VOL"), (0x1b, "ELDO3_VOL"),
                  (0x90, "GPIO0_CTL"), (0x91, "GPIO0_VOL"), (0x92, "GPIO1_CTL"), (0x93, "GPIO1_VOL"),
                  (0x94, "GPIO2_CTL"), (0x95, "GPIO3_CTL")]:
    v = rsb_read_reg(reg)
    v_str = f"0x{v:02x} ({v:08b})" if v is not None else "ERR"
    print(f"  Reg 0x{reg:02x} ({name:<10}): {v_str}")

rsb_page.close()
os.close(fd)
