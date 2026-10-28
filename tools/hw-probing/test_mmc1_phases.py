import os
import mmap
import struct
import time

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
ccu = mmap.mmap(fd, 4096, offset=0x01c20000)

val = struct.unpack('<I', ccu[0x64:0x68])[0]
print(f"Original MMC1_CLK (0x01c20064) = 0x{val:08x}")
print(f"  Sample Phase: {((val >> 20) & 0x7) * 90} deg (bits={(val >> 20) & 0x7})")
print(f"  Output Phase: {((val >> 8)  & 0x7) * 90} deg (bits={(val >> 8) & 0x7})")

# Let's test each sample phase (0, 1, 2, 3) -> 0 deg, 90 deg, 180 deg, 270 deg
# while monitoring dmesg
for sample_bits in [0, 1, 2, 3]:
    for output_bits in [0, 2]:
        new_val = (val & ~((0x7 << 20) | (0x7 << 8))) | (sample_bits << 20) | (output_bits << 8)
        ccu[0x64:0x68] = struct.pack('<I', new_val)
        time.sleep(0.5)
        # Check dmesg
        cur = struct.unpack('<I', ccu[0x64:0x68])[0]
        # read dmesg tail
        lines = os.popen("dmesg | tail -n 2").read().strip().split("\n")
        last_line = lines[-1] if lines else ""
        print(f"Testing Sample={sample_bits*90}deg, Output={output_bits*90}deg -> {last_line}")
        if "err=-110" not in last_line and "trying init" not in last_line:
            print("  >>> POTENTIAL SUCCESS: " + "\n".join(lines))
            break

# Restore original
ccu[0x64:0x68] = struct.pack('<I', val)
ccu.close()
os.close(fd)
