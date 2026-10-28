import os
import mmap
import struct
import time

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# 1. RTC 32kHz
rtc = mmap.mmap(fd, 4096, offset=0x01f00000)
rtc[0x60:0x64] = struct.pack('<I', 1)
rtc.close()

# 2. Port L: PL6=1, PL8=1, PL10=1, PL11=1
rpio = mmap.mmap(fd, 4096, offset=0x01f02000)
base_l = 0xc00
cfg0 = (struct.unpack('<I', rpio[base_l:base_l+4])[0] & ~(0x7 << 24)) | (1 << 24)
cfg1 = (struct.unpack('<I', rpio[base_l+4:base_l+8])[0] & ~0x7007) | 0x1001
rpio[base_l:base_l+4] = struct.pack('<I', cfg0)
rpio[base_l+4:base_l+8] = struct.pack('<I', cfg1)
dat = struct.unpack('<I', rpio[base_l+0x10:base_l+0x14])[0] | (1 << 6) | (1 << 8) | (1 << 10) | (1 << 11)
rpio[base_l+0x10:base_l+0x14] = struct.pack('<I', dat)
rpio.close()

# 3. CCU & PIO
pio = mmap.mmap(fd, 4096, offset=0x01c20000)

# Ungate UART1 clock (0x06c bit 17) & reset (0x2d8 bit 17)
u1_clk = struct.unpack('<I', pio[0x6c:0x70])[0] | (1 << 17)
pio[0x6c:0x70] = struct.pack('<I', u1_clk)
u1_rst = struct.unpack('<I', pio[0x2d8:0x2dc])[0] | (1 << 17)
pio[0x2d8:0x2dc] = struct.pack('<I', u1_rst)

# Configure Port G PG6-PG9 as function 2 (UART1)
# PG CFG0 (0x8d8): bits 24..31 (PG6, PG7)
cfg0 = struct.unpack('<I', pio[0x8d8:0x8dc])[0] & ~(0xff << 24)
cfg0 |= (0x22 << 24) # PG6=2, PG7=2
pio[0x8d8:0x8dc] = struct.pack('<I', cfg0)

# PG CFG1 (0x8dc): bits 0..7 (PG8, PG9)
cfg1 = struct.unpack('<I', pio[0x8dc:0x8e0])[0] & ~(0xff << 0)
cfg1 |= (0x22 << 0)  # PG8=2, PG9=2
pio[0x8dc:0x8e0] = struct.pack('<I', cfg1)

# Pull-ups on PG6-PG9 (0x8f4 bits 12..19)
pull = struct.unpack('<I', pio[0x8f4:0x8f8])[0] | (0x55 << 12)
pio[0x8f4:0x8f8] = struct.pack('<I', pull)

print(f"CCU UART1: CLK_GATE=0x{struct.unpack('<I', pio[0x6c:0x70])[0]:08x}, RST=0x{struct.unpack('<I', pio[0x2d8:0x2dc])[0]:08x}")
print(f"Port G CFG0=0x{struct.unpack('<I', pio[0x8d8:0x8dc])[0]:08x}, CFG1=0x{struct.unpack('<I', pio[0x8dc:0x8e0])[0]:08x}")
pio.close()

# 4. UART1 Controller (0x01c28400 -> page 0x01c28000, offset 0x400)
u1_page = mmap.mmap(fd, 4096, offset=0x01c28000)
ubase = 0x400

def ur32(off):
    return struct.unpack('<I', u1_page[ubase+off:ubase+off+4])[0]

def uw32(off, val):
    u1_page[ubase+off:ubase+off+4] = struct.pack('<I', val)

# Configure 115200 8N1
# Disable interrupts: IER = 0
uw32(0x04, 0x00)
# Enable FIFO, reset FIFOs: FCR = 0x07
uw32(0x08, 0x07)
# Enable DLAB to set baud rate divisor: LCR = 0x83
uw32(0x0c, 0x83)
# Divisor for 115200 from 24MHz: 24000000 / (16 * 115200) = 13 (0x0d)
uw32(0x00, 13) # DLL
uw32(0x04, 0)  # DLM
# Clear DLAB, set 8 bits, 1 stop bit, no parity: LCR = 0x03
uw32(0x0c, 0x03)
# Modem control: RTS=1, DTR=1
uw32(0x10, 0x03)

print(f"UART1 Initialized: LCR=0x{ur32(0x0c):02x}, LSR=0x{ur32(0x14):02x}, MSR=0x{ur32(0x18):02x}")

def uart_write(data):
    for b in data:
        # Wait for THRE (bit 5) in LSR
        while not (ur32(0x14) & (1 << 5)):
            time.sleep(0.0001)
        uw32(0x00, b)

def uart_read(timeout=0.5):
    res = []
    t0 = time.time()
    while time.time() - t0 < timeout:
        if ur32(0x14) & 1: # DR (Data Ready)
            res.append(ur32(0x00) & 0xff)
            t0 = time.time() # reset timeout on byte
        else:
            time.sleep(0.001)
    return bytes(res)

print("\n--- Sending Bluetooth HCI Reset (0x01, 0x03, 0x0c, 0x00) ---")
# Flush RX
while ur32(0x14) & 1:
    ur32(0x00)

uart_write(bytes([0x01, 0x03, 0x0c, 0x00]))
resp = uart_read(0.5)

if resp:
    print(f"  [+] SUCCESS! Bluetooth replied: {[hex(x) for x in resp]}")
else:
    print("  [-] No reply to HCI Reset at 115200 baud")

u1_page.close()
os.close(fd)
