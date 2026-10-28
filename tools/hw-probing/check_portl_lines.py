import os
import struct
import fcntl

# struct gpioline_info {
#   __u32 line_offset;
#   __u32 flags;
#   char name[32];
#   char consumer[32];
# };
# GPIO_GET_LINEINFO_IOCTL = 0xc048b405

fd = os.open('/dev/gpiochip0', os.O_RDONLY)
print("=== GPIOCHIP0 (1f02c00.pinctrl - Port L) Lines ===")
for offset in range(12):
    buf = bytearray(struct.pack('II32s32s', offset, 0, b'', b''))
    try:
        fcntl.ioctl(fd, 0xc048b405, buf)
        line_offset, flags, name, consumer = struct.unpack('II32s32s', buf)
        name = name.split(b'\x00')[0].decode()
        consumer = consumer.split(b'\x00')[0].decode()
        is_used = bool(flags & 1)
        is_out = bool(flags & 2)
        active_low = bool(flags & 4)
        print(f"PL{offset:02d}: used={is_used:<5} dir={'OUT' if is_out else 'IN ':<3} act_low={active_low:<5} consumer='{consumer}'")
    except Exception as e:
        print(f"PL{offset:02d}: error {e}")
os.close(fd)
