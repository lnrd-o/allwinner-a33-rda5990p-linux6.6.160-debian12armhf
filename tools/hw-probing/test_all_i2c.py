import os, sys, time, mmap, struct

print("==================================================")
print("  PROBING HARDWARE I2C BUSES (/dev/i2c-0..2)")
print("==================================================")

# Linux I2C ioctl definitions
I2C_SLAVE = 0x0703

candidates = [0x11, 0x13, 0x14, 0x15, 0x16, 0x40, 0x18]

for bus_id in [0, 1, 2]:
    dev_path = f"/dev/i2c-{bus_id}"
    if not os.path.exists(dev_path):
        continue
    print(f"\n--- Scanning {dev_path} ---")
    try:
        import fcntl
        fd = os.open(dev_path, os.O_RDWR)
        found = []
        for addr in range(0x08, 0x78):
            try:
                fcntl.ioctl(fd, I2C_SLAVE, addr)
                # Try a 1-byte read or write of 0 bytes
                os.write(fd, b'\x00')
                found.append(f"0x{addr:02x}")
            except Exception:
                pass
        os.close(fd)
        if found:
            print(f"  [+] Devices found on {dev_path}: {', '.join(found)}")
        else:
            print(f"  [-] No devices responded on {dev_path}")
    except Exception as e:
        print(f"  [-] Error scanning {dev_path}: {e}")

print("\n==================================================")
print("  BIT-BANGING I2C SCAN ON PB02 (SCL) & PB03 (SDA)")
print("==================================================")

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
pio = mmap.mmap(fd_mem, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0x01c20800)

# PB_CFG0 at offset 0x24
# PB_DATA at offset 0x34
# PB_PULL0 at offset 0x44

# Configure PB2, PB3 pull-ups:
# PB2: bits 5:4 = 01 (pull-up)
# PB3: bits 7:6 = 01 (pull-up)
pull = struct.unpack('<I', pio[0x44:0x48])[0]
pull = (pull & ~0x000000f0) | 0x00000050
pio[0x44:0x48] = struct.pack('<I', pull)

def set_scl(val):
    # If val=1, set as input (pulled high). If val=0, set as output low.
    cfg = struct.unpack('<I', pio[0x24:0x28])[0]
    if val:
        cfg = cfg & ~(7 << 8) # Input (high-Z)
        pio[0x24:0x28] = struct.pack('<I', cfg)
    else:
        dat = struct.unpack('<I', pio[0x34:0x38])[0] & ~(1 << 2)
        pio[0x34:0x38] = struct.pack('<I', dat)
        cfg = (cfg & ~(7 << 8)) | (1 << 8) # Output low
        pio[0x24:0x28] = struct.pack('<I', cfg)

def set_sda(val):
    cfg = struct.unpack('<I', pio[0x24:0x28])[0]
    if val:
        cfg = cfg & ~(7 << 12) # Input (high-Z)
        pio[0x24:0x28] = struct.pack('<I', cfg)
    else:
        dat = struct.unpack('<I', pio[0x34:0x38])[0] & ~(1 << 3)
        pio[0x34:0x38] = struct.pack('<I', dat)
        cfg = (cfg & ~(7 << 12)) | (1 << 12) # Output low
        pio[0x24:0x28] = struct.pack('<I', cfg)

def get_sda():
    dat = struct.unpack('<I', pio[0x34:0x38])[0]
    return (dat >> 3) & 1

def i2c_delay():
    time.sleep(0.00002) # ~25 kHz

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
    # Read ACK
    set_sda(1) # release SDA
    i2c_delay()
    set_scl(1)
    i2c_delay()
    ack = get_sda() == 0
    set_scl(0)
    i2c_delay()
    return ack

# Test lines state
set_scl(1)
set_sda(1)
time.sleep(0.01)
sda_idle = get_sda()
print(f"SDA idle level (should be 1 with pull-up): {sda_idle}")

found_bb = []
for addr in range(0x08, 0x78):
    i2c_start()
    ack = i2c_write_byte((addr << 1) | 0) # Write
    i2c_stop()
    if ack:
        found_bb.append(f"0x{addr:02x}")

if found_bb:
    print(f"\n🎉🎉🎉 RESPONDING I2C DEVICES FOUND ON PB02/PB03: {', '.join(found_bb)} 🎉🎉🎉")
else:
    print("\n[-] No ACK on PB02/PB03 for range 0x08..0x77")

pio.close()
os.close(fd_mem)
