import os
import mmap
import struct
import time

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

# 3. Port L setup
rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base_l = 0xc00
# Output on PL2..PL11
rpio[base_l:base_l+4] = struct.pack('<I', 0x11111122)
rpio[base_l+4:base_l+8] = struct.pack('<I', 0x00001111)

# 4. Port G / CCU MMC1 Setup
pio = mmap.mmap(fd_mem, 4096, offset=0x01c20000)
pio[0x8d8:0x8dc] = struct.pack('<I', 0x77222222)
pio[0x8f4:0x8f8] = struct.pack('<I', 0x00000555)
pio[0x60:0x64] = struct.pack('<I', struct.unpack('<I', pio[0x60:0x64])[0] | (1 << 9))
pio[0x2c0:0x2c4] = struct.pack('<I', struct.unpack('<I', pio[0x2c0:0x2c4])[0] | (1 << 9))
pio[0x8c:0x90] = struct.pack('<I', 0x8022020e) # 400kHz
pio.close()

# 5. MMC1 Controller
mmc = mmap.mmap(fd_mem, 4096, offset=0x01c10000)
def mr32(off): return struct.unpack('<I', mmc[off:off+4])[0]
def mw32(off, val): mmc[off:off+4] = struct.pack('<I', val)

def init_mmc():
    mw32(0x00, 0x7)
    t0 = time.time()
    while time.time() - t0 < 0.1:
        if (mr32(0x00) & 0x7) == 0: break
        time.sleep(0.001)
    mw32(0x00, 0x110)
    mw32(0x08, 0xffffffff)
    mw32(0x0c, 0)
    mw32(0x04, 0x00010000) # clock on
    mw32(0x18, 0x80202000) # update clk
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (mr32(0x18) & 0x80000000): break
        time.sleep(0.001)

def send_cmd(opcode, arg, resp_type=0, init_seq=False):
    mw32(0x38, 0xffffffff)
    mw32(0x1c, arg)
    cmd_val = 0x80000000 | (opcode & 0x3f)
    if init_seq: cmd_val |= (1 << 15)
    if resp_type != 0:
        cmd_val |= (1 << 6)
        if resp_type == 48: cmd_val |= (1 << 8)
    mw32(0x18, cmd_val)
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (mr32(0x18) & 0x80000000): break
        time.sleep(0.001)
    t0 = time.time()
    rintr = 0
    while time.time() - t0 < 0.3:
        rintr = mr32(0x38)
        if rintr & 0x1ff: break
        time.sleep(0.001)
    resp0 = mr32(0x20)
    mw32(0x38, rintr)
    return rintr, resp0

print("=== Systematic Reset Pulse on Each Port L Pin ===")
# Set all PL2..PL11 HIGH first
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000ffc)
time.sleep(0.05)

for pin in range(2, 12):
    # Drive pin LOW
    dat = 0x00000ffc & ~(1 << pin)
    rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', dat)
    time.sleep(0.05) # hold in reset
    
    # Release pin HIGH
    dat |= (1 << pin)
    rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', dat)
    time.sleep(0.05) # wait for PLL
    
    init_mmc()
    r0, _ = send_cmd(0, 0, init_seq=True)
    time.sleep(0.01)
    r5, o5 = send_cmd(5, 0, resp_type=4)
    has_to = bool(r5 & 0x100)
    print(f"PL{pin:02d} Reset Pulse -> CMD5: RINTR=0x{r5:08x}, RESP0=0x{o5:08x}, TIMEOUT={has_to}")
    if not has_to and (r5 & 4):
        print(f"  >>> SUCCESS TRIGGERED BY PL{pin} RESET! OCR=0x{o5:08x} <<<")
        break

# What if a pin is ACTIVE-LOW enable (needs to be LOW to run)?
print("\n=== Testing Each Port L Pin Held LOW ===")
for pin in range(2, 12):
    # Drive pin LOW and keep it LOW
    dat = 0x00000ffc & ~(1 << pin)
    rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', dat)
    time.sleep(0.05)
    
    init_mmc()
    r0, _ = send_cmd(0, 0, init_seq=True)
    time.sleep(0.01)
    r5, o5 = send_cmd(5, 0, resp_type=4)
    has_to = bool(r5 & 0x100)
    if not has_to and (r5 & 4):
        print(f"  >>> SUCCESS WITH PL{pin} HELD LOW! OCR=0x{o5:08x} <<<")
        break
    else:
        # restore HIGH
        rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000ffc)

rpio.close()
mmc.close()
os.close(fd_mem)
