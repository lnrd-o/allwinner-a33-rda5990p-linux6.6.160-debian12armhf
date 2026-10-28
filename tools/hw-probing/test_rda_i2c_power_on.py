#!/usr/bin/env python3
import os
import fcntl
import mmap
import struct
import time

def read_u32(mm, offset):
    return struct.unpack('<I', mm[offset:offset+4])[0]

def write_u32(mm, offset, val):
    mm[offset:offset+4] = struct.pack('<I', val)

def set_pin_power():
    print("[1] Powering and Clocking RDA5990...")
    fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
    
    # 32k clock
    rtc = mmap.mmap(fd, 4096, offset=0x01f00000)
    write_u32(rtc, 0x60, 1)
    rtc.close()
    
    # Port L (0x01f02c00)
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
    
    # Reset all first
    dat &= ~((1 << 6) | (1 << 8) | (1 << 10) | (1 << 11))
    write_u32(rpio, base_l + 0x10, dat)
    time.sleep(0.02)
    
    # 1. Drive PL11 (chip_en) HIGH
    dat |= (1 << 11)
    write_u32(rpio, base_l + 0x10, dat)
    time.sleep(0.01)
    
    # 2. Drive PL06 (wl_regon) HIGH
    dat |= (1 << 6) | (1 << 10)
    write_u32(rpio, base_l + 0x10, dat)
    time.sleep(0.01)
    
    # 3. Drive PL08 (bt_rst_n) HIGH
    dat |= (1 << 8)
    write_u32(rpio, base_l + 0x10, dat)
    time.sleep(0.05)
    
    dat_now = read_u32(rpio, base_l + 0x10)
    print(f"    Port L DAT = 0x{dat_now:08x} (PL6={bool(dat_now&(1<<6))}, PL8={bool(dat_now&(1<<8))}, PL11={bool(dat_now&(1<<11))})")
    rpio.close()
    os.close(fd)

def test_i2c_bus(bus_num):
    dev = f'/dev/i2c-{bus_num}'
    if not os.path.exists(dev):
        print(f"[-] {dev} does not exist")
        return False
    print(f"[*] Testing {dev} for RDA5990 (0x13, 0x14, 0x15, 0x16)...")
    found = []
    for addr in [0x13, 0x14, 0x15, 0x16]:
        try:
            fd = os.open(dev, os.O_RDWR)
            fcntl.ioctl(fd, 0x0703, addr)
            # Try reading register 0x3f
            os.write(fd, bytes([0x3f]))
            val = os.read(fd, 2)
            u16_val = (val[0] << 8) | val[1]
            print(f"    [+] Responded at addr 0x{addr:02x}! Reg 0x3f = 0x{u16_val:04x}")
            found.append(addr)
            os.close(fd)
        except Exception as e:
            try:
                os.close(fd)
            except:
                pass
    return found

def main():
    set_pin_power()
    found0 = test_i2c_bus(0)
    found1 = test_i2c_bus(1)
    if not found0 and not found1:
        print("[-] Not detected on i2c-0 or i2c-1 with standard read.")
    else:
        print(f"[+] Found targets: i2c-0: {found0}, i2c-1: {found1}")

if __name__ == '__main__':
    main()
