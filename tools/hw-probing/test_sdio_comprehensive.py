#!/usr/bin/env python3
import os
import mmap
import struct
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# RTC 32k
rtc = mmap.mmap(fd_mem, 4096, offset=0x01f00000)
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()

# Port L: PL6, PL8, PL10, PL11 out high
rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base_l = 0xc00
cfg0 = (struct.unpack('<I', rpio[base_l:base_l+4])[0] & ~(0x7 << 24)) | (1 << 24)
cfg1 = (struct.unpack('<I', rpio[base_l+4:base_l+8])[0] & ~0x7007) | 0x1001
rpio[base_l:base_l+4] = struct.pack('<I', cfg0)
rpio[base_l+4:base_l+8] = struct.pack('<I', cfg1)
dat = struct.unpack('<I', rpio[base_l+0x10:base_l+0x14])[0] | (1 << 6) | (1 << 8) | (1 << 10) | (1 << 11)
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', dat)

# Port G: PG0-PG5 MMC1
pio = mmap.mmap(fd_mem, 4096, offset=0x01c20000)
pio[0x8d8:0x8dc] = struct.pack('<I', 0x77222222)
pio[0x8f4:0x8f8] = struct.pack('<I', 0x00000555)

# Ungate bus clock & reset
pio[0x60:0x64] = struct.pack('<I', struct.unpack('<I', pio[0x60:0x64])[0] | (1 << 9))
pio[0x2c0:0x2c4] = struct.pack('<I', struct.unpack('<I', pio[0x2c0:0x2c4])[0] | (1 << 9))

# MMC1 Controller
mmc = mmap.mmap(fd_mem, 4096, offset=0x01c10000)

def r32(off):
    return struct.unpack('<I', mmc[off:off+4])[0]

def w32(off, val):
    mmc[off:off+4] = struct.pack('<I', val)

def set_frequency(freq_khz, sample_deg=180, output_deg=180):
    sample_bits = sample_deg // 90
    output_bits = output_deg // 90
    
    # Calculate P and M for 24MHz
    # freq = 24000 / ((1 << p) * (m + 1))
    if freq_khz == 400:
        p, m = 2, 14 # 24000 / (4 * 15) = 400
    elif freq_khz == 200:
        p, m = 3, 14 # 24000 / (8 * 15) = 200
    elif freq_khz == 100:
        p, m = 3, 29 # 24000 / (8 * 30) = 100
        # M is only 4 bits (0..15)! So for 100kHz, use internal divider in CLKCR
        p, m = 3, 14 # 200kHz from CCU, then div by 2 in CLKCR
    elif freq_khz == 50:
        p, m = 3, 14 # 200kHz from CCU, div by 4 in CLKCR
    else:
        p, m = 2, 14
        
    ccu_val = 0x80000000 | (sample_bits << 20) | (p << 16) | (output_bits << 8) | (m & 0xf)
    pio[0x8c:0x90] = struct.pack('<I', ccu_val)
    
    # Internal divider in CLKCR
    clkcr_div = 0
    if freq_khz == 100:
        clkcr_div = 1 # div by 2
    elif freq_khz == 50:
        clkcr_div = 2 # div by 4
        
    w32(0x04, 0x00010000 | clkcr_div) # CARD_CLOCK_ON
    w32(0x18, 0x80202000) # update clock
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (r32(0x18) & 0x80000000):
            break
        time.sleep(0.001)

def send_cmd(opcode, arg, resp_type=0, init_seq=False):
    w32(0x38, 0xffffffff) # clear RINTR
    w32(0x1c, arg)
    cmd_val = 0x80000000 | (opcode & 0x3f)
    if init_seq:
        cmd_val |= (1 << 15)
    if resp_type != 0:
        cmd_val |= (1 << 6)
        if resp_type == 136:
            cmd_val |= (1 << 7)
        if resp_type == 48:
            cmd_val |= (1 << 8)
    w32(0x18, cmd_val)
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (r32(0x18) & 0x80000000):
            break
        time.sleep(0.001)
    
    t0 = time.time()
    rintr = 0
    while time.time() - t0 < 0.3:
        rintr = r32(0x38)
        if rintr & 0x1ff:
            break
        time.sleep(0.001)
    resp0 = r32(0x20)
    w32(0x38, rintr)
    return rintr, resp0

print("=== Comprehensive SDIO Frequency & Phase Test ===")

# Reset MMC controller
w32(0x00, 0x7)
time.sleep(0.02)
w32(0x00, 0x110)
w32(0x08, 0xffffffff)
w32(0x0c, 0)

found = False
for freq in [400, 200, 100, 50]:
    for sample in [180, 0, 90, 270]:
        for output in [180, 0]:
            set_frequency(freq, sample, output)
            
            # Pulse reset pins (PL11=0 -> 1, PL6=0 -> 1, PL8=0 -> 1)
            # Power cycle the chip cleanly while clock is already running!
            d = struct.unpack('<I', rpio[base_l+0x10:base_l+0x14])[0]
            d &= ~((1 << 6) | (1 << 8) | (1 << 11))
            rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', d)
            time.sleep(0.01)
            d |= (1 << 11) | (1 << 6) | (1 << 8)
            rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', d)
            time.sleep(0.05) # wait 50ms for PLL lock
            
            # Send CMD0 with init sequence
            send_cmd(0, 0, init_seq=True)
            time.sleep(0.01)
            
            # Send CMD5 arg=0
            rintr, resp = send_cmd(5, 0, resp_type=4)
            has_done = bool(rintr & 0x4)
            has_to = bool(rintr & 0x100)
            
            if has_done and not has_to:
                print(f"\n>>> [SUCCESS!] Freq={freq}kHz, Sample={sample}deg, Output={output}deg: RESP0=0x{resp:08x}, RINTR=0x{rintr:08x}")
                found = True
                break
        if found:
            break
    if found:
        break
    print(f"  Freq {freq}kHz: all phases timed out")

if not found:
    print("Scan finished: No response on CMD5 across frequencies and phases.")

mmc.close()
pio.close()
rpio.close()
os.close(fd_mem)
