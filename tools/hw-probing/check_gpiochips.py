import os
import struct
import fcntl

# GPIO_GET_CHIPINFO_IOCTL = 0x8044b401
for dev in ['/dev/gpiochip0', '/dev/gpiochip1']:
    fd = os.open(dev, os.O_RDONLY)
    buf = bytearray(68)
    fcntl.ioctl(fd, 0x8044b401, buf)
    name, label, lines = struct.unpack('32s32sI', buf)
    print(dev, name.split(b'\x00')[0].decode(), label.split(b'\x00')[0].decode(), lines)
    os.close(fd)
