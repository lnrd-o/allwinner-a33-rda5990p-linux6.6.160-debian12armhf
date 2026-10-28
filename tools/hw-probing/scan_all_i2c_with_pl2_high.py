import os
import mmap
import struct
import time
import fcntl

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 1. RTC 32kHz
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
rsb_write_reg(0x12, 0xff) # All LDOs ON
rsb_page.close()

# 3. Port L: Drive ALL PL2..PL11 HIGH!
rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base_l = 0xc00
# Output on PL2..PL11
rpio[base_l:base_l+4] = struct.pack('<I', 0x11111122)
rpio[base_l+4:base_l+8] = struct.pack('<I', 0x00001111)

# Drive PL2 LOW first for 50ms, then HIGH!
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000ff8)
time.sleep(0.05)
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000ffc)
time.sleep(0.05)
print("Port L DAT now:", hex(struct.unpack('<I', rpio[base_l+0x10:base_l+0x14])[0]))

# 4. Scan Linux /dev/i2c-0, 1, 2
print("\n=== Scanning /dev/i2c-0, 1, 2 ===")
for b in [0, 1, 2]:
    dev = f"/dev/i2c-{b}"
    if not os.path.exists(dev): continue
    fd = os.open(dev, os.O_RDWR)
    wr_acks = []
    rd_acks = []
    for a in range(0x08, 0x78):
        try:
            fcntl.ioctl(fd, 0x0703, a)
            os.write(fd, bytes([0]))
            wr_acks.append(hex(a))
        except: pass
        try:
            fcntl.ioctl(fd, 0x0703, a)
            os.read(fd, 1)
            rd_acks.append(hex(a))
        except: pass
    os.close(fd)
    print(f"  {dev} WR: {wr_acks}, RD: {rd_acks}")

rpio.close()
os.close(fd_mem)
