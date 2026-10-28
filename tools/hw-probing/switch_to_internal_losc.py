#!/usr/bin/env python3
import os
import mmap
import struct
import time

print("==================================================")
print("  SWITCHING RTC TO INTERNAL 32kHz RC OSCILLATOR   ")
print("==================================================")

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
rtc = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)

before = struct.unpack('<I', rtc[0x00:0x04])[0]
print(f"Before: LOSC_CTRL = 0x{before:08x} (EXT_OSC={bool(before & 1)})")

# Write 0x16aa8000: Key + Auto Switch Bypass + Internal RC Oscillator (bit 0 = 0)
val = (0x16aa << 16) | (1 << 15)
rtc[0x00:0x04] = struct.pack('<I', val)
time.sleep(0.05)

after = struct.unpack('<I', rtc[0x00:0x04])[0]
print(f"After:  LOSC_CTRL = 0x{after:08x} (EXT_OSC={bool(after & 1)})")

# Ensure LOSC_OUT gating is active (0x60 = 1)
rtc[0x60:0x64] = struct.pack('<I', 1)
out_val = struct.unpack('<I', rtc[0x60:0x64])[0]
print(f"  LOSC_OUT (0x60) = 0x{out_val:08x} (Enabled={bool(out_val & 1)})")

# Test if RTC time register (0x14) is now ticking!
print("\n[Testing if RTC is ticking automatically]:")
for i in range(4):
    hms = struct.unpack('<I', rtc[0x14:0x18])[0]
    sec = hms & 0x3f
    minute = (hms >> 8) & 0x3f
    hour = (hms >> 16) & 0x1f
    print(f"  Sample {i}: RTC HMS = {hour:02d}:{minute:02d}:{sec:02d} (raw=0x{hms:08x})")
    time.sleep(1.0)

rtc.close()
os.close(fd)
