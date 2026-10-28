import os, sys, time, mmap, struct, fcntl

print("==================================================")
print("  ENERGIZING CHIP & SCANNING ALL I2C CANDIDATES")
print("==================================================")

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 1. 32kHz Clock
rtc = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f00000)
rtc[0x00:0x04] = struct.pack('<I', (0x16aa << 16) | (1 << 15))
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()

# 2. PMIC Rails via RSB
rsb = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f03000)
def rsb_w(reg, val):
    rsb[0x410:0x414] = struct.pack('<I', reg)
    rsb[0x41c:0x420] = struct.pack('<I', val)
    rsb[0x430:0x434] = struct.pack('<I', 0x2d << 16)
    rsb[0x42c:0x430] = struct.pack('<I', 0x4e)
    rsb[0x400:0x404] = struct.pack('<I', 0x80)
    t0 = time.time()
    while time.time() - t0 < 0.05:
        st = struct.unpack('<I', rsb[0x40c:0x410])[0]
        if st & 0x1: rsb[0x40c:0x410] = struct.pack('<I', st); return True
        if st & 0x2: rsb[0x40c:0x410] = struct.pack('<I', st); return False
        time.sleep(0.001)
    return False

rsb_w(0x10, 0xff) # DCDC 1..5 ON
rsb_w(0x12, 0xff) # LDOs ON
rsb_w(0x15, 0x1a) # DLDO1 = 3.3V
rsb_w(0x16, 0x1a) # DLDO2 = 3.3V
rsb_w(0x90, 0x03); rsb_w(0x91, 0x1a) # LDO_IO0 = 3.3V
rsb_w(0x92, 0x03); rsb_w(0x93, 0x1a) # LDO_IO1 = 3.3V
rsb.close()
print("[+] Power rails locked at 3.3V and 32kHz clock active.")

# 3. Port L Enables & Reset
rpio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01f02000)
base_l = 0xc00
# Configure PL2..PL11 as output
rpio[base_l:base_l+4] = struct.pack('<I', 0x11111100)
rpio[base_l+4:base_l+8] = struct.pack('<I', 0x00001111)

# Cold discharge: all low
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', 0)
time.sleep(0.1)

# Assert Enables (PL06, PL11, PL02, PL03, PL04) while holding Reset (PL08) LOW
en_mask = (1 << 6) | (1 << 11) | (1 << 2) | (1 << 3) | (1 << 4)
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', en_mask)
time.sleep(0.05)

# Release Reset (PL08) HIGH
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', en_mask | (1 << 8))
print("[+] Chip enabled and reset released. Settle 200ms...")
time.sleep(0.2)
rpio.close()

# 4. Check hardware /dev/i2c-0 and /dev/i2c-1 with powered chip
I2C_SLAVE = 0x0703
for bus_id in [0, 1]:
    dev_path = f"/dev/i2c-{bus_id}"
    try:
        fd = os.open(dev_path, os.O_RDWR)
        found = []
        for addr in range(0x08, 0x78):
            try:
                fcntl.ioctl(fd, I2C_SLAVE, addr)
                os.write(fd, b'\x00')
                found.append(f"0x{addr:02x}")
            except Exception:
                pass
        os.close(fd)
        print(f"[+] Responding addresses on {dev_path}: {found}")
    except Exception as e:
        print(f"[-] Error on {dev_path}: {e}")

# 5. Check PB02 / PB03 bit-bang I2C
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
base = 0x800
# Pull-ups on PB2 and PB3
pull = (struct.unpack('<I', pio[base+0x44:base+0x48])[0] & ~0x000000f0) | 0x00000050
pio[base+0x44:base+0x48] = struct.pack('<I', pull)

def set_scl(val):
    cfg = struct.unpack('<I', pio[base+0x24:base+0x28])[0]
    if val:
        cfg = cfg & ~(7 << 8)
        pio[base+0x24:base+0x28] = struct.pack('<I', cfg)
    else:
        dat = struct.unpack('<I', pio[base+0x34:base+0x38])[0] & ~(1 << 2)
        pio[base+0x34:base+0x38] = struct.pack('<I', dat)
        cfg = (cfg & ~(7 << 8)) | (1 << 8)
        pio[base+0x24:base+0x28] = struct.pack('<I', cfg)

def set_sda(val):
    cfg = struct.unpack('<I', pio[base+0x24:base+0x28])[0]
    if val:
        cfg = cfg & ~(7 << 12)
        pio[base+0x24:base+0x28] = struct.pack('<I', cfg)
    else:
        dat = struct.unpack('<I', pio[base+0x34:base+0x38])[0] & ~(1 << 3)
        pio[base+0x34:base+0x38] = struct.pack('<I', dat)
        cfg = (cfg & ~(7 << 12)) | (1 << 12)
        pio[base+0x24:base+0x28] = struct.pack('<I', cfg)

def get_sda():
    return (struct.unpack('<I', pio[base+0x34:base+0x38])[0] >> 3) & 1

def i2c_delay():
    time.sleep(0.00005)

def i2c_start():
    set_sda(1); set_scl(1); i2c_delay()
    set_sda(0); i2c_delay()
    set_scl(0); i2c_delay()

def i2c_stop():
    set_sda(0); i2c_delay()
    set_scl(1); i2c_delay()
    set_sda(1); i2c_delay()

def i2c_write_byte(b):
    for i in range(8):
        bit = (b >> (7 - i)) & 1
        set_sda(bit); i2c_delay()
        set_scl(1); i2c_delay()
        set_scl(0); i2c_delay()
    set_sda(1); i2c_delay()
    set_scl(1); i2c_delay()
    ack = (get_sda() == 0)
    set_scl(0); i2c_delay()
    return ack

set_scl(1); set_sda(1); time.sleep(0.01)
dat = struct.unpack('<I', pio[base+0x34:base+0x38])[0]
print(f"PB2/PB3 idle: SCL={(dat>>2)&1}, SDA={(dat>>3)&1}")

found_bb = []
for addr in range(0x08, 0x78):
    i2c_start()
    ack = i2c_write_byte((addr << 1) | 0)
    i2c_stop()
    if ack:
        found_bb.append(f"0x{addr:02x}")

print(f"PB02/PB03 Bit-Bang Results: {found_bb}")

# Try swapping SCL and SDA (PB03=SCL, PB02=SDA) just in case!
def set_scl_swapped(val): set_sda(val)
def set_sda_swapped(val): set_scl(val)
def get_sda_swapped(): return (struct.unpack('<I', pio[base+0x34:base+0x38])[0] >> 2) & 1

def i2c_write_byte_swapped(b):
    for i in range(8):
        bit = (b >> (7 - i)) & 1
        set_sda_swapped(bit); i2c_delay()
        set_scl_swapped(1); i2c_delay()
        set_scl_swapped(0); i2c_delay()
    set_sda_swapped(1); i2c_delay()
    set_scl_swapped(1); i2c_delay()
    ack = (get_sda_swapped() == 0)
    set_scl_swapped(0); i2c_delay()
    return ack

found_swapped = []
for addr in range(0x08, 0x78):
    set_sda_swapped(1); set_scl_swapped(1); i2c_delay()
    set_sda_swapped(0); i2c_delay()
    set_scl_swapped(0); i2c_delay()
    ack = i2c_write_byte_swapped((addr << 1) | 0)
    set_sda_swapped(0); i2c_delay()
    set_scl_swapped(1); i2c_delay()
    set_sda_swapped(1); i2c_delay()
    if ack:
        found_swapped.append(f"0x{addr:02x}")

print(f"PB03/PB02 Swapped Bit-Bang Results: {found_swapped}")

set_scl(1); set_sda(1)
pio.close()
os.close(fd_mem)
