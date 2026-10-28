import os
import mmap
import struct
import time

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 1. RSB to control AXP223
rsb_page = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f03000)
base = 0x400
def write_u32(off, val):
    rsb_page[base+off:base+off+4] = struct.pack('<I', val)
def read_u32(off):
    return struct.unpack('<I', rsb_page[base+off:base+off+4])[0]
RTADDR = 0x2d

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

def rsb_read_reg(reg):
    write_u32(0x10, reg)
    write_u32(0x30, RTADDR << 16)
    write_u32(0x2c, 0x8b) # RD8
    write_u32(0x00, 0x80)
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

# Ensure DLDO1, DLDO2 are enabled and at 3.3V
rsb_write_reg(0x15, 0x1a) # DLDO1 3.3V
rsb_write_reg(0x16, 0x1a) # DLDO2 3.3V
rsb_write_reg(0x12, rsb_read_reg(0x12) | 0x30)

print(f"Current Reg 0x90 (GPIO0): 0x{rsb_read_reg(0x90):02x}")
print(f"Current Reg 0x92 (GPIO1): 0x{rsb_read_reg(0x92):02x}")

# 2. Clock Fanout: RTC 32kHz
rtc = mmap.mmap(fd, 4096, offset=0x01f00000)
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()

# 3. Port L setup
rpio = mmap.mmap(fd, 4096, offset=0x01f02000)
base_l = 0xc00
# Output on PL2..PL11
rpio[base_l:base_l+4] = struct.pack('<I', 0x11111122)
rpio[base_l+4:base_l+8] = struct.pack('<I', 0x00001111)

# Hold PL2 (RESET) LOW first
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000ff8)

# 4. MMC1 Setup
pio = mmap.mmap(fd, 4096, offset=0x01c20000)
pio[0x8d8:0x8dc] = struct.pack('<I', 0x77222222)
pio[0x8f4:0x8f8] = struct.pack('<I', 0x00000555)
pio[0x60:0x64] = struct.pack('<I', struct.unpack('<I', pio[0x60:0x64])[0] | (1 << 9))
pio[0x2c0:0x2c4] = struct.pack('<I', struct.unpack('<I', pio[0x2c0:0x2c4])[0] | (1 << 9))
pio[0x8c:0x90] = struct.pack('<I', 0x8022020e) # 400kHz
pio.close()

mmc = mmap.mmap(fd, 4096, offset=0x01c10000)
def mr32(off):
    return struct.unpack('<I', mmc[off:off+4])[0]
def mw32(off, val):
    mmc[off:off+4] = struct.pack('<I', val)

def init_mmc():
    mw32(0x00, 0x7)
    t0 = time.time()
    while time.time() - t0 < 0.1:
        if (mr32(0x00) & 0x7) == 0:
            break
        time.sleep(0.001)
    mw32(0x00, 0x110)
    mw32(0x08, 0xffffffff)
    mw32(0x0c, 0)
    mw32(0x04, 0x00010000)
    mw32(0x18, 0x80202000)
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (mr32(0x18) & 0x80000000):
            break
        time.sleep(0.001)

def send_cmd(opcode, arg, resp_type=0, init_seq=False):
    mw32(0x38, 0xffffffff)
    mw32(0x1c, arg)
    cmd_val = 0x80000000 | (opcode & 0x3f)
    if init_seq:
        cmd_val |= (1 << 15)
    if resp_type != 0:
        cmd_val |= (1 << 6)
        if resp_type == 48:
            cmd_val |= (1 << 8)
    mw32(0x18, cmd_val)
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (mr32(0x18) & 0x80000000):
            break
        time.sleep(0.001)
    t0 = time.time()
    rintr = 0
    while time.time() - t0 < 0.3:
        rintr = mr32(0x38)
        if rintr & 0x1ff:
            break
        time.sleep(0.001)
    resp0 = mr32(0x20)
    mw32(0x38, rintr)
    return rintr, resp0

# Test combinations of GPIO0 and GPIO1
for g0 in [0x00, 0x01, 0x03]:
    for g1 in [0x00, 0x01, 0x03]:
        print(f"=== Testing AXP223 Reg 0x90=0x{g0:02x}, Reg 0x92=0x{g1:02x} ===")
        rsb_write_reg(0x90, g0)
        rsb_write_reg(0x92, g1)
        time.sleep(0.05)
        
        # Pulse RESET: PL2 LOW -> HIGH
        rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000ff8) # PL2 LOW
        time.sleep(0.02)
        rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000ffc) # PL2 HIGH
        time.sleep(0.05)
        
        init_mmc()
        r0, _ = send_cmd(0, 0, init_seq=True)
        time.sleep(0.01)
        r5, o5 = send_cmd(5, 0, resp_type=4)
        print(f"  CMD5: RINTR=0x{r0:08x}/0x{r5:08x}, RESP0=0x{o5:08x}, TIMEOUT={bool(r5 & 0x100)}")
        if r5 & 4 and not (r5 & 0x100):
            print(f"  >>> SUCCESS WITH GPIO0=0x{g0:02x}, GPIO1=0x{g1:02x}! OCR=0x{o5:08x} <<<")
            break

rsb_page.close()
rpio.close()
mmc.close()
os.close(fd)
