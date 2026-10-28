#!/usr/bin/env python3
import mmap
import os
import struct
import sys
import time

def read_u32(mm, offset):
    return struct.unpack('<I', mm[offset:offset+4])[0]

def write_u32(mm, offset, val):
    mm[offset:offset+4] = struct.pack('<I', val)

def main():
    print("=" * 60)
    print("       A33 ET_F900 RDA5990 HARDWARE DIAGNOSTIC")
    print("=" * 60)
    
    fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
    
    # 1. RTC (0x01f00000)
    rtc_mmap = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)
    losc = read_u32(rtc_mmap, 0x60)
    print(f"[RTC] LOSC_OUT (0x01f00060): 0x{losc:08x} (bit 0 = 32k out: {losc & 1})")
    
    # 2. Port L (0x01f02c00) -> base 0x01f02000 offset 0xc00
    r_cpucfg = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f02000)
    pl_cfg0 = read_u32(r_cpucfg, 0xc00 + 0x00)
    pl_cfg1 = read_u32(r_cpucfg, 0xc00 + 0x04)
    pl_dat  = read_u32(r_cpucfg, 0xc00 + 0x10)
    pl_pull = read_u32(r_cpucfg, 0xc00 + 0x1c)
    print(f"[Port L] CFG0: 0x{pl_cfg0:08x}, CFG1: 0x{pl_cfg1:08x}, DAT: 0x{pl_dat:08x}, PULL: 0x{pl_pull:08x}")
    # PL6: (pl_cfg0 >> 24) & 7, PL7: (pl_cfg0 >> 28) & 7
    # PL8: (pl_cfg1 >> 0) & 7, PL9: (pl_cfg1 >> 4) & 7, PL10: (pl_cfg1 >> 8) & 7, PL11: (pl_cfg1 >> 12) & 7
    print(f"  PL06 (wl_regon):   func={(pl_cfg0 >> 24) & 7}, dat={(pl_dat >> 6) & 1}")
    print(f"  PL07 (wl_hostwake):func={(pl_cfg0 >> 28) & 7}, dat={(pl_dat >> 7) & 1}")
    print(f"  PL08 (bt_rst_n):   func={(pl_cfg1 >> 0) & 7},  dat={(pl_dat >> 8) & 1}")
    print(f"  PL09 (bt_hostwake):func={(pl_cfg1 >> 4) & 7},  dat={(pl_dat >> 9) & 1}")
    print(f"  PL10 (bt_wake):    func={(pl_cfg1 >> 8) & 7},  dat={(pl_dat >> 10) & 1}")
    print(f"  PL11 (chip_en):    func={(pl_cfg1 >> 12) & 7}, dat={(pl_dat >> 11) & 1}")
    
    # 3. Port G (0x01c20800) -> base 0x01c20000 offset 0x800
    gpio_mmap = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
    # Port G: offset in pinctrl: CFG0 is at 0x800 + 0xd8 = 0x8d8
    pg_cfg0 = read_u32(gpio_mmap, 0x8d8)
    pg_dat  = read_u32(gpio_mmap, 0x8e8)
    pg_pull = read_u32(gpio_mmap, 0x8f4)
    print(f"[Port G (SDIO)] CFG0: 0x{pg_cfg0:08x}, DAT: 0x{pg_dat:08x}, PULL: 0x{pg_pull:08x}")
    # PG0: clk, PG1: cmd, PG2: d0, PG3: d1, PG4: d2, PG5: d3 (func 2 = mmc1)
    for pin in range(6):
        fn = (pg_cfg0 >> (pin * 4)) & 7
        d = (pg_dat >> pin) & 1
        pu = (pg_pull >> (pin * 2)) & 3
        print(f"  PG{pin}: func={fn} (is_mmc1={fn==2}), dat={d}, pull={pu}")
        
    # 4. CCU MMC1 clock (0x01c20064)
    mmc1_clk = read_u32(gpio_mmap, 0x64)
    print(f"[CCU] MMC1_CLK (0x01c20064): 0x{mmc1_clk:08x} (gate={bool(mmc1_clk & (1<<31))})")
    
    # 5. MMC1 controller (0x01c10000)
    mmc1_mmap = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c10000)
    gctrl = read_u32(mmc1_mmap, 0x00)
    clkcr = read_u32(mmc1_mmap, 0x04)
    status = read_u32(mmc1_mmap, 0x3c)
    rint = read_u32(mmc1_mmap, 0x38)
    print(f"[MMC1 Register] GCTRL: 0x{gctrl:08x}, CLKCR: 0x{clkcr:08x}, STATUS: 0x{status:08x}, RINT: 0x{rint:08x}")
    
    # 6. Regulators
    print("[Regulators]")
    for r in sorted(os.listdir('/sys/class/regulator')):
        p = os.path.join('/sys/class/regulator', r)
        try:
            name = open(os.path.join(p, 'name')).read().strip()
            state = open(os.path.join(p, 'state')).read().strip() if os.path.exists(os.path.join(p, 'state')) else 'unknown'
            microvolts = open(os.path.join(p, 'microvolts')).read().strip() if os.path.exists(os.path.join(p, 'microvolts')) else '0'
            if any(k in name.lower() for k in ['wifi', 'dldo', 'aldo']):
                mv = int(microvolts) / 1000000.0 if microvolts.isdigit() else 0
                print(f"  {r}: {name:<25} state={state:<8} {mv:.2f}V")
        except Exception as e:
            pass
            
    print("=" * 60)

if __name__ == '__main__':
    main()
