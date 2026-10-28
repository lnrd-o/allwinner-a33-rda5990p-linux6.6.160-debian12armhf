import mmap, os, struct

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
mm = mmap.mmap(fd, 4096, offset=0x01f02000)
print("=== DUMP 0x01f02c00 - 0x01f02c40 ===")
for i in range(0, 0x40, 4):
    val = struct.unpack('<I', mm[0xc00+i:0xc00+i+4])[0]
    print(f"+0x{i:02x}: 0x{val:08x}")
mm.close()
os.close(fd)
