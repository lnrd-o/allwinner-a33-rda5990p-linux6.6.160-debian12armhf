import os
import mmap
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# Ensure RTC 32kHz is active
rtc = mmap.mmap(fd_mem, 4096, offset=0x01f00000)
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()

# Port L configuration
rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base_l = 0xc00

# CFG0: PL0=2 (rsb), PL1=2 (rsb), PL2..PL7 = 0 (input)
# 0x00000022
rpio[base_l:base_l+4] = struct.pack('<I', 0x00000022)

# CFG1: PL8..PL11 = 0 (input)
rpio[base_l+4:base_l+8] = struct.pack('<I', 0x00000000)

# Pull-ups on PL2..PL11 (offset 0x1c)
# 2 bits per pin. PL0-1: 0x2, PL2-11: 0x1 (pull-up)
# bits: [23:4] = 0x55555
pull = 0x0055555a
rpio[base_l+0x1c:base_l+0x20] = struct.pack('<I', pull)

time.sleep(0.05)

# Read levels on Port L
dat = struct.unpack('<I', rpio[base_l+0x10:base_l+0x14])[0]
print(f"Port L as ALL INPUTS with PULL-UPS -> DAT: 0x{dat:08x}")
for p in range(2, 12):
    lvl = (dat >> p) & 1
    print(f"  PL{p:02d}: level={lvl}")

rpio.close()
os.close(fd_mem)
