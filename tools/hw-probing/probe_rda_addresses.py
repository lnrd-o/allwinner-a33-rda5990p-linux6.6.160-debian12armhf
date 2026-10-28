import os
import fcntl

fd = os.open('/dev/i2c-1', os.O_RDWR)
print("=== Probing RDA Addresses on /dev/i2c-1 ===")
for addr in [0x13, 0x14, 0x15, 0x16]:
    try:
        fcntl.ioctl(fd, 0x0703, addr)
        os.write(fd, bytes([0x3f]))
        val = os.read(fd, 2)
        print(f"  Addr 0x{addr:02x}: ACK! val=0x{(val[0]<<8)|val[1]:04x}")
    except Exception as e:
        print(f"  Addr 0x{addr:02x}: No ACK ({e})")
os.close(fd)
