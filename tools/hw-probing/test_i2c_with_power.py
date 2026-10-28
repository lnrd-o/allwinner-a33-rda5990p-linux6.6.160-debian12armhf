import os
import fcntl
import mmap
import struct
import time

def read_u32(mm, offset):
    return struct.unpack('<I', mm[offset:offset+4])[0]

def write_u32(mm, offset, val):
    mm[offset:offset+4] = struct.pack('<I', val)

def main():
    print("=" * 60)
    print("  I2C SCAN WITH RDA5990 FULLY POWERED")
    print("=" * 60)
    
    fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
    
    # 1. RTC 32k fanout
    rtc = mmap.mmap(fd, 4096, offset=0x01f00000)
    write_u32(rtc, 0x60, 1)
    rtc.close()
    
    # 2. Port L: PL6=1, PL8=1, PL11=1, PL10=1, PL7/PL9=in pullup
    rpio = mmap.mmap(fd, 4096, offset=0x01f02000)
    base_l = 0xc00
    cfg0 = read_u32(rpio, base_l)
    cfg1 = read_u32(rpio, base_l + 4)
    dat  = read_u32(rpio, base_l + 0x10)
    pull = read_u32(rpio, base_l + 0x1c)
    
    cfg0 = (cfg0 & ~(0x7 << 24)) | (1 << 24) # PL6 out
    cfg0 = (cfg0 & ~(0x7 << 28)) | (0 << 28) # PL7 in
    cfg1 = (cfg1 & ~(0x7 << 0))  | (1 << 0)  # PL8 out
    cfg1 = (cfg1 & ~(0x7 << 4))  | (0 << 4)  # PL9 in
    cfg1 = (cfg1 & ~(0x7 << 8))  | (1 << 8)  # PL10 out
    cfg1 = (cfg1 & ~(0x7 << 12)) | (1 << 12) # PL11 out
    pull |= (1 << 14) | (1 << 18)
    
    write_u32(rpio, base_l, cfg0)
    write_u32(rpio, base_l + 4, cfg1)
    write_u32(rpio, base_l + 0x1c, pull)
    
    # Reset cycle
    dat &= ~((1 << 6) | (1 << 8) | (1 << 10) | (1 << 11))
    write_u32(rpio, base_l + 0x10, dat)
    time.sleep(0.05)
    
    dat |= (1 << 6) | (1 << 10) | (1 << 11)
    write_u32(rpio, base_l + 0x10, dat)
    time.sleep(0.05)
    
    dat |= (1 << 8)
    write_u32(rpio, base_l + 0x10, dat)
    time.sleep(0.1)
    
    print(f"Port L DAT: 0x{read_u32(rpio, base_l + 0x10):08x}")
    rpio.close()
    os.close(fd)
    
    # 3. Now scan both I2C buses
    for bus_num in [0, 1]:
        dev = f'/dev/i2c-{bus_num}'
        if not os.path.exists(dev):
            continue
        found = []
        for addr in range(0x08, 0x78):
            try:
                i2cfd = os.open(dev, os.O_RDWR)
                fcntl.ioctl(i2cfd, 0x0703, addr)
                try:
                    os.write(i2cfd, b'\x00')
                    found.append(hex(addr))
                except Exception:
                    try:
                        os.read(i2cfd, 1)
                        found.append(hex(addr))
                    except Exception:
                        pass
                os.close(i2cfd)
            except Exception:
                pass
        print(f"I2C-{bus_num} responding devices: {found}")
    print("=" * 60)

if __name__ == '__main__':
    main()
