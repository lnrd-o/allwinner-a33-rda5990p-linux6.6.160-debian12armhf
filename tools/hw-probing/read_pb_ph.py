import mmap, os, struct

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
pio = mmap.mmap(fd, 4096, offset=0x01c20000)

cfg_b = struct.unpack('<I', pio[0x824:0x828])[0]
dat_b = struct.unpack('<I', pio[0x834:0x838])[0]
pull_b = struct.unpack('<I', pio[0x840:0x844])[0]

cfg_h0 = struct.unpack('<I', pio[0x8fc:0x900])[0]
cfg_h1 = struct.unpack('<I', pio[0x900:0x904])[0]
dat_h = struct.unpack('<I', pio[0x90c:0x910])[0]
pull_h = struct.unpack('<I', pio[0x918:0x91c])[0]

print(f"Port B CFG0=0x{cfg_b:08x}, DAT=0x{dat_b:08x}, PULL0=0x{pull_b:08x}")
for i in range(8):
    mux = (cfg_b >> (i*4)) & 0x7
    val = (dat_b >> i) & 1
    print(f"  PB{i}: mux={mux}, val={val}")

print(f"\nPort H CFG0=0x{cfg_h0:08x}, CFG1=0x{cfg_h1:08x}, DAT=0x{dat_h:08x}")
for i in range(8):
    mux = (cfg_h0 >> (i*4)) & 0x7
    val = (dat_h >> i) & 1
    print(f"  PH{i}: mux={mux}, val={val}")
for i in range(8, 10):
    mux = (cfg_h1 >> ((i-8)*4)) & 0x7
    val = (dat_h >> i) & 1
    print(f"  PH{i}: mux={mux}, val={val}")

pio.close()
os.close(fd)
