import os
import mmap
import struct
import time

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
ccu = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)

orig_val = struct.unpack('<I', ccu[0x8c:0x90])[0]
print(f"Initial MMC1_CLK (0x8c) = 0x{orig_val:08x}")

# Phases to test: sample (0, 1, 2, 3) x output (0, 1, 2, 3)
# Rates: P=2 (400kHz), P=3 (200kHz)
success = False
for p in [2, 3]:
    freq_khz = 400 if p == 2 else 200
    for sample in [2, 0, 1, 3]:
        for output in [2, 0, 1, 3]:
            # Construct new register value
            # Bits: [31]=1 (gate), [25:24]=0 (24M), [22:20]=sample, [17:16]=p, [10:8]=output, [3:0]=0xe (15)
            new_val = 0x8000000e | (sample << 20) | (p << 16) | (output << 8)
            ccu[0x8c:0x90] = struct.pack('<I', new_val)
            time.sleep(1.2) # wait for kernel mmc rescan
            
            lines = os.popen("dmesg | tail -n 2").read().strip().split("\n")
            last_line = lines[-1] if lines else ""
            print(f"Freq={freq_khz}kHz, Sample={sample*90}deg, Output={output*90}deg (0x{new_val:08x}) -> {last_line}")
            if "err=-110" not in last_line and "trying init" not in last_line:
                print("\n" + "="*50)
                print(">>> SUCCESS DETECTED ON MMC1!")
                print("\n".join(lines))
                print("="*50 + "\n")
                success = True
                break
        if success:
            break
    if success:
        break

if not success:
    ccu[0x8c:0x90] = struct.pack('<I', orig_val)
    print("Test finished. Restored original value.")

ccu.close()
os.close(fd)
