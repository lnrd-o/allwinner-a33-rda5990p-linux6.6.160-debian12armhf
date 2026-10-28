import os
import mmap
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

print("=== Complete Cold Hardware Power-Cycle of RDA5990 ===")

# Step 1: Discharge all rails and pins
print("[1] Driving all Port G and Port L pins to 0V (GND) to eliminate phantom power...")
pio = mmap.mmap(fd_mem, 4096, offset=0x01c20000)
# PG0-PG5 as output LOW
pio[0x8d8:0x8dc] = struct.pack('<I', 0x77111111) # output
pio[0x8e8:0x8ec] = struct.pack('<I', 0x00000000) # drive 0V
pio[0x8f4:0x8f8] = struct.pack('<I', 0x00000000) # no pull-up

rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base_l = 0xc00
# PL2..PL11 as output LOW
rpio[base_l:base_l+4] = struct.pack('<I', 0x11111122)
rpio[base_l+4:base_l+8] = struct.pack('<I', 0x00001111)
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000000) # drive 0V
rpio[base_l+0x1c:base_l+0x20] = struct.pack('<I', 0x00000000) # no pull-up

# Step 2: Turn off 32kHz fanout
print("[2] Gating RTC 32kHz clock fanout...")
rtc = mmap.mmap(fd_mem, 4096, offset=0x01f00000)
rtc[0x60:0x64] = struct.pack('<I', 0)

# Step 3: Turn off DLDO1 and DLDO2 on AXP223
print("[3] Cutting DLDO1 and DLDO2 power rails to 0V...")
rsb_page = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f03000)
base_rsb = 0x400
def write_u32(off, val): rsb_page[base_rsb+off:base_rsb+off+4] = struct.pack('<I', val)
def read_u32(off): return struct.unpack('<I', rsb_page[base_rsb+off:base_rsb+off+4])[0]
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
def rsb_read_reg(reg):
    write_u32(0x10, reg); write_u32(0x30, RTADDR << 16); write_u32(0x2c, 0x8b); write_u32(0x00, 0x80)
    t0 = time.time()
    while time.time() - t0 < 0.1:
        st = read_u32(0x0c)
        if st & 0x1: write_u32(0x0c, st); return read_u32(0x1c) & 0xff
        if st & 0x2: write_u32(0x0c, st); return None
        time.sleep(0.001)
    return None

pwr2 = rsb_read_reg(0x12)
rsb_write_reg(0x12, pwr2 & ~(0x30)) # Disable DLDO1 and DLDO2

print("[4] Waiting 500ms for all decoupling capacitors to fully discharge...")
time.sleep(0.5)

# Step 4: Power up sequence
print("[5] Re-enabling 32.768 kHz RTC clock...")
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()
time.sleep(0.02)

print("[6] Powering DLDO1 and DLDO2 to 3.3V...")
rsb_write_reg(0x15, 0x1a) # 3.3V
rsb_write_reg(0x16, 0x1a) # 3.3V
rsb_write_reg(0x12, pwr2 | 0x30)
rsb_page.close()
time.sleep(0.05) # 50ms stabilization delay

print("[7] Deasserting RESET and CHIP_EN (Driving PL2..PL11 HIGH)...")
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000ffc)
rpio.close()
time.sleep(0.1) # 100ms for crystal oscillator lock

print("[8] Configuring Port G MMC1 SDIO bus...")
pio[0x8d8:0x8dc] = struct.pack('<I', 0x77222222) # func 2 (MMC1)
pio[0x8f4:0x8f8] = struct.pack('<I', 0x00000555) # pull-up
# CCU clocks
pio[0x60:0x64] = struct.pack('<I', struct.unpack('<I', pio[0x60:0x64])[0] | (1 << 9))
pio[0x2c0:0x2c4] = struct.pack('<I', struct.unpack('<I', pio[0x2c0:0x2c4])[0] | (1 << 9))
pio[0x8c:0x90] = struct.pack('<I', 0x8022020e) # 400kHz
pio.close()

# Step 5: Test SDIO CMD5
mmc = mmap.mmap(fd_mem, 4096, offset=0x01c10000)
def mr32(off): return struct.unpack('<I', mmc[off:off+4])[0]
def mw32(off, val): mmc[off:off+4] = struct.pack('<I', val)

mw32(0x00, 0x7) # Soft reset
t0 = time.time()
while time.time() - t0 < 0.1:
    if (mr32(0x00) & 0x7) == 0: break
    time.sleep(0.001)

mw32(0x00, 0x110)
mw32(0x08, 0xffffffff)
mw32(0x0c, 0)
mw32(0x04, 0x00010000)
mw32(0x18, 0x80202000)
t0 = time.time()
while time.time() - t0 < 0.2:
    if not (mr32(0x18) & 0x80000000): break
    time.sleep(0.001)

def send_cmd(opcode, arg, resp_type=0, init_seq=False):
    mw32(0x38, 0xffffffff)
    mw32(0x1c, arg)
    cmd_val = 0x80000000 | (opcode & 0x3f)
    if init_seq: cmd_val |= (1 << 15)
    if resp_type != 0: cmd_val |= (1 << 6)
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

print("[9] Sending 74 clocks initialization sequence (CMD0)...")
r0, _ = send_cmd(0, 0, init_seq=True)
time.sleep(0.02)

print("[10] Sending CMD5 (arg=0x00000000)...")
r5_0, o5_0 = send_cmd(5, 0x00000000, resp_type=4)
print(f"  CMD5 arg=0:      RINTR=0x{r5_0:08x}, RESP0=0x{o5_0:08x}, TIMEOUT={bool(r5_0 & 0x100)}")

print("[11] Sending CMD5 (arg=0x00ff8000)...")
r5_1, o5_1 = send_cmd(5, 0x00ff8000, resp_type=4)
print(f"  CMD5 arg=3.3V:   RINTR=0x{r5_1:08x}, RESP0=0x{o5_1:08x}, TIMEOUT={bool(r5_1 & 0x100)}")

if not (r5_0 & 0x100) or not (r5_1 & 0x100):
    print(f"\n🎉🎉🎉 SUCCESS! RDA5990 ENUMERATED! OCR = 0x{o5_1:08x} 🎉🎉🎉")

mmc.close()
os.close(fd_mem)
