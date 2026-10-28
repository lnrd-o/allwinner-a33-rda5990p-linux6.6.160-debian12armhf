import mmap
import os
import struct
import fcntl
import time

fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
rtc = mmap.mmap(fd_mem, 4096, offset=0x01f00000)
losc = struct.unpack('<I', rtc[0x60:0x64])[0]
print("LOSC_OUT (0x01f00060):", hex(losc))
rtc.close()

rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
cfg0 = struct.unpack('<I', rpio[0xc00:0xc04])[0]
cfg1 = struct.unpack('<I', rpio[0xc04:0xc08])[0]
dat  = struct.unpack('<I', rpio[0xc10:0xc14])[0]
pull = struct.unpack('<I', rpio[0xc1c:0xc20])[0]
print(f"Port L CFG0={hex(cfg0)}, CFG1={hex(cfg1)}, DAT={hex(dat)}, PULL={hex(pull)}")
rpio.close()
os.close(fd_mem)

print("\nScanning /dev/i2c-1 for ALL ACK addresses (both Read and Write)...")
read_acks = []
write_acks = []
for a in range(0x08, 0x78):
    # Try 1-byte write (address probe)
    try:
        f = os.open('/dev/i2c-1', os.O_RDWR)
        fcntl.ioctl(f, 0x0703, a)
        os.write(f, bytes([0x00]))
        write_acks.append(hex(a))
        os.close(f)
    except:
        try: os.close(f)
        except: pass

    # Try 1-byte read
    try:
        f = os.open('/dev/i2c-1', os.O_RDWR)
        fcntl.ioctl(f, 0x0703, a)
        b = os.read(f, 1)
        read_acks.append((hex(a), hex(b[0])))
        os.close(f)
    except:
        try: os.close(f)
        except: pass

print("Write ACKs on /dev/i2c-1:", write_acks)
print("Read ACKs on /dev/i2c-1:", read_acks)
