import os
import mmap
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 1. RTC 32kHz
rtc = mmap.mmap(fd_mem, 4096, offset=0x01f00000)
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()

# 2. Port L: Configure PL2, PL3, PL4, PL5, PL6, PL7, PL8, PL9, PL10, PL11 as OUTPUTS and drive ALL HIGH (1)!
rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base_l = 0xc00

# CFG0: PL0=2 (rsb), PL1=2 (rsb), PL2..PL7 = 1 (output)
# Nibbles: [31:28]=PL7, [27:24]=PL6, [23:20]=PL5, [19:16]=PL4, [15:12]=PL3, [11:8]=PL2, [7:4]=PL1, [3:0]=PL0
# 0x11111122
rpio[base_l:base_l+4] = struct.pack('<I', 0x11111122)

# CFG1: PL8..PL11 = 1 (output)
# 0x00001111
rpio[base_l+4:base_l+8] = struct.pack('<I', 0x00001111)

# Drive ALL PL2..PL11 HIGH!
# Bits 2..11 = 1 -> 0x00000ffc
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0x00000ffc)
time.sleep(0.05)

dat = struct.unpack('<I', rpio[base_l+0x10:base_l+0x14])[0]
print(f"Port L DAT: 0x{dat:08x} (PL2={bool(dat&(1<<2))}, PL3={bool(dat&(1<<3))}, PL6={bool(dat&(1<<6))}, PL11={bool(dat&(1<<11))})")

# 3. Port G SDIO Pins (PG0-PG5 Function 2 = MMC1)
pio = mmap.mmap(fd_mem, 4096, offset=0x01c20000)
pio[0x8d8:0x8dc] = struct.pack('<I', 0x77222222)
pio[0x8f4:0x8f8] = struct.pack('<I', 0x00000555)

# Ungate MMC1 bus clock & reset
pio[0x60:0x64] = struct.pack('<I', struct.unpack('<I', pio[0x60:0x64])[0] | (1 << 9))
pio[0x2c0:0x2c4] = struct.pack('<I', struct.unpack('<I', pio[0x2c0:0x2c4])[0] | (1 << 9))

# MMC1 Module Clock: 400kHz (0x8022020e)
pio[0x8c:0x90] = struct.pack('<I', 0x8022020e)
pio.close()

# 4. MMC1 Controller (0x01c10000)
mmc = mmap.mmap(fd_mem, 4096, offset=0x01c10000)

def r32(off):
    return struct.unpack('<I', mmc[off:off+4])[0]

def w32(off, val):
    mmc[off:off+4] = struct.pack('<I', val)

# Reset MMC controller
w32(0x00, 0x7)
t0 = time.time()
while time.time() - t0 < 0.1:
    if (r32(0x00) & 0x7) == 0: break
    time.sleep(0.001)

w32(0x00, 0x110)
w32(0x08, 0xffffffff)
w32(0x0c, 0)
w32(0x04, 0x00010000) # clock on
w32(0x18, 0x80202000) # update clk
t0 = time.time()
while time.time() - t0 < 0.2:
    if not (r32(0x18) & 0x80000000): break
    time.sleep(0.001)

def send_cmd(opcode, arg, resp_type=0, init_seq=False):
    w32(0x38, 0xffffffff)
    w32(0x1c, arg)
    cmd_val = 0x80000000 | (opcode & 0x3f)
    if init_seq:
        cmd_val |= (1 << 15)
    if resp_type != 0:
        cmd_val |= (1 << 6)
        if resp_type == 48:
            cmd_val |= (1 << 8)
    w32(0x18, cmd_val)
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (r32(0x18) & 0x80000000): break
        time.sleep(0.001)
    t0 = time.time()
    rintr = 0
    while time.time() - t0 < 0.3:
        rintr = r32(0x38)
        if rintr & 0x1ff: break
        time.sleep(0.001)
    resp0 = r32(0x20)
    w32(0x38, rintr)
    return rintr, resp0

print("\n--- Sending CMD0 and CMD5 with PL02 & PL03 HIGH ---")
send_cmd(0, 0, init_seq=True)
time.sleep(0.05)

rintr5, resp5 = send_cmd(5, 0, resp_type=4)
print(f"CMD5 (arg=0): RINTR=0x{rintr5:08x}, RESP0=0x{resp5:08x} (DONE={bool(rintr5&4)}, TO={bool(rintr5&0x100)})")

if rintr5 & 4 and not (rintr5 & 0x100):
    print(f"\n🎉>>> SUCCESS! CARD RESPONDED TO CMD5! OCR=0x{resp5:08x} <<<🎉")

mmc.close()
rpio.close()
os.close(fd_mem)
