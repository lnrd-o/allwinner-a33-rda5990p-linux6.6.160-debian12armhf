import os
import fcntl

for b in [0, 1, 2]:
    dev = f"/dev/i2c-{b}"
    if not os.path.exists(dev):
        print(f"{dev} does not exist!")
        continue
    fd = os.open(dev, os.O_RDWR)
    found_wr = []
    found_rd = []
    for a in range(0x03, 0x78):
        try:
            fcntl.ioctl(fd, 0x0703, a)
            os.write(fd, bytes([0x00]))
            found_wr.append(hex(a))
        except:
            pass
        try:
            fcntl.ioctl(fd, 0x0703, a)
            b_read = os.read(fd, 1)
            found_rd.append(hex(a))
        except:
            pass
    os.close(fd)
    print(f"{dev} Write ACKs: {found_wr}")
    print(f"{dev} Read ACKs:  {found_rd}")
