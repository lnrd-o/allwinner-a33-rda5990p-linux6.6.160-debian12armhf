import os
import mmap
import struct

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
rtc = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ, offset=0x01f00000)

ctrl = struct.unpack('<I', rtc[0x00:0x04])[0]
gate = struct.unpack('<I', rtc[0x60:0x64])[0]
presc = struct.unpack('<I', rtc[0x08:0x0c])[0]

print(f"RTC LOSC_CTRL (0x00): 0x{ctrl:08x}")
print(f"RTC LOSC_PRESC (0x08): 0x{presc:08x}")
print(f"RTC LOSC_OUT (0x60): 0x{gate:08x}")

# Decode LOSC_CTRL:
# bit 0: EXT_OSC (1=ext 32768 crystal, 0=internal RC osc)
# bit 4: EXT_LOSC_EN
# bit 15: AUTO_SWT_BYPASS
print(f"  EXT_OSC (bit 0): {bool(ctrl & 1)}")
print(f"  EXT_LOSC_EN (bit 4): {bool(ctrl & (1 << 4))}")
print(f"  AUTO_SWT_BYPASS (bit 15): {bool(ctrl & (1 << 15))}")

rtc.close()
os.close(fd)
