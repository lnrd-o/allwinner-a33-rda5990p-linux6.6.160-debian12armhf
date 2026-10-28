#!/usr/bin/env python3
import os
import mmap
import struct
import time
import termios

print("==================================================")
print("  RDA5990P HARDWARE RESET / WAKE & SDIO/BT PROBE  ")
print("==================================================")

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 1. RTC 32kHz Fanout (Internal RC Oscillator + LOSC_OUT)
rtc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)
rtc[0x00:0x04] = struct.pack('<I', (0x16aa << 16) | (1 << 15)) # Key + Internal RC
rtc[0x60:0x64] = struct.pack('<I', 1) # LOSC_OUT enable
rtc.close()
print("[1] RTC 32kHz LOSC_OUT confirmed active with internal RC oscillator.")

# 2. AXP223 RSB: Ensure all power rails active
rsb_page = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f03000)
base_rsb = 0x400

def read_rsb_u32(off):
    return struct.unpack('<I', rsb_page[base_rsb+off:base_rsb+off+4])[0]

def write_rsb_u32(off, val):
    rsb_page[base_rsb+off:base_rsb+off+4] = struct.pack('<I', val)

RTADDR = 0x2d

def rsb_write(reg, val):
    write_rsb_u32(0x10, reg)
    write_rsb_u32(0x1c, val)
    write_rsb_u32(0x30, RTADDR << 16)
    write_rsb_u32(0x2c, 0x4e)
    write_rsb_u32(0x00, 0x80)
    t0 = time.time()
    while time.time() - t0 < 0.1:
        st = read_rsb_u32(0x0c)
        if st & 0x1:
            write_rsb_u32(0x0c, st)
            return True
        if st & 0x2:
            write_rsb_u32(0x0c, st)
            return False
        time.sleep(0.001)
    return False

rsb_write(0x10, 0xff) # DCDC1..5, ALDO1..3 ON
rsb_write(0x12, 0xff) # DLDO1..4, ELDO1, ELDO3 ON
rsb_write(0x13, 0x87) # DCDC mode
rsb_write(0x15, 0x1a) # DLDO1 = 3.3V
rsb_write(0x16, 0x1a) # DLDO2 = 3.3V
rsb_write(0x90, 0x03) # LDO_IO0 ON (3.3V)
rsb_write(0x91, 0x1a)
rsb_write(0x92, 0x03) # LDO_IO1 ON (3.3V)
rsb_write(0x93, 0x1a)
rsb_page.close()
print("[2] AXP223 DLDO1/2 (3.3V) and LDO_IO0/1 (3.3V) locked ON.")

# 3. Port L Configuration
# PL00, PL01 are RSB -> PRESERVE THEM!
# PL02..PL11 -> Output
rpio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f02000)
base_l = 0xc00
cfg0 = struct.unpack('<I', rpio[base_l:base_l+4])[0]
cfg1 = struct.unpack('<I', rpio[base_l+4:base_l+8])[0]

# Preserve PL0, PL1 (bits 0..7) as func 2 (0x22)
# Set PL2..PL7 as output (func 1: 0x11111100)
cfg0 = (cfg0 & 0x000000ff) | 0x11111100
# Set PL8..PL11 as output (func 1: 0x00001111)
cfg1 = (cfg1 & 0xffff0000) | 0x00001111

rpio[base_l:base_l+4] = struct.pack('<I', cfg0)
rpio[base_l+4:base_l+8] = struct.pack('<I', cfg1)

def set_port_l(mask_high, mask_low):
    dat = struct.unpack('<I', rpio[base_l+0x10:base_l+0x14])[0]
    dat = (dat | mask_high) & ~mask_low
    rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', dat)
    return dat

# 4. Port G Configuration (MMC1: PG0..5, UART1: PG6..9)
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
# PG CFG0: 0x8d8, PG CFG1: 0x8dc
pio[0x8d8:0x8dc] = struct.pack('<I', 0x22222222) # PG0..PG7 = func 2
pio[0x8dc:0x8e0] = struct.pack('<I', 0x00000022) # PG8, PG9 = func 2
pio[0x8f4:0x8f8] = struct.pack('<I', 0x000ff555) # Pull-ups on PG0..PG9

# CCU MMC1 Bus Clock & Reset
pio[0x60:0x64] = struct.pack('<I', struct.unpack('<I', pio[0x60:0x64])[0] | (1 << 9))
pio[0x2c0:0x2c4] = struct.pack('<I', struct.unpack('<I', pio[0x2c0:0x2c4])[0] | (1 << 9))
# CCU MMC1 Mod Clock @ 400kHz (0x8022020e)
pio[0x8c:0x90] = struct.pack('<I', 0x8022020e)

# CCU UART1 Clock & Reset
pio[0x6c:0x70] = struct.pack('<I', struct.unpack('<I', pio[0x6c:0x70])[0] | (1 << 17))
pio[0x2d0:0x2d4] = struct.pack('<I', struct.unpack('<I', pio[0x2d0:0x2d4])[0] | (1 << 17))
pio.close()
print("[3] Port G MMC1 & UART1 muxed, clocks ungated.")

# 5. MMC1 Controller Init
mmc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c10000)

def mmc_r32(off): return struct.unpack('<I', mmc[off:off+4])[0]
def mmc_w32(off, val): mmc[off:off+4] = struct.pack('<I', val)

def reset_mmc1():
    mmc_w32(0x00, 0x7)
    t0 = time.time()
    while time.time() - t0 < 0.1:
        if (mmc_r32(0x00) & 0x7) == 0: break
        time.sleep(0.001)
    mmc_w32(0x00, 0x110)
    mmc_w32(0x08, 0xffffffff) # Max timeout
    mmc_w32(0x0c, 0) # 1-bit bus
    mmc_w32(0x38, 0xffffffff)
    mmc_w32(0x04, 0x00010000) # Enable card clock
    mmc_w32(0x18, 0x80202000) # Update clock
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (mmc_r32(0x18) & 0x80000000): break
        time.sleep(0.001)

def send_mmc_cmd(cmd, arg, resp_type=0, init_seq=False):
    mmc_w32(0x38, 0xffffffff) # Clear RINT
    mmc_w32(0x1c, arg)        # 0x1c is ARG
    val = 0x80000000 | (cmd & 0x3f) # START | CMD
    if init_seq:
        val |= (1 << 15)      # SEND_INIT_SEQUENCE (80 clocks)
    if resp_type != 0:
        val |= (1 << 6)       # RESP_EXPIRE
        if resp_type == 136: val |= (1 << 7)
        if resp_type == 48:  val |= (1 << 8)
    mmc_w32(0x18, val)        # 0x18 is CMD!
    t0 = time.time()
    while time.time() - t0 < 0.3:
        rintr = mmc_r32(0x38) # 0x38 is RINT
        if rintr & 0x100:     # Timeout (bit 8)
            return False, rintr, 0
        if rintr & 0x004:     # Command Done (bit 2)
            return True, rintr, mmc_r32(0x20) # 0x20 is RESP0!
        time.sleep(0.001)
    return False, mmc_r32(0x38), 0

def check_bt_uart():
    try:
        fd_tty = os.open('/dev/ttyS1', os.O_RDWR | os.O_NONBLOCK | os.O_NOCTTY)
        # Configure 115200 8N1 raw
        attrs = termios.tcgetattr(fd_tty)
        attrs[0] = 0 # iflag
        attrs[1] = 0 # oflag
        attrs[2] = termios.B115200 | termios.CS8 | termios.CREAD | termios.CLOCAL # cflag
        attrs[3] = 0 # lflag
        termios.tcsetattr(fd_tty, termios.TCSANOW, attrs)
        # Flush
        termios.tcflush(fd_tty, termios.TCIOFLUSH)
        # Send HCI Reset: 01 03 0C 00
        os.write(fd_tty, b'\x01\x03\x0c\x00')
        time.sleep(0.05)
        try:
            resp = os.read(fd_tty, 64)
            os.close(fd_tty)
            if resp:
                return True, resp.hex()
        except BlockingIOError:
            pass
        os.close(fd_tty)
    except Exception as e:
        return False, str(e)
    return False, None

# Test different Reset & Wake pin permutations
test_cases = [
    ("PL2=LOW (Reset), PL3=HIGH, PL4=HIGH", (1<<3)|(1<<4), (1<<2)),
    ("PL2=HIGH (Released), PL3=HIGH, PL4=HIGH", (1<<2)|(1<<3)|(1<<4), 0),
    ("ALL PL2..PL11 HIGH", 0x00000ffc, 0),
    ("PL2=HIGH, PL3=LOW, PL4=HIGH", (1<<2)|(1<<4), (1<<3)),
    ("PL2=HIGH, PL3=HIGH, PL4=LOW", (1<<2)|(1<<3), (1<<4)),
    ("PL2=HIGH, PL4 pulse (toggle wake)", (1<<2)|(1<<3), 0)
]

for label, mask_hi, mask_lo in test_cases:
    print(f"\n--- Testing state: {label} ---")
    set_port_l(mask_hi, mask_lo)
    time.sleep(0.05)
    
    # Check Bluetooth HCI
    bt_ok, bt_data = check_bt_uart()
    print(f"  Bluetooth /dev/ttyS1 HCI Reset: {'REPLY: ' + bt_data if bt_ok else 'No reply'}")
    
    # Check SDIO
    reset_mmc1()
    # 1. 80-clock init sequence with CMD0
    ok0, r0, resp0 = send_mmc_cmd(0, 0, resp_type=0, init_seq=True)
    # 2. CMD5 inquiry
    ok5, r5, resp5 = send_mmc_cmd(5, 0x00000000, resp_type=4)
    print(f"  SDIO CMD5 arg=0: ok={ok5}, RINTR=0x{r5:08x}, RESP0=0x{resp5:08x}")
    if resp5 != 0 or ok5:
        print(f"  *** SUCCESS! SDIO Device Responded! RESP0 = 0x{resp5:08x} ***")
        break
    # 3. CMD5 voltage window
    ok5_v, r5_v, resp5_v = send_mmc_cmd(5, 0x00ff8000, resp_type=4)
    if resp5_v != 0 or ok5_v:
        print(f"  *** SUCCESS! SDIO Device Responded! RESP0 = 0x{resp5_v:08x} ***")
        break

rpio.close()
mmc.close()
os.close(fd_mem)
print("\n=== Probe complete ===")
