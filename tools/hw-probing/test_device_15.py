import os, fcntl

fd = os.open('/dev/i2c-1', os.O_RDWR)
fcntl.ioctl(fd, 0x0703, 0x15)

print("Reading registers from 0x15 on i2c-1:")
for reg in [0x00, 0x01, 0x02, 0x0f, 0x20, 0x3f]:
    try:
        os.write(fd, bytes([reg]))
        data = os.read(fd, 2)
        print(f"Reg 0x{reg:02x}: {[hex(b) for b in data]}")
    except Exception as e:
        print(f"Reg 0x{reg:02x}: error {e}")
os.close(fd)
