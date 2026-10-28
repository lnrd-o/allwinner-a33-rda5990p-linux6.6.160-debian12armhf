import os
import mmap
import struct
import fcntl
import time

def read_u32(mm, offset):
    return struct.unpack('<I', mm[offset:offset+4])[0]

def write_u32(mm, offset, val):
    mm[offset:offset+4] = struct.pack('<I', val)

print("=== [1] Power & Clock Initialization ===")
fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 1. RTC 32k clock fanout
rtc = mmap.mmap(fd_mem, 4096, offset=0x01f00000)
write_u32(rtc, 0x60, 1) # LOSC_OUT enable
losc = read_u32(rtc, 0x60)
print(f"RTC LOSC_OUT (0x01f00060) = 0x{losc:08x}")
rtc.close()

# 2. Port L pins (0x01f02c00)
rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
base_l = 0xc00
cfg0 = read_u32(rpio, base_l)
cfg1 = read_u32(rpio, base_l + 4)
pull = read_u32(rpio, base_l + 0x1c)

# PL6 (out), PL7 (in), PL8 (out), PL9 (in), PL10 (out), PL11 (out)
cfg0 = (cfg0 & ~(0x7 << 24)) | (1 << 24) # PL6 out
cfg1 = (cfg1 & ~(0x7 << 0))  | (1 << 0)  # PL8 out
cfg1 = (cfg1 & ~(0x7 << 8))  | (1 << 8)  # PL10 out
cfg1 = (cfg1 & ~(0x7 << 12)) | (1 << 12) # PL11 out
pull |= (1 << 14) | (1 << 18)

write_u32(rpio, base_l, cfg0)
write_u32(rpio, base_l + 4, cfg1)
write_u32(rpio, base_l + 0x1c, pull)

# Power sequence:
# Reset everything low first
dat = read_u32(rpio, base_l + 0x10)
dat &= ~((1 << 6) | (1 << 8) | (1 << 10) | (1 << 11))
write_u32(rpio, base_l + 0x10, dat)
time.sleep(0.05)

# Step A: chip_en (PL11) HIGH
dat |= (1 << 11)
write_u32(rpio, base_l + 0x10, dat)
time.sleep(0.02)

# Step B: wl_regon (PL6) and PL10 HIGH
dat |= (1 << 6) | (1 << 10)
write_u32(rpio, base_l + 0x10, dat)
time.sleep(0.02)

# Step C: bt_rst_n (PL8) HIGH
dat |= (1 << 8)
write_u32(rpio, base_l + 0x10, dat)
time.sleep(0.05)

dat_now = read_u32(rpio, base_l + 0x10)
print(f"Port L DAT = 0x{dat_now:08x} (PL6={bool(dat_now&(1<<6))}, PL8={bool(dat_now&(1<<8))}, PL11={bool(dat_now&(1<<11))})")
rpio.close()
os.close(fd_mem)

print("\n=== [2] Probing I2C Buses ===")
for bus in [1, 0]:
    dev = f'/dev/i2c-{bus}'
    if not os.path.exists(dev):
        continue
    print(f"Scanning {dev}...")
    for addr in [0x13, 0x14, 0x15, 0x16]:
        try:
            fd = os.open(dev, os.O_RDWR)
            fcntl.ioctl(fd, 0x0703, addr)
            # Try reading reg 0x3f
            os.write(fd, bytes([0x3f]))
            val = os.read(fd, 2)
            u16 = (val[0] << 8) | val[1]
            print(f"  [+] ACK on {dev} addr 0x{addr:02x}! Reg 0x3f = 0x{u16:04x}")
            os.close(fd)
        except Exception as e:
            try:
                os.close(fd)
            except:
                pass
