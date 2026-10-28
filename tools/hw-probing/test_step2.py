import os
import fcntl
import time

fd = os.open('/dev/i2c-1', os.O_RDWR)
fcntl.ioctl(fd, 0x0703, 0x16)

def w(reg, val):
    data = bytes([reg, (val >> 8) & 0xff, val & 0xff])
    os.write(fd, data)

def r(reg):
    os.write(fd, bytes([reg]))
    buf = os.read(fd, 2)
    return (buf[0] << 8) | buf[1]

print("=== Testing Writes to 0x16 ===")
try:
    print("1. Set Page 1 (0x3f = 0x0001)")
    w(0x3f, 0x0001)
    print("   Success! Reading back 0x3f:", hex(r(0x3f)))
except Exception as e:
    print("   Failed:", e)

try:
    print("2. Writing wifi_en_data to 0x16...")
    w(0x23, 0x8fa1)
    w(0x31, 0x0b40)
    w(0x24, 0x80c8)
    w(0x27, 0x4925)
    w(0x31, 0x8140)
    time.sleep(0.015)
    w(0x32, 0x0113)
    print("   wifi_en_data success! Reading 0x31:", hex(r(0x31)))
except Exception as e:
    print("   Failed wifi_en_data:", e)

try:
    print("3. Check 0xA2 and WLAN Version:")
    a2 = r(0x22)
    print(f"   0xA2 = 0x{a2:04x}")
    a2 |= 0x0200
    w(0x22, a2)
    ver = r(0x21)
    print(f"   WLAN Version (0x21) = 0x{ver:04x}")
except Exception as e:
    print("   Failed 0xA2:", e)

print("4. Switching back to Page 0 (0x3f = 0x0000)")
try:
    w(0x3f, 0x0000)
    print("   Page 0 set!")
except Exception as e:
    print("   Failed setting Page 0:", e)

print("5. Now check if 0x14 or 0x13 or 0x15 appeared on the bus:")
for addr in [0x13, 0x14, 0x15, 0x16]:
    try:
        fcntl.ioctl(fd, 0x0703, addr)
        os.write(fd, bytes([0x3f]))
        buf = os.read(fd, 2)
        print(f"   Addr 0x{addr:02x}: ACK! val=0x{(buf[0]<<8)|buf[1]:04x}")
    except Exception as e:
        print(f"   Addr 0x{addr:02x}: No ACK ({e})")

os.close(fd)
