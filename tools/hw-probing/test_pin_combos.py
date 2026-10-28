import os
import mmap
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base_l = 0xc00

def r32(off):
    return struct.unpack('<I', rpio[base_l + off:base_l + off + 4])[0]

def w32(off, val):
    rpio[base_l + off:base_l + off + 4] = struct.pack('<I', val)

# Ensure PL6, PL8, PL10, PL11 are OUTPUTS
cfg0 = r32(0x00)
cfg1 = r32(0x04)
cfg0 = (cfg0 & ~(0x7 << 24)) | (1 << 24) # PL6 out
cfg1 = (cfg1 & ~(0x7 << 0))  | (1 << 0)  # PL8 out
cfg1 = (cfg1 & ~(0x7 << 8))  | (1 << 8)  # PL10 out
cfg1 = (cfg1 & ~(0x7 << 12)) | (1 << 12) # PL11 out
w32(0x00, cfg0)
w32(0x04, cfg1)

# Ensure RTC 32k clock is active
rtc = mmap.mmap(fd_mem, 4096, offset=0x01f00000)
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()

print("=== Testing All Combinations of Control Pins (PL6, PL8, PL11) ===")

def check_dmesg():
    lines = os.popen("dmesg | tail -n 2").read().strip().split("\n")
    return lines[-1] if lines else ""

# Test combinations: (PL6, PL8, PL11)
combos = [
    (1, 0, 1), # PL8=0 (what if PL8 is active-high reset?)
    (1, 1, 1), # all high
    (0, 1, 1), # PL6=0
    (1, 1, 0), # PL11=0
    (1, 0, 0),
    (0, 0, 1),
    (0, 1, 0),
]

for pl6, pl8, pl11 in combos:
    dat = r32(0x10)
    dat = (dat & ~(1 << 6))  | (pl6  << 6)
    dat = (dat & ~(1 << 8))  | (pl8  << 8)
    dat = (dat & ~(1 << 11)) | (pl11 << 11)
    dat |= (1 << 10) # PL10 high
    w32(0x10, dat)
    
    print(f"\n--- Set: PL6={pl6}, PL8={pl8}, PL11={pl11} ---")
    time.sleep(1.2) # wait for kernel mmc rescan attempt
    last = check_dmesg()
    print("  dmesg:", last)
    if "err=-110" not in last and "trying init" not in last:
        print("  >>> SUCCESS DETECTED ON MMC1!")
        break

rpio.close()
os.close(fd_mem)
