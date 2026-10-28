import os
import struct
import time
import termios
import mmap

print("=== [1] Testing Bluetooth UART (ttyS1) ===")
try:
    fd_uart = os.open('/dev/ttyS1', os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    # Set 115200 8N1 raw mode
    attr = termios.tcgetattr(fd_uart)
    # iflag
    attr[0] = 0
    # oflag
    attr[1] = 0
    # cflag: CS8, CREAD, CLOCAL, B115200
    attr[2] = termios.CS8 | termios.CREAD | termios.CLOCAL | termios.B115200
    # lflag
    attr[3] = 0
    # cc
    attr[6][termios.VMIN] = 0
    attr[6][termios.VTIME] = 5 # 500ms
    termios.tcsetattr(fd_uart, termios.TCSANOW, attr)
    
    # Flush
    termios.tcflush(fd_uart, termios.TCIOFLUSH)
    
    # Send HCI Reset: Packet Type 0x01 (Command), Opcode 0x0c03 (HCI_Reset), Length 0x00
    hci_reset = bytes([0x01, 0x03, 0x0c, 0x00])
    os.write(fd_uart, hci_reset)
    time.sleep(0.1)
    
    buf = os.read(fd_uart, 64)
    if buf:
        print(f"  [+] HCI Reset Reply: {[hex(x) for x in buf]}")
    else:
        print("  [-] No reply to HCI Reset at 115200 on ttyS1")
    os.close(fd_uart)
except Exception as e:
    print(f"  [-] ttyS1 error: {e}")

print("\n=== [2] Testing Direct SDIO CMD5 with OCR Mask (0x00ff8000) ===")
fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)

# Ensure CCU MMC1 clock
ccu = mmap.mmap(fd, 4096, offset=0x01c20000)
ccu[0x64:0x68] = struct.pack('<I', 0x80000000)
gate = struct.unpack('<I', ccu[0x60:0x64])[0] | (1 << 9)
ccu[0x60:0x64] = struct.pack('<I', gate)
rst = struct.unpack('<I', ccu[0x2c0:0x2c4])[0] | (1 << 9)
ccu[0x2c0:0x2c4] = struct.pack('<I', rst)
ccu.close()

# MMC1 controller (0x01c10000)
mmc = mmap.mmap(fd, 4096, offset=0x01c10000)

def r32(off):
    return struct.unpack('<I', mmc[off:off+4])[0]

def w32(off, val):
    mmc[off:off+4] = struct.pack('<I', val)

# Soft reset
w32(0x00, 0x7)
time.sleep(0.02)
w32(0x08, 0xffffffff) # TMOUT
w32(0x0c, 0x0)        # 1-bit

# 400kHz clock
w32(0x04, 0x0001011d)
w32(0x18, 0x80202000) # update clk
t0 = time.time()
while time.time() - t0 < 0.2:
    if not (r32(0x18) & 0x80000000): break
    time.sleep(0.001)
w32(0x38, 0xffffffff)

# Send CMD0 with 74 clocks: START | SEND_INIT_SEQ | WAIT_PRE_OVER = 0x8000a000
w32(0x1c, 0)
w32(0x18, 0x8000a000)
t0 = time.time()
while time.time() - t0 < 0.2:
    if not (r32(0x18) & 0x80000000): break
    time.sleep(0.001)
w32(0x38, 0xffffffff)

# Send CMD5 (arg = 0x00000000)
print("Sending CMD5 with arg=0x00000000...")
w32(0x1c, 0)
w32(0x18, 0x80002045)
t0 = time.time()
while time.time() - t0 < 0.2:
    if not (r32(0x18) & 0x80000000): break
    time.sleep(0.001)

rint_inq = r32(0x38)
resp0_inq = r32(0x20)
print(f"  CMD5 Inquiry: RINT=0x{rint_inq:08x}, RESP0=0x{resp0_inq:08x}")
w32(0x38, 0xffffffff)

# Send CMD5 (arg = 0x00ff8000 - standard 3.3V voltage window)
print("Sending CMD5 with arg=0x00ff8000 (3.3V OCR)...")
w32(0x1c, 0x00ff8000)
w32(0x18, 0x80002045)
t0 = time.time()
while time.time() - t0 < 0.2:
    if not (r32(0x18) & 0x80000000): break
    time.sleep(0.001)

rint_ocr = r32(0x38)
resp0_ocr = r32(0x20)
print(f"  CMD5 with OCR: RINT=0x{rint_ocr:08x}, RESP0=0x{resp0_ocr:08x}")
w32(0x38, 0xffffffff)

# Send CMD52 Software Reset (CCCR address 0x06, value 0x08)
# Argument for write byte to CCCR 0x06:
# Bit 31 = 1 (Write)
# Bits 30:28 = 0 (Function 0)
# Bit 27 = 0 (RAW)
# Bits 25:9 = 0x06 (Address)
# Bits 7:0 = 0x08 (Reset)
# arg = (1 << 31) | (0x06 << 9) | 0x08 = 0x80000c08
print("Sending CMD52 CCCR Reset (arg=0x80000c08)...")
w32(0x1c, 0x80000c08)
# CMD52 expects R5 response: RESP_EXPIRE (bit 6) | CHECK_CRC (bit 8) | WAIT_PRE_OVER (bit 13) | CMD 52
# 0x80002174
w32(0x18, 0x80002174)
t0 = time.time()
while time.time() - t0 < 0.2:
    if not (r32(0x18) & 0x80000000): break
    time.sleep(0.001)

rint_cmd52 = r32(0x38)
resp0_cmd52 = r32(0x20)
print(f"  CMD52 Result: RINT=0x{rint_cmd52:08x}, RESP0=0x{resp0_cmd52:08x}")
w32(0x38, 0xffffffff)

mmc.close()
os.close(fd)
