import os
import mmap
import struct
import time

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
rtc = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)

print(f"Before: LOSC_CTRL = 0x{struct.unpack('<I', rtc[0x00:0x04])[0]:08x}")

# Write with security key: 0x16aa0000 | BIT(4) (EXT_LOSC_EN) | BIT(0) (EXT_OSC) | BIT(15) (AUTO_SWT_BYPASS)
# 0x16aa8011
key_val = (0x16aa << 16) | (1 << 15) | (1 << 4) | 1
rtc[0x00:0x04] = struct.pack('<I', key_val)

time.sleep(0.01)

after = struct.unpack('<I', rtc[0x00:0x04])[0]
print(f"After:  LOSC_CTRL = 0x{after:08x}")
print(f"  EXT_LOSC_EN (bit 4): {bool(after & (1 << 4))}")
print(f"  EXT_OSC (bit 0):     {bool(after & 1)}")

# Ensure LOSC_OUT gating is active (0x60 = 1)
rtc[0x60:0x64] = struct.pack('<I', 1)
print(f"  LOSC_OUT (0x60):     0x{struct.unpack('<I', rtc[0x60:0x64])[0]:08x}")

rtc.close()
os.close(fd)
