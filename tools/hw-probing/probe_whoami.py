import os, fcntl

f = os.open('/dev/i2c-1', os.O_RDWR)
fcntl.ioctl(f, 0x0703, 0x17)
for r in [0x00, 0x01, 0x02, 0x0f, 0x10, 0x20, 0x3f]:
    try:
        os.write(f, bytes([r]))
        b = os.read(f, 1)
        print(f"Reg 0x{r:02x}: 0x{b[0]:02x}")
    except Exception as e:
        print(f"Reg 0x{r:02x}: err {e}")
os.close(f)
