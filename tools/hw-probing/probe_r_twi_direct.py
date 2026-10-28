import mmap
import os
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

def r32(mm, off):
    return struct.unpack('<I', mm[off:off+4])[0]

def w32(mm, off, val):
    mm[off:off+4] = struct.pack('<I', val)

# 1. PRCM APB0 clock gating & reset for R_TWI (0x01f01400)
prcm = mmap.mmap(fd_mem, 4096, offset=0x01f01000)
base_prcm = 0x400

# APB0 Gating is at 0x28, Reset is at 0xb0
gate = r32(prcm, base_prcm + 0x28)
rst  = r32(prcm, base_prcm + 0xb0)
gate |= (1 << 6)
rst  |= (1 << 6)
w32(prcm, base_prcm + 0x28, gate)
w32(prcm, base_prcm + 0xb0, rst)
prcm.close()

# 2. Port L: Ensure PL6=1, PL8=1, PL11=1 (chip powered)
rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base_l = 0xc00
cfg0 = r32(rpio, base_l)
cfg1 = r32(rpio, base_l + 4)
dat  = r32(rpio, base_l + 0x10)

cfg0 = (cfg0 & ~(0x7 << 24)) | (1 << 24) # PL6 out
cfg1 = (cfg1 & ~(0x7 << 0))  | (1 << 0)  # PL8 out
cfg1 = (cfg1 & ~(0x7 << 12)) | (1 << 12) # PL11 out
w32(rpio, base_l, cfg0)
w32(rpio, base_l + 4, cfg1)

dat |= (1 << 6) | (1 << 8) | (1 << 10) | (1 << 11)
w32(rpio, base_l + 0x10, dat)
rpio.close()

# 3. R_TWI Controller (0x01f02400)
twi = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base_twi = 0x400

# Reset TWI
w32(twi, base_twi + 0x18, 1) # TWI_SRST
time.sleep(0.01)

# CCR: 100kHz
w32(twi, base_twi + 0x14, 0x12)

# Enable TWI
w32(twi, base_twi + 0x0c, (1 << 6))
time.sleep(0.01)

def twi_wait_int():
    t0 = time.time()
    while time.time() - t0 < 0.05:
        c = r32(twi, base_twi + 0x0c)
        if c & (1 << 3): # INT_FLAG
            st = r32(twi, base_twi + 0x10)
            return st
        time.sleep(0.0001)
    return None

def twi_probe_addr(addr):
    # Send START
    w32(twi, base_twi + 0x0c, (1 << 6) | (1 << 5) | (1 << 3))
    s = twi_wait_int()
    if s != 0x08 and s != 0x10:
        w32(twi, base_twi + 0x0c, (1 << 6) | (1 << 4) | (1 << 3)) # STOP
        return False, s
    
    # Send Slave Address + WR
    w32(twi, base_twi + 0x08, (addr << 1) | 0)
    w32(twi, base_twi + 0x0c, (1 << 6) | (1 << 3)) # Clear int to send
    s = twi_wait_int()
    
    # Send STOP
    w32(twi, base_twi + 0x0c, (1 << 6) | (1 << 4) | (1 << 3))
    
    if s == 0x18: # SLA+W ACK
        return True, s
    return False, s

print("\n--- Probing R_TWI (0x01f02400) on PL0/PL1 ---")
acks = []
for a in range(0x08, 0x78):
    ack, st = twi_probe_addr(a)
    st_str = f"0x{st:02x}" if st is not None else "TIMEOUT"
    if ack:
        acks.append(hex(a))
        print(f"  [+] Found ACK at 0x{a:02x}! (status={st_str})")
    elif a in [0x13, 0x14, 0x15, 0x16, 0x34, 0x68]:
        print(f"  Addr 0x{a:02x}: ACK={ack} (status={st_str})")

print(f"\nR_TWI Probe Results: {acks}")

twi.close()
os.close(fd_mem)
