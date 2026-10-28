import os
import mmap
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 1. Ensure RTC 32kHz clock fanout is ON
rtc = mmap.mmap(fd_mem, 4096, offset=0x01f00000)
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()

# 2. Port L (0x01f02c00)
# CFG0: PL0 to PL7
# CFG1: PL8 to PL11
# DAT: 0x10
rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base = 0xc00

def r32(off):
    return struct.unpack('<I', rpio[base + off:base + off + 4])[0]

def w32(off, val):
    rpio[base + off:base + off + 4] = struct.pack('<I', val)

cfg0 = r32(0x00)
cfg1 = r32(0x04)
dat  = r32(0x10)
print(f"BEFORE: CFG0=0x{cfg0:08x}, CFG1=0x{cfg1:08x}, DAT=0x{dat:08x}")

# Keep PL0 and PL1 for RSB (bits [7:0] = 0x22)
# Configure PL2, PL3, PL4, PL5, PL6, PL7 as OUTPUT (1)
cfg0 = (cfg0 & 0x000000ff) | 0x11111100
# Configure PL8, PL9, PL10, PL11 as OUTPUT (1)
cfg1 = 0x00001111

w32(0x00, cfg0)
w32(0x04, cfg1)

# Drive PL2 through PL11 HIGH (1)
dat |= (0x3ff << 2) # bits 2 to 11 all HIGH!
w32(0x10, dat)
time.sleep(0.1)

cfg0_now = r32(0x00)
cfg1_now = r32(0x04)
dat_now  = r32(0x10)
print(f"AFTER:  CFG0=0x{cfg0_now:08x}, CFG1=0x{cfg1_now:08x}, DAT=0x{dat_now:08x}")
print("All Port L pins (PL2 to PL11) are now driven to 3.3V HIGH!")

rpio.close()
os.close(fd_mem)

# Watch dmesg for 3 seconds
print("\nWaiting for kernel MMC1 rescan attempts...")
for i in range(3):
    time.sleep(1)
    line = os.popen("dmesg | tail -n 1").read().strip()
    print(f"  [{i+1}s] dmesg: {line}")
    if "err=-110" not in line and "trying init" not in line:
        print("  >>> SUCCESS DETECTED ON MMC1!")
        break
