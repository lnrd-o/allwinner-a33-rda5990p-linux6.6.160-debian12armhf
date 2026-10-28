import mmap, os, struct, time

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
mm = mmap.mmap(fd, 4096, offset=0x01c20000)

# Port G is at offset 0x800 + 0xd8 = 0x8d8
cfg0 = struct.unpack('<I', mm[0x8d8:0x8dc])[0]
pull0 = struct.unpack('<I', mm[0x8f4:0x8f8])[0]
print(f"Original PG CFG0: 0x{cfg0:08x}, PULL0: 0x{pull0:08x}")

# Set PG0-PG5 to input (func 0)
cfg_input = cfg0 & ~(0x00ffffff)
mm[0x8d8:0x8dc] = struct.pack('<I', cfg_input)
time.sleep(0.01)

dat = struct.unpack('<I', mm[0x8e8:0x8ec])[0]
print(f"PG0-PG5 as input -> DAT: 0x{dat:08x} (bits 0-5: {(dat & 0x3f):06b})")
# Disable internal pull-ups on PG0-PG5 to check for external pull-ups
pull_none = pull0 & ~(0x00000fff)
mm[0x8f4:0x8f8] = struct.pack('<I', pull_none)
time.sleep(0.01)
dat_nopull = struct.unpack('<I', mm[0x8e8:0x8ec])[0]
print(f"PG0-PG5 with NO internal pull -> DAT: 0x{dat_nopull:08x} (bits 0-5: {(dat_nopull & 0x3f):06b})")
for pin in range(6):
    names = ["CLK", "CMD", "D0", "D1", "D2", "D3"]
    print(f"  PG{pin} ({names[pin]}): external pull={'PULLED HIGH' if (dat_nopull >> pin) & 1 else 'LOW/FLOATING'}")

# Restore pull-up
mm[0x8f4:0x8f8] = struct.pack('<I', pull0)

# Restore original func (func 2 for PG0-PG5)
mm[0x8d8:0x8dc] = struct.pack('<I', cfg0)
time.sleep(0.01)
cfg_restored = struct.unpack('<I', mm[0x8d8:0x8dc])[0]
print(f"Restored PG CFG0: 0x{cfg_restored:08x}")

mm.close()
os.close(fd)
