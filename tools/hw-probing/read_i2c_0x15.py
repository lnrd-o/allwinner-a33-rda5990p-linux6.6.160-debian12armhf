import os, fcntl

I2C_SLAVE = 0x0703
fd = os.open('/dev/i2c-1', os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, 0x15)

print("Reading registers 0x00..0x20 from 0x15 on /dev/i2c-1:")
for reg in range(0x20):
    try:
        os.write(fd, bytes([reg]))
        val = os.read(fd, 2) # Read 2 bytes
        hex_val = ' '.join(f"{b:02x}" for b in val)
        print(f"  Reg 0x{reg:02x}: {hex_val}")
    except Exception as e:
        # Try 1 byte read
        try:
            val = os.read(fd, 1)
            print(f"  Reg 0x{reg:02x} (1-byte): 0x{val[0]:02x}")
        except Exception:
            pass
os.close(fd)
