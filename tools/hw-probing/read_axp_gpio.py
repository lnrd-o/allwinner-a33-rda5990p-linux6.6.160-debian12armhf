import mmap, os, struct, time

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
rsb = mmap.mmap(fd, 4096, offset=0x01f03000)
base = 0x400

def w32(off, val):
    rsb[base+off:base+off+4] = struct.pack('<I', val)

def r32(off):
    return struct.unpack('<I', rsb[base+off:base+off+4])[0]

RTADDR = 0x2d

def rsb_read_reg(reg):
    w32(0x10, reg)
    w32(0x30, RTADDR << 16)
    w32(0x2c, 0x8b)
    w32(0x00, 0x80)
    t0 = time.time()
    while time.time() - t0 < 0.1:
        st = r32(0x0c)
        if st & 0x1:
            w32(0x0c, st)
            return r32(0x1c) & 0xff
        if st & 0x2:
            w32(0x0c, st)
            return None
        time.sleep(0.001)
    return None

regs = [0x10, 0x12, 0x13, 0x15, 0x16, 0x17, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x90, 0x91, 0x92, 0x93]
for r in regs:
    val = rsb_read_reg(r)
    val_str = f"0x{val:02x}" if val is not None else "None"
    print(f"AXP Reg 0x{r:02x} = {val_str}")

rsb.close()
os.close(fd)
