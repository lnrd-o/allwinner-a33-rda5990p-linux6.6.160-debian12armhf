import os, sys, time, fcntl

I2C_SLAVE = 0x0703
dev_path = "/dev/i2c-1"

print(f"Targeted Scan of {dev_path}:")
fd = os.open(dev_path, os.O_RDWR)

found = []
for addr in range(0x08, 0x78):
    try:
        fcntl.ioctl(fd, I2C_SLAVE, addr)
        os.write(fd, b'\x00')
        found.append(f"0x{addr:02x}")
    except Exception:
        pass

print("Found on /dev/i2c-1:", found)

# Now test specific RDA addresses on /dev/i2c-1:
rda_addrs = [0x11, 0x13, 0x14, 0x15, 0x16, 0x18, 0x19]
print("\nTesting specific RDA candidates on /dev/i2c-1:")
for addr in rda_addrs:
    try:
        fcntl.ioctl(fd, I2C_SLAVE, addr)
        # Try reading 1 byte or 2 bytes
        os.write(fd, b'\x00')
        print(f"  [+] Address 0x{addr:02x}: ACK received on write!")
    except Exception as e:
        print(f"  [-] Address 0x{addr:02x}: NAK ({e})")

os.close(fd)
