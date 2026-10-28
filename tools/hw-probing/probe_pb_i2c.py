import os, sys, time, mmap, struct

print("==================================================")
print("  PROBING BIT-BANGED I2C ON PB02 (SCL) & PB03 (SDA)")
print("==================================================")

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20000)
base = 0x800

# Pull-ups on PB2 and PB3
# PB_PULL0 is at offset 0x44 (so base + 0x44)
pull = struct.unpack('<I', pio[base+0x44:base+0x48])[0]
pull = (pull & ~0x000000f0) | 0x00000050
pio[base+0x44:base+0x48] = struct.pack('<I', pull)

# First read idle level with both configured as input
cfg = struct.unpack('<I', pio[base+0x24:base+0x28])[0]
cfg = cfg & ~((7 << 8) | (7 << 12)) # Both input
pio[base+0x24:base+0x28] = struct.pack('<I', cfg)
time.sleep(0.01)

dat = struct.unpack('<I', pio[base+0x34:base+0x38])[0]
scl_idle = (dat >> 2) & 1
sda_idle = (dat >> 3) & 1
print(f"Idle levels: PB2 (SCL)={scl_idle}, PB3 (SDA)={sda_idle}")

def set_scl(val):
    cfg = struct.unpack('<I', pio[base+0x24:base+0x28])[0]
    if val:
        cfg = cfg & ~(7 << 8) # Input (pulled high)
        pio[base+0x24:base+0x28] = struct.pack('<I', cfg)
    else:
        dat = struct.unpack('<I', pio[base+0x34:base+0x38])[0] & ~(1 << 2)
        pio[base+0x34:base+0x38] = struct.pack('<I', dat)
        cfg = (cfg & ~(7 << 8)) | (1 << 8) # Output low
        pio[base+0x24:base+0x28] = struct.pack('<I', cfg)

def set_sda(val):
    cfg = struct.unpack('<I', pio[base+0x24:base+0x28])[0]
    if val:
        cfg = cfg & ~(7 << 12) # Input
        pio[base+0x24:base+0x28] = struct.pack('<I', cfg)
    else:
        dat = struct.unpack('<I', pio[base+0x34:base+0x38])[0] & ~(1 << 3)
        pio[base+0x34:base+0x38] = struct.pack('<I', dat)
        cfg = (cfg & ~(7 << 12)) | (1 << 12) # Output low
        pio[base+0x24:base+0x28] = struct.pack('<I', cfg)

def get_sda():
    dat = struct.unpack('<I', pio[base+0x34:base+0x38])[0]
    return (dat >> 3) & 1

def i2c_delay():
    time.sleep(0.00005) # ~10-20 kHz

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
        set_sda(bit)
        i2c_delay()
        set_scl(1)
        i2c_delay()
        set_scl(0)
        i2c_delay()
    set_sda(1) # release SDA for ACK
    i2c_delay()
    set_scl(1)
    i2c_delay()
    ack = (get_sda() == 0)
    set_scl(0)
    i2c_delay()
    return ack

print("Scanning addresses 0x08..0x77 on PB02/PB03:")
found = []
for addr in range(0x08, 0x78):
    i2c_start()
    ack = i2c_write_byte((addr << 1) | 0)
    i2c_stop()
    if ack:
        found.append(f"0x{addr:02x}")

if found:
    print(f"\n🎉🎉🎉 FOUND RESPONDING I2C DEVICES ON PB02/PB03: {', '.join(found)} 🎉🎉🎉")
else:
    print("[-] No ACK on PB02/PB03.")

# Restore pins as input
set_scl(1)
set_sda(1)
pio.close()
os.close(fd_mem)
