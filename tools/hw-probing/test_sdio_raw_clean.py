#!/usr/bin/env python3
import os
import mmap
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 1. RTC 32kHz Clock Fanout
rtc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()

# 2. Port L Power & Enable Lines
rpio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f02000)
base_l = 0xc00
cfg0 = struct.unpack('<I', rpio[base_l:base_l+4])[0]
cfg1 = struct.unpack('<I', rpio[base_l+4:base_l+8])[0]
# PL6, PL8, PL10, PL11 as outputs
cfg0 = (cfg0 & ~(0x7 << 24)) | (1 << 24) # PL6
cfg1 = (cfg1 & ~(0x7 << 0))  | (1 << 0)  # PL8
cfg1 = (cfg1 & ~(0x7 << 8))  | (1 << 8)  # PL10
cfg1 = (cfg1 & ~(0x7 << 12)) | (1 << 12) # PL11
rpio[base_l:base_l+4] = struct.pack('<I', cfg0)
rpio[base_l+4:base_l+8] = struct.pack('<I', cfg1)
dat = struct.unpack('<I', rpio[base_l+0x10:base_l+0x14])[0]
dat |= (1 << 6) | (1 << 8) | (1 << 10) | (1 << 11)
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', dat)
rpio.close()

# 3. Port G SDIO Pins (PG0-PG5 Function 2 = MMC1, Pull-ups active)
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
# PG CFG0: 0x8d8, DAT: 0x8e8, PULL: 0x8f4
pio[0x8d8:0x8dc] = struct.pack('<I', 0x77222222) # PG0-PG5 = func 2
pio[0x8f4:0x8f8] = struct.pack('<I', 0x00000555) # pull-up on PG0-PG5

# CCU MMC1 Bus clock & reset:
# 0x060 bit 9 = 1, 0x2c0 bit 9 = 1
bus_gate = struct.unpack('<I', pio[0x60:0x64])[0] | (1 << 9)
pio[0x60:0x64] = struct.pack('<I', bus_gate)
bus_rst = struct.unpack('<I', pio[0x2c0:0x2c4])[0] | (1 << 9)
pio[0x2c0:0x2c4] = struct.pack('<I', bus_rst)

# CCU MMC1 Module Clock: 0x08c
# Set 400kHz: gate=1, osc24M, P=2, M=14 -> 0x8022020e (sample=180, output=180)
pio[0x8c:0x90] = struct.pack('<I', 0x8022020e)
pio.close()

# 4. MMC1 Controller: 0x01c10000
mmc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c10000)

def r32(off):
    return struct.unpack('<I', mmc[off:off+4])[0]

def w32(off, val):
    mmc[off:off+4] = struct.pack('<I', val)

print("=== Direct MMC1 SDIO Test ===")

# Soft reset
w32(0x00, 0x7)
t0 = time.time()
while time.time() - t0 < 0.1:
    if (r32(0x00) & 0x7) == 0:
        break
    time.sleep(0.001)

# GCTRL: Enable interrupts & debounce
w32(0x00, 0x110) # INTERRUPT_ENABLE_BIT | DEBOUNCE_ENABLE_BIT
w32(0x08, 0xffffffff) # TMOUT
w32(0x0c, 0) # 1-bit width
w32(0x38, 0xffffffff) # clear RINTR

# Enable card clock: CLKCR = 0x00010000 (CARD_CLOCK_ON, divider=0)
w32(0x04, 0x00010000)
# Update clock to CIU
w32(0x18, 0x80202000) # START | UPCLK_ONLY | WAIT_PRE_OVER
t0 = time.time()
while time.time() - t0 < 0.2:
    if not (r32(0x18) & 0x80000000):
        break
    time.sleep(0.001)

print(f"  GCTRL=0x{r32(0x00):08x}, CLKCR=0x{r32(0x04):08x}, RINTR=0x{r32(0x38):08x}")

def send_cmd(opcode, arg, resp_type=0, init_seq=False):
    w32(0x38, 0xffffffff) # clear RINTR
    w32(0x1c, arg)
    
    cmd_val = 0x80000000 | (opcode & 0x3f) # START
    if init_seq:
        cmd_val |= (1 << 15) # SEND_INIT_SEQUENCE (74 clocks)
    if resp_type != 0:
        cmd_val |= (1 << 6) # RESP_EXPIRE
        if resp_type == 136:
            cmd_val |= (1 << 7) # LONG_RESPONSE
        if resp_type == 48: # standard 48-bit with CRC
            cmd_val |= (1 << 8) # CHECK_RESPONSE_CRC
        # R4 for SDIO CMD5 does not check CRC
    
    w32(0x18, cmd_val)
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (r32(0x18) & 0x80000000):
            break
        time.sleep(0.001)
    
    # Wait for completion or timeout in RINTR
    t0 = time.time()
    rintr = 0
    while time.time() - t0 < 0.5:
        rintr = r32(0x38)
        if rintr & 0x1ff: # any done or err
            break
        time.sleep(0.001)
    
    resp0 = r32(0x20)
    w32(0x38, rintr)
    return rintr, resp0

# 1. Send CMD0 with 74 clocks initialization sequence
rintr0, resp0 = send_cmd(0, 0, resp_type=0, init_seq=True)
print(f"  CMD0 (Init Sequence): RINTR=0x{rintr0:08x} (DONE={bool(rintr0 & 4)})")

time.sleep(0.05)

# 2. Send CMD5 (arg=0x00000000, probe OCR)
# R4 response: 48-bit response WITHOUT CRC
rintr5, resp5 = send_cmd(5, 0x00000000, resp_type=4)
print(f"  CMD5 (arg=0x00000000): RINTR=0x{rintr5:08x}, RESP0=0x{resp5:08x}")
if rintr5 & 4:
    print(f"    >>> CARD RESPONDED TO CMD5! OCR = 0x{resp5:08x}")
elif rintr5 & 0x100:
    print(f"    --- RESP_TIMEOUT (No response from card on CMD line)")
if rintr5 & 2:
    print(f"    --- RESP_ERROR")

time.sleep(0.05)

# 3. Send CMD5 (arg=0x00ff8000, request 3.3V)
rintr5_2, resp5_2 = send_cmd(5, 0x00ff8000, resp_type=4)
print(f"  CMD5 (arg=0x00ff8000): RINTR=0x{rintr5_2:08x}, RESP0=0x{resp5_2:08x}")
if rintr5_2 & 4:
    print(f"    >>> CARD RESPONDED! OCR = 0x{resp5_2:08x}")

mmc.close()
os.close(fd_mem)
