import os
import fcntl

print("=== Scanning /dev/i2c-0 for ALL devices ===")
f = os.open('/dev/i2c-0', os.O_RDWR)
acks_wr = []
acks_rd = []

for a in range(0x08, 0x78):
    try:
        fcntl.ioctl(f, 0x0703, a)
        os.write(f, bytes([0x00]))
        acks_wr.append(hex(a))
    except:
        pass

    try:
        fcntl.ioctl(f, 0x0703, a)
        b = os.read(f, 1)
        acks_rd.append((hex(a), hex(b[0])))
    except:
        pass

os.close(f)
print("Write ACKs on /dev/i2c-0:", acks_wr)
print("Read ACKs on /dev/i2c-0:", acks_rd)
