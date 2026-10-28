import os, sys, time, mmap, struct

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
base_pio = 0x800

def set_scl(val):
    cfg = struct.unpack('<I', pio[base_pio+0x24:base_pio+0x28])[0]
    if val:
        cfg &= ~(7 << 12)
        pio[base_pio+0x24:base_pio+0x28] = struct.pack('<I', cfg)
    else:
        dat = struct.unpack('<I', pio[base_pio+0x34:base_pio+0x38])[0] & ~(1 << 3)
        pio[base_pio+0x34:base_pio+0x38] = struct.pack('<I', dat)
        cfg = (cfg & ~(7 << 12)) | (1 << 12)
        pio[base_pio+0x24:base_pio+0x28] = struct.pack('<I', cfg)

def set_sda(val):
    cfg = struct.unpack('<I', pio[base_pio+0x24:base_pio+0x28])[0]
    if val:
        cfg &= ~(7 << 8)
        pio[base_pio+0x24:base_pio+0x28] = struct.pack('<I', cfg)
    else:
        dat = struct.unpack('<I', pio[base_pio+0x34:base_pio+0x38])[0] & ~(1 << 2)
        pio[base_pio+0x34:base_pio+0x38] = struct.pack('<I', dat)
        cfg = (cfg & ~(7 << 8)) | (1 << 8)
        pio[base_pio+0x24:base_pio+0x28] = struct.pack('<I', cfg)

def get_sda():
    return (struct.unpack('<I', pio[base_pio+0x34:base_pio+0x38])[0] >> 2) & 1

def i2c_d(): time.sleep(0.00002)

def i2c_start():
    set_sda(1); set_scl(1); i2c_d()
    set_sda(0); i2c_d()
    set_scl(0); i2c_d()

def i2c_stop():
    set_sda(0); i2c_d()
    set_scl(1); i2c_d()
    set_sda(1); i2c_d()

def i2c_wb(b):
    for i in range(8):
        bit = (b >> (7 - i)) & 1
        set_sda(bit); i2c_d()
        set_scl(1); i2c_d()
        set_scl(0); i2c_d()
    set_sda(1); i2c_d()
    set_scl(1); i2c_d()
    ack = (get_sda() == 0)
    set_scl(0); i2c_d()
    return ack

def rda_i2c_write(addr7, reg8, val16):
    i2c_start()
    if not i2c_wb((addr7 << 1) | 0): i2c_stop(); return False
    if not i2c_wb(reg8): i2c_stop(); return False
    if not i2c_wb((val16 >> 8) & 0xff): i2c_stop(); return False
    if not i2c_wb(val16 & 0xff): i2c_stop(); return False
    i2c_stop()
    return True

CHIP_ADDR = 0x14

wifi_rf_init_data_verE = [
    (0x3f, 0x0000), (0x06, 0x0101), (0x07, 0x0101), (0x08, 0x0101),
    (0x09, 0x0101), (0x0A, 0x002C), (0x0D, 0x0507), (0x0E, 0x2300),
    (0x0F, 0x5689), (0x10, 0x0f78), (0x11, 0x0602), (0x13, 0x0652),
    (0x14, 0x8886), (0x15, 0x0990), (0x16, 0x049f), (0x17, 0x0990),
    (0x18, 0x049F), (0x19, 0x3C01), (0x1C, 0x0934), (0x1D, 0xFF00),
    (0x20, 0x06E4), (0x21, 0x0ACF), (0x22, 0x24DC), (0x23, 0x23FF),
    (0x24, 0x00FC), (0x26, 0x004F), (0x27, 0x171D), (0x28, 0x031D),
    (0x2A, 0x2860), (0x2B, 0x0800),
]

print("[+] Applying VerE RF tables to RDA5990 over PB03/PB02...")
for reg, val in wifi_rf_init_data_verE:
    rda_i2c_write(CHIP_ADDR, reg, val)

# DC calibration
for reg, val in [(0x3f, 0x0000), (0x30, 0x0248), (0x30, 0x0249)]:
    rda_i2c_write(CHIP_ADDR, reg, val)

time.sleep(0.05)
print("[✓] VerE RF tables applied!")
pio.close()
os.close(fd_mem)
