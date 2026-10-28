import os
import fcntl
import time
import mmap
import struct

print("=== RDA5990 Silicon Wakeup & SDIO Digital Reset ===")

# 1. Verify RTC 32kHz fanout is active
fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
rtc = mmap.mmap(fd_mem, 4096, offset=0x01f00000)
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()

# 2. Port L: PL6=1, PL8=1, PL11=1 (all HIGH)
rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base_l = 0xc00
cfg0 = (struct.unpack('<I', rpio[base_l:base_l+4])[0] & ~(0x7 << 24)) | (1 << 24)
cfg1 = (struct.unpack('<I', rpio[base_l+4:base_l+8])[0] & ~0x7007) | 0x1001
rpio[base_l:base_l+4] = struct.pack('<I', cfg0)
rpio[base_l+4:base_l+8] = struct.pack('<I', cfg1)
dat = struct.unpack('<I', rpio[base_l+0x10:base_l+0x14])[0] | (1 << 6) | (1 << 8) | (1 << 10) | (1 << 11)
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', dat)
rpio.close()
os.close(fd_mem)
print("  [+] Power and clock lines held HIGH (PL6=1, PL8=1, PL11=1, 32kHz=1)")

# 3. I2C Wake on /dev/i2c-1 at 0x16
dev = '/dev/i2c-1'
fd = os.open(dev, os.O_RDWR)

def w(addr, reg, val):
    fcntl.ioctl(fd, 0x0703, addr)
    data = bytes([reg, (val >> 8) & 0xff, val & 0xff])
    os.write(fd, data)

def r(addr, reg):
    fcntl.ioctl(fd, 0x0703, addr)
    os.write(fd, bytes([reg]))
    buf = os.read(fd, 2)
    return (buf[0] << 8) | buf[1]

# Probe 0x16
target_addr = None
for a in [0x16, 0x14]:
    try:
        fcntl.ioctl(fd, 0x0703, a)
        os.write(fd, bytes([0x3f]))
        val = os.read(fd, 2)
        target_addr = a
        print(f"  [+] Responded at address 0x{a:02x}! (Reg 0x3f = 0x{(val[0]<<8)|val[1]:04x})")
        break
    except Exception as e:
        print(f"  [-] Addr 0x{a:02x} probe: {e}")

if not target_addr:
    print("[-] No ACK on 0x16 or 0x14 on /dev/i2c-1")
else:
    print(f"\n[+] Executing Power-On Sequence on 0x{target_addr:02x}...")
    # Step A: wifi_en_data
    w(target_addr, 0x3f, 0x0001)
    w(target_addr, 0x23, 0x8fa1)
    w(target_addr, 0x31, 0x0b40) # wifi off first
    w(target_addr, 0x24, 0x80c8)
    w(target_addr, 0x27, 0x4925)
    w(target_addr, 0x31, 0x8140) # enable wifi
    time.sleep(0.015)
    w(target_addr, 0x32, 0x0113) # ldo on
    
    # Step B: Setup A2 power
    a2 = r(target_addr, 0x22)
    print(f"  0xA2 Register: 0x{a2:04x}")
    a2 |= 0x0200
    w(target_addr, 0x22, a2)
    
    wlan_ver = r(target_addr, 0x21)
    print(f"  WLAN Version (0x21): 0x{wlan_ver:04x}")
    
    # Step C: Wi-Fi Digital Reset (wakes up internal SDIO state machine)
    print("  Executing Wi-Fi Digital Reset sequence (0x31: 0x8D40 -> 0x8F40 -> 0x8B40)...")
    w(target_addr, 0x31, 0x8d40)
    time.sleep(0.005)
    w(target_addr, 0x31, 0x8f40)
    time.sleep(0.005)
    w(target_addr, 0x31, 0x8b40)
    time.sleep(0.010)
    w(target_addr, 0x3f, 0x0000) # page down
    print("  [+] Wi-Fi Digital Reset complete!")

os.close(fd)

# Check dmesg
print("\nWaiting for kernel MMC1 rescan...")
time.sleep(1.5)
lines = os.popen("dmesg | tail -n 5").read().strip().split("\n")
for l in lines:
    print("  dmesg:", l)
