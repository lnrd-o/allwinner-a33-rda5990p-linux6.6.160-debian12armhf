import os
import mmap
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
mmc = mmap.mmap(fd_mem, 4096, offset=0x01c10000)

def r32(off):
    return struct.unpack('<I', mmc[off:off+4])[0]

def w32(off, val):
    mmc[off:off+4] = struct.pack('<I', val)

def send_cmd(opcode, arg, resp_type=0, init_seq=False):
    w32(0x38, 0xffffffff) # clear RINTR
    w32(0x1c, arg)
    cmd_val = 0x80000000 | (opcode & 0x3f)
    if init_seq:
        cmd_val |= (1 << 15)
    if resp_type != 0:
        cmd_val |= (1 << 6) # RESP_EXPIRE
        if resp_type == 136:
            cmd_val |= (1 << 7)
        if resp_type == 48: # with CRC
            cmd_val |= (1 << 8) # CHECK_RESPONSE_CRC
    w32(0x18, cmd_val)
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (r32(0x18) & 0x80000000):
            break
        time.sleep(0.001)
    
    t0 = time.time()
    rintr = 0
    while time.time() - t0 < 0.3:
        rintr = r32(0x38)
        if rintr & 0x1ff:
            break
        time.sleep(0.001)
    resp0 = r32(0x20)
    w32(0x38, rintr)
    return rintr, resp0

print("=== Testing All Standard SD/SDIO/MMC Commands on MMC1 ===")

# Send CMD0 with 74 clocks
r, resp = send_cmd(0, 0, resp_type=0, init_seq=True)
print(f"CMD0 (Init):   RINTR=0x{r:08x} (DONE={bool(r&4)})")
time.sleep(0.01)

# CMD8 (Interface condition)
r, resp = send_cmd(8, 0x000001aa, resp_type=48)
print(f"CMD8 (Cond):   RINTR=0x{r:08x}, RESP0=0x{resp:08x} (DONE={bool(r&4)}, TO={bool(r&0x100)})")
time.sleep(0.01)

# CMD5 (SDIO Inquiry)
r, resp = send_cmd(5, 0x00000000, resp_type=4)
print(f"CMD5 (SDIO 0): RINTR=0x{r:08x}, RESP0=0x{resp:08x} (DONE={bool(r&4)}, TO={bool(r&0x100)})")
time.sleep(0.01)

# CMD5 (SDIO 3.3V)
r, resp = send_cmd(5, 0x00ff8000, resp_type=4)
print(f"CMD5 (SDIO 1): RINTR=0x{r:08x}, RESP0=0x{resp:08x} (DONE={bool(r&4)}, TO={bool(r&0x100)})")
time.sleep(0.01)

# CMD52 (CCCR Read Reg 0)
r, resp = send_cmd(52, 0x00000000, resp_type=48)
print(f"CMD52 (CCCR0): RINTR=0x{r:08x}, RESP0=0x{resp:08x} (DONE={bool(r&4)}, TO={bool(r&0x100)})")
time.sleep(0.01)

# CMD1 (MMC SEND_OP_COND)
r, resp = send_cmd(1, 0x40ff8000, resp_type=4)
print(f"CMD1 (MMC):    RINTR=0x{r:08x}, RESP0=0x{resp:08x} (DONE={bool(r&4)}, TO={bool(r&0x100)})")

mmc.close()
os.close(fd_mem)
