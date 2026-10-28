import os
import mmap
import struct

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
ccu = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ, offset=0x01c20000)

val0 = struct.unpack('<I', ccu[0x88:0x8c])[0]
val1 = struct.unpack('<I', ccu[0x8c:0x90])[0]
val2 = struct.unpack('<I', ccu[0x90:0x94])[0]

print(f"MMC0_CLK (0x88): 0x{val0:08x}")
print(f"MMC1_CLK (0x8c): 0x{val1:08x}")
print(f"MMC2_CLK (0x90): 0x{val2:08x}")

ccu.close()
os.close(fd)
