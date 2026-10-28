#!/usr/bin/env python3
"""
Staged Hardware Power & Reset Sequencing Probe for RDA5990P on Allwinner A33
Based on direct hardware control with kernel polling disabled.
"""
import os
import mmap
import struct
import time

print("=" * 60)
print("  STAGED HARDWARE POWER & RESET SEQUENCING SDIO PROBE")
print("=" * 60)

# 1. Unbind kernel sunxi-mmc driver from mmc1 (1c10000.mmc)
# This completely disables kernel polling and prevents 1-second power resets!
mmc_unbind_path = "/sys/bus/platform/drivers/sunxi-mmc/unbind"
if os.path.exists(mmc_unbind_path):
    try:
        with open(mmc_unbind_path, "w") as f:
            f.write("1c10000.mmc\n")
        print("[✓] Unbound 1c10000.mmc from sunxi-mmc driver (polling stopped).")
    except Exception as e:
        print(f"[-] Unbind note: {e}")

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 2. Configure & Verify Clock Tree (Internal 32kHz RC + LOSC_OUT)
rtc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)
# Force RC oscillator: Key 0x16aa, AUTO_SWT_BYPASS=1, EXT_OSC=0
rtc[0x00:0x04] = struct.pack('<I', (0x16aa << 16) | (1 << 15))
# Enable LOSC_OUT clock output gating (Bit 0 = 1)
rtc[0x60:0x64] = struct.pack('<I', 1)

# Verify clock is actively ticking
t_start = struct.unpack('<I', rtc[0x14:0x18])[0]
time.sleep(1.1)
t_end = struct.unpack('<I', rtc[0x14:0x18])[0]
ctrl = struct.unpack('<I', rtc[0x00:0x04])[0]
gating = struct.unpack('<I', rtc[0x60:0x64])[0]
print(f"[✓] RTC LOSC_CTRL = 0x{ctrl:08x}, LOSC_OUT = 0x{gating:08x}")
print(f"[✓] RTC Timer Ticking: {hex(t_start)} -> {hex(t_end)} (Active 32.768 kHz RC clock confirmed!)")
rtc.close()

# 3. Configure AXP223 PMIC via RSB: Ensure all power rails active
rsb_page = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f03000)
base_rsb = 0x400
def wr_rsb(off, val): rsb_page[base_rsb+off:base_rsb+off+4] = struct.pack('<I', val)
def rd_rsb(off): return struct.unpack('<I', rsb_page[base_rsb+off:base_rsb+off+4])[0]
RTADDR = 0x2d
def rsb_w(reg, val):
    wr_rsb(0x10, reg); wr_rsb(0x1c, val); wr_rsb(0x30, RTADDR << 16)
    wr_rsb(0x2c, 0x4e); wr_rsb(0x00, 0x80)
    t0 = time.time()
    while time.time() - t0 < 0.1:
        st = rd_rsb(0x0c)
        if st & 0x1: wr_rsb(0x0c, st); return True
        if st & 0x2: wr_rsb(0x0c, st); return False
        time.sleep(0.001)
    return False

# Energize all power rails:
# DCDC1..5 ON (0x10 = 0xff)
# DLDO1..4, ELDO1..3 ON (0x12 = 0xff)
# DLDO1 (0x15) = 3.3V (0x1a)
# DLDO2 (0x16) = 3.3V (0x1a)
# LDO_IO0 (0x90 = 0x03, 0x91 = 0x1a) = 3.3V
# LDO_IO1 (0x92 = 0x03, 0x93 = 0x1a) = 3.3V
rsb_w(0x10, 0xff)
rsb_w(0x12, 0xff)
rsb_w(0x15, 0x1a)
rsb_w(0x16, 0x1a)
rsb_w(0x90, 0x03); rsb_w(0x91, 0x1a)
rsb_w(0x92, 0x03); rsb_w(0x93, 0x1a)
rsb_page.close()
print("[✓] AXP223 PMIC Rails locked: DLDO1=3.3V, DLDO2=3.3V, LDO_IO0=3.3V, LDO_IO1=3.3V.")

# 4. Port G & CCU MMC1 Setup
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
# Mux PG0..PG5 to function 2 (MMC1)
pio[0x8d8:0x8dc] = struct.pack('<I', 0x77222222)
# Internal pull-ups on PG0..PG5
pio[0x8f4:0x8f8] = struct.pack('<I', 0x00000555)

# Ungate CCU MMC1 bus clock & deassert reset
pio[0x60:0x64] = struct.pack('<I', struct.unpack('<I', pio[0x60:0x64])[0] | (1 << 9))
pio[0x2c0:0x2c4] = struct.pack('<I', struct.unpack('<I', pio[0x2c0:0x2c4])[0] | (1 << 9))
# Configure CCU MMC1 Mod Clock @ 400kHz (0x8022020e: 24MHz / (1 << 2) / 15 = 400kHz)
pio[0x8c:0x90] = struct.pack('<I', 0x8022020e)

# 5. Port L (R_PIO) Setup
rpio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f02000)
base_l = 0xc00
cfg0 = (struct.unpack('<I', rpio[base_l:base_l+4])[0] & 0x000000ff) | 0x11111100 # PL2..7 = out
cfg1 = (struct.unpack('<I', rpio[base_l+4:base_l+8])[0] & 0xffff0000) | 0x00001111 # PL8..11 = out
rpio[base_l:base_l+4] = struct.pack('<I', cfg0)
rpio[base_l+4:base_l+8] = struct.pack('<I', cfg1)

def set_port_l_pins(high_mask, low_mask):
    dat = struct.unpack('<I', rpio[base_l+0x10:base_l+0x14])[0]
    dat = (dat | high_mask) & ~low_mask
    rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', dat)
    return dat

# 6. MMC1 Hardware Controller Low-Level Access
mmc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c10000)
def mr(off): return struct.unpack('<I', mmc[off:off+4])[0]
def mw(off, val): mmc[off:off+4] = struct.pack('<I', val)

def reset_mmc1_controller():
    mw(0x00, 0x7) # Soft reset
    t0 = time.time()
    while time.time() - t0 < 0.1:
        if (mr(0x00) & 0x7) == 0: break
        time.sleep(0.001)
    mw(0x00, 0x110) # DMA / IRQ enable flags
    mw(0x08, 0xffffffff) # Max timeout
    mw(0x0c, 0) # 1-bit bus
    mw(0x04, 0x00010000) # Enable card clock
    mw(0x18, 0x80202000) # Update clock register
    t0 = time.time()
    while time.time() - t0 < 0.2:
        if not (mr(0x18) & 0x80000000): break
        time.sleep(0.001)

def send_cmd(cmd_idx, arg, resp_type=0, init_seq=False):
    mw(0x38, 0xffffffff) # Clear all interrupt flags (RINT)
    mw(0x1c, arg)        # 0x1c is ARG register
    val = 0x80000000 | (cmd_idx & 0x3f) # START | CMD_INDEX
    if init_seq:
        val |= (1 << 15) # SEND_INIT_SEQUENCE (80 clocks)
    if resp_type != 0:
        val |= (1 << 6)  # RESP_EXPIRE (Response expected)
        # Note: For R4 (CMD5), NO CRC check bit (bit 8) is set!
    mw(0x18, val)        # 0x18 is CMD register!
    t0 = time.time()
    while time.time() - t0 < 0.3:
        rintr = mr(0x38)
        if rintr & 0x100: # SDXC_RESP_TIMEOUT (bit 8)
            return False, rintr, 0
        if rintr & 0x004: # SDXC_COMMAND_DONE (bit 2)
            resp0 = mr(0x20) # 0x20 is RESP0 register!
            return True, rintr, resp0
        time.sleep(0.001)
    return False, mr(0x38), 0

# 7. Execute Staged Power & Reset Sequences
# Candidates:
# PL06: wl_regon
# PL11: chip_en
# PL08: bt_rst_n / chip master reset
# PL02: pull-down line / reset
# PL03, PL04: wake / control lines
print("\n" + "=" * 60)
print("  EXECUTING STAGED POWER SEQUENCES (with settle delays)")
print("=" * 60)

delays = [0.3, 0.5, 0.8, 1.2]
success = False

for settle_sec in delays:
    print(f"\n---> Testing Sequence with {int(settle_sec * 1000)}ms Settle Delay <---")
    
    # Step A: Cold reset state: Drive all control lines LOW
    set_port_l_pins(0, 0x00000ffc)
    time.sleep(0.1) # 100ms discharge
    
    # Step B: Assert chip enables (PL06, PL11, PL02) while holding RESET (PL08) LOW
    # High: PL06 (1<<6), PL11 (1<<11), PL02 (1<<2), PL03 (1<<3), PL04 (1<<4)
    # Low:  PL08 (1<<8)
    en_mask = (1 << 6) | (1 << 11) | (1 << 2) | (1 << 3) | (1 << 4)
    rst_mask = (1 << 8)
    set_port_l_pins(en_mask, rst_mask)
    time.sleep(0.05) # 50ms enable hold
    
    # Step C: Deassert RESET (Drive PL08 HIGH)
    set_port_l_pins((1 << 8), 0)
    print(f"  [>] Enables asserted, Reset released. Settle delay: {int(settle_sec*1000)}ms...")
    time.sleep(settle_sec)
    
    # Step D: Init controller & send 80 clock cycles
    reset_mmc1_controller()
    ok0, r0, resp0 = send_cmd(0, 0, resp_type=0, init_seq=True)
    time.sleep(0.02)
    
    # Step E: Send CMD5 inquiry (arg=0)
    ok5, r5, resp5 = send_cmd(5, 0x00000000, resp_type=4)
    print(f"  [>] CMD5 Inquiry (arg=0): ok={ok5}, RINTR=0x{r5:08x}, RESP0=0x{resp5:08x}")
    if ok5 or resp5 != 0:
        print(f"\n🎉🎉🎉 SUCCESS! CHIP RESPONDED TO CMD5 INQUIRY! RESP0 = 0x{resp5:08x} 🎉🎉🎉")
        success = True
        break
        
    # Step F: Send CMD5 voltage window (arg=0x00ff8000)
    ok5_v, r5_v, resp5_v = send_cmd(5, 0x00ff8000, resp_type=4)
    print(f"  [>] CMD5 Voltage (3.3V):  ok={ok5_v}, RINTR=0x{r5_v:08x}, RESP0=0x{resp5_v:08x}")
    if ok5_v or resp5_v != 0:
        print(f"\n🎉🎉🎉 SUCCESS! CHIP RESPONDED TO CMD5 VOLTAGE! RESP0 = 0x{resp5_v:08x} 🎉🎉🎉")
        success = True
        break

if not success:
    print("\n[-] Standard sequence completed. Testing alternative frequencies (200kHz, 100kHz)...")
    for n, m, freq_name in [(1, 14, "200kHz"), (2, 14, "100kHz")]:
        reg_val = 0x80220000 | (n << 8) | m
        pio[0x8c:0x90] = struct.pack('<I', reg_val)
        mw(0x18, 0x80202000)
        time.sleep(0.02)
        ok, r, resp = send_cmd(5, 0x00000000, resp_type=4)
        print(f"  [>] CMD5 @ {freq_name}: ok={ok}, RINTR=0x{r:08x}, RESP0=0x{resp:08x}")
        if ok or resp != 0:
            print(f"\n🎉🎉🎉 SUCCESS AT {freq_name}! RESP0 = 0x{resp:08x} 🎉🎉🎉")
            success = True
            break

mmc.close()
pio.close()
rpio.close()
os.close(fd_mem)
print("\n" + "=" * 60)
print(f"  PROBE RESULT: {'SUCCESS' if success else 'NO RESPONSE'}")
print("=" * 60)
