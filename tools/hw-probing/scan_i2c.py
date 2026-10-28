import os
import fcntl

# I2C_SLAVE = 0x0703
def scan_bus(bus_num):
    dev = f'/dev/i2c-{bus_num}'
    if not os.path.exists(dev):
        print(f"{dev} does not exist")
        return
    print(f"=== Scanning {dev} ===")
    found = []
    for addr in range(0x08, 0x78):
        try:
            fd = os.open(dev, os.O_RDWR)
            fcntl.ioctl(fd, 0x0703, addr)
            # Try a 1-byte read or write
            try:
                os.write(fd, b'\x00')
                found.append(hex(addr))
            except Exception:
                try:
                    os.read(fd, 1)
                    found.append(hex(addr))
                except Exception:
                    pass
            os.close(fd)
        except Exception:
            pass
    print(f"Found on i2c-{bus_num}: {found}")

scan_bus(0)
scan_bus(1)
