#!/usr/bin/env python3
import mmap
import os
import struct
import time

def read_u32(mm, offset):
    return struct.unpack('<I', mm[offset:offset+4])[0]

def write_u32(mm, offset, val):
    mm[offset:offset+4] = struct.pack('<I', val)

def main():
    print("=== Powering On RDA5990P ===")
    fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
    
    # 1. RTC LOSC_OUT (0x01f00060)
    rtc = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)
    write_u32(rtc, 0x60, 1) # Enable 32k clock output
    print(f"1. RTC LOSC_OUT: 0x{read_u32(rtc, 0x60):08x}")
    
    # 2. Port L base 0x01f02000 offset 0xc00
    r_gpio = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f02000)
    
    # Configure pins:
    # PL6: func 1 (output), PL7: func 0 (input, host wake)
    # PL8: func 1 (output, rst), PL9: func 0 (input, bt wake)
    # PL10: func 1 (output, bt_wake), PL11: func 1 (output, chip_en)
    
    # Read current CFG0 and CFG1
    cfg0 = read_u32(r_gpio, 0xc00 + 0x00)
    cfg1 = read_u32(r_gpio, 0xc00 + 0x04)
    dat  = read_u32(r_gpio, 0xc00 + 0x10)
    pull = read_u32(r_gpio, 0xc00 + 0x1c)
    
    # Set PL6 func=1, PL7 func=0
    cfg0 = (cfg0 & ~(0x7 << 24)) | (1 << 24)
    cfg0 = (cfg0 & ~(0x7 << 28)) | (0 << 28)
    write_u32(r_gpio, 0xc00 + 0x00, cfg0)
    
    # Set PL8 func=1, PL9 func=0, PL10 func=1, PL11 func=1
    cfg1 = (cfg1 & ~(0x7 << 0)) | (1 << 0)
    cfg1 = (cfg1 & ~(0x7 << 4)) | (0 << 4)
    cfg1 = (cfg1 & ~(0x7 << 8)) | (1 << 8)
    cfg1 = (cfg1 & ~(0x7 << 12)) | (1 << 12)
    write_u32(r_gpio, 0xc00 + 0x04, cfg1)
    
    # Pull-ups on PL7 (bit 14-15 = 1) and PL9 (bit 18-19 = 1)
    pull |= (1 << 14) | (1 << 18)
    write_u32(r_gpio, 0xc00 + 0x1c, pull)
    
    # Sequence:
    # 1. Assert reset: PL8=0, PL6=0, PL11=0
    dat &= ~((1 << 6) | (1 << 8) | (1 << 10) | (1 << 11))
    write_u32(r_gpio, 0xc00 + 0x10, dat)
    print("2. Asserted reset (PL8=0, PL6=0, PL11=0)")
    time.sleep(0.05)
    
    # 2. Assert chip_en (PL11=1) and wl_regon (PL6=1)
    dat |= (1 << 11) | (1 << 6)
    write_u32(r_gpio, 0xc00 + 0x10, dat)
    print("3. Enabled chip_en (PL11=1) and wl_regon (PL6=1)")
    time.sleep(0.05)
    
    # 3. Deassert reset (PL8=1)
    dat |= (1 << 8)
    write_u32(r_gpio, 0xc00 + 0x10, dat)
    print("4. Deasserted reset (PL8=1)")
    time.sleep(0.1)
    
    # Verify pin status
    cfg0 = read_u32(r_gpio, 0xc00 + 0x00)
    cfg1 = read_u32(r_gpio, 0xc00 + 0x04)
    dat  = read_u32(r_gpio, 0xc00 + 0x10)
    print(f"5. Port L state: CFG0=0x{cfg0:08x}, CFG1=0x{cfg1:08x}, DAT=0x{dat:08x}")
    print(f"   PL06(wl_regon)={bool(dat & (1<<6))}, PL08(bt_rst)={bool(dat & (1<<8))}, PL11(chip_en)={bool(dat & (1<<11))}")
    print(f"   PL07(wl_hostwake)={bool(dat & (1<<7))}, PL09(bt_hostwake)={bool(dat & (1<<9))}")

    # Check SDIO pins (Port G)
    ccu = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
    pg_dat = read_u32(ccu, 0x8e8)
    print(f"6. Port G DAT (SDIO lines): 0x{pg_dat:08x} (PG0-PG5 bits: {(pg_dat & 0x3f):06b})")
    
if __name__ == '__main__':
    main()
