import os
import mmap
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base = 0xc00

def r32(off):
    return struct.unpack('<I', rpio[base + off:base + off + 4])[0]

def w32(off, val):
    rpio[base + off:base + off + 4] = struct.pack('<I', val)

print("=== Testing Reset Pulse on each Port L Pin (PL2 to PL11) ===")
# All start HIGH
dat = r32(0x10) | (0x3ff << 2)
w32(0x10, dat)

for pin in range(2, 12):
    print(f"\n--- Pulsing PL{pin} LOW then HIGH ---")
    # Drive LOW
    dat = r32(0x10) & ~(1 << pin)
    w32(0x10, dat)
    time.sleep(0.05)
    # Drive HIGH
    dat = r32(0x10) | (1 << pin)
    w32(0x10, dat)
    time.sleep(1.2) # wait for mmc scan
    
    line = os.popen("dmesg | tail -n 1").read().strip()
    print(f"  PL{pin} pulse result: {line}")
    if "err=-110" not in line and "trying init" not in line:
        print(f"  >>> SUCCESS TRIGGERED BY PL{pin} PULSE!")
        break

rpio.close()
os.close(fd_mem)
