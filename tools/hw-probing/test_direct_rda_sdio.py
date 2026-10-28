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
    print("=" * 60)
    print("  DIRECT HARDWARE POWER & SDIO CMD5 PROBE")
    print("=" * 60)
    
    fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
    
    # 1. Enable RTC 32kHz clock fanout
    rtc = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)
    write_u32(rtc, 0x60, 1)
    losc = read_u32(rtc, 0x60)
    print(f"[1] RTC LOSC_OUT (0x01f00060) = 0x{losc:08x}")
    rtc.close()
    
    # 2. Configure Port L pins:
    # PL6=out, PL7=in_pullup, PL8=out, PL9=in_pullup, PL10=out, PL11=out
    rpio = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f02000)
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
    pull |= (1 << 14) | (1 << 18) # pullup PL7, PL9
    
    write_u32(rpio, base_l, cfg0)
    write_u32(rpio, base_l + 4, cfg1)
    write_u32(rpio, base_l + 0x1c, pull)
    
    # Step A: Power down / reset
    dat &= ~((1 << 6) | (1 << 8) | (1 << 10) | (1 << 11))
    write_u32(rpio, base_l + 0x10, dat)
    time.sleep(0.05)
    
    # Step B: Power up
    dat |= (1 << 6) | (1 << 10) | (1 << 11)
    write_u32(rpio, base_l + 0x10, dat)
    time.sleep(0.05)
    
    # Step C: Deassert reset
    dat |= (1 << 8)
    write_u32(rpio, base_l + 0x10, dat)
    time.sleep(0.1)
    
    dat_now = read_u32(rpio, base_l + 0x10)
    print(f"[2] Port L powered: DAT=0x{dat_now:08x} (PL6={bool(dat_now&(1<<6))}, PL8={bool(dat_now&(1<<8))}, PL11={bool(dat_now&(1<<11))})")
    print(f"    Host wake pins: PL7={bool(dat_now&(1<<7))}, PL9={bool(dat_now&(1<<9))}")
    rpio.close()
    
    # 3. Port G SDIO pins check
    ccu_pio = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
    pg_cfg0 = read_u32(ccu_pio, 0x8d8)
    pg_dat  = read_u32(ccu_pio, 0x8e8)
    pg_pull = read_u32(ccu_pio, 0x8f4)
    print(f"[3] Port G SDIO: CFG0=0x{pg_cfg0:08x}, DAT=0x{pg_dat:08x}, PULL=0x{pg_pull:08x}")
    
    # Ensure CCU MMC1 clock is enabled: 0x01c20064 bit 31=1, source=OSC24M (0), divider=0
    # 0x80000000
    write_u32(ccu_pio, 0x64, 0x80000000)
    # Also ungate bus clock for MMC1: 0x01c20060 bit 9
    bus_gate = read_u32(ccu_pio, 0x60) | (1 << 9)
    write_u32(ccu_pio, 0x60, bus_gate)
    # Ungate bus reset for MMC1: 0x01c202c0 bit 9
    bus_rst = read_u32(ccu_pio, 0x2c0) | (1 << 9)
    write_u32(ccu_pio, 0x2c0, bus_rst)
    print(f"[4] CCU: MMC1_CLK=0x{read_u32(ccu_pio, 0x64):08x}, BUS_GATE=0x{read_u32(ccu_pio, 0x60):08x}, BUS_RST=0x{read_u32(ccu_pio, 0x2c0):08x}")
    ccu_pio.close()
    
    # 4. MMC1 Controller (0x01c10000)
    mmc = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c10000)
    
    # Soft reset
    write_u32(mmc, 0x00, 0x7)
    time.sleep(0.02)
    
    # Set TMOUT = 0xffffffff
    write_u32(mmc, 0x08, 0xffffffff)
    # Set 1-bit width
    write_u32(mmc, 0x0c, 0x0)
    
    # Configure 400kHz clock (24MHz / (2 * 30) = 400kHz) -> divider = 29 (0x1d)
    # CLKCR: divider=29 (0x1d), cken=1 (bit 16), mask_data0=0
    # 0x0001011d
    write_u32(mmc, 0x04, 0x0001011d)
    # Update clock: START | UPCLK_ONLY | WAIT_PRE_OVER = 0x80202000
    write_u32(mmc, 0x18, 0x80202000)
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (read_u32(mmc, 0x18) & 0x80000000):
            break
        time.sleep(0.001)
    write_u32(mmc, 0x38, 0xffffffff) # clear RINT
    print(f"[5] MMC1 CLK configured: CLKCR=0x{read_u32(mmc, 0x04):08x}")
    
    # Send CMD0 with 74 clocks: START | SEND_INIT_SEQ | WAIT_PRE_OVER = 0x8000a000
    write_u32(mmc, 0x1c, 0)
    write_u32(mmc, 0x18, 0x8000a000)
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (read_u32(mmc, 0x18) & 0x80000000):
            break
        time.sleep(0.001)
    rint0 = read_u32(mmc, 0x38)
    write_u32(mmc, 0x38, 0xffffffff)
    print(f"[6] CMD0 (Init Seq): RINT=0x{rint0:08x}")
    time.sleep(0.02)
    
    # Send CMD5 (IO_SEND_OP_COND, arg=0)
    # START (bit 31) | WAIT_PRE_OVER (bit 13) | RESP_EXPIRE (bit 6) | CMD 5 (0x5) = 0x80002045
    write_u32(mmc, 0x1c, 0)
    write_u32(mmc, 0x18, 0x80002045)
    t0 = time.time()
    while time.time() - t0 < 0.5:
        if not (read_u32(mmc, 0x18) & 0x80000000):
            break
        time.sleep(0.001)
        
    rint5 = read_u32(mmc, 0x38)
    resp0 = read_u32(mmc, 0x20)
    status = read_u32(mmc, 0x3c)
    print(f"[7] CMD5 Result: RINT=0x{rint5:08x}, RESP0=0x{resp0:08x}, STATUS=0x{status:08x}")
    if rint5 & 0x4:
        print("    >>> SUCCESS! SDXC_COMMAND_DONE: Card responded to CMD5!")
        print(f"    >>> OCR response: 0x{resp0:08x}")
    if rint5 & 0x100:
        print("    -> SDXC_RESP_TIMEOUT (CMD line timed out)")
    if rint5 & 0x2:
        print("    -> SDXC_RESP_ERROR")
        
    mmc.close()
    os.close(fd)
    print("=" * 60)

if __name__ == '__main__':
    main()
