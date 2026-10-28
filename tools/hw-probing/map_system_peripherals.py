import os
import sys
import glob
import subprocess
import json
import time
import struct
import mmap

report = {}

# 1. System & Kernel
report["system"] = {
    "kernel": subprocess.getoutput("uname -a"),
    "uptime": subprocess.getoutput("uptime"),
    "cmdline": subprocess.getoutput("cat /proc/cmdline")
}

# 2. CPU & Memory
mem_info = subprocess.getoutput("free -m")
cpu_info = subprocess.getoutput("lscpu | grep -E 'Model name|CPU\(s\)|CPU max MHz|Architecture'")
report["cpu_memory"] = {
    "cpu": cpu_info,
    "memory": mem_info
}

# 3. Power & Battery (AXP223)
ps_dict = {}
for ps in glob.glob("/sys/class/power_supply/*"):
    name = os.path.basename(ps)
    ps_dict[name] = {}
    for prop in ["type", "status", "capacity", "voltage_now", "current_now", "online", "health"]:
        p_path = os.path.join(ps, prop)
        if os.path.exists(p_path):
            with open(p_path) as f:
                ps_dict[name][prop] = f.read().strip()
report["power_supply"] = ps_dict

# 4. Regulators
regs = {}
for reg in glob.glob("/sys/class/regulator/*"):
    name = os.path.basename(reg)
    name_file = os.path.join(reg, "name")
    uV_file = os.path.join(reg, "microvolts")
    state_file = os.path.join(reg, "state")
    r_name = open(name_file).read().strip() if os.path.exists(name_file) else name
    uV = open(uV_file).read().strip() if os.path.exists(uV_file) else "N/A"
    st = open(state_file).read().strip() if os.path.exists(state_file) else "N/A"
    regs[r_name] = {"microvolts": uV, "state": st}
report["regulators"] = regs

# 5. Display & Framebuffer
fb_info = {}
for fb in glob.glob("/sys/class/graphics/fb*"):
    name = os.path.basename(fb)
    modes = subprocess.getoutput(f"cat {fb}/modes 2>/dev/null")
    blank = subprocess.getoutput(f"cat {fb}/blank 2>/dev/null")
    bpp = subprocess.getoutput(f"cat {fb}/bits_per_pixel 2>/dev/null")
    fb_info[name] = {"modes": modes, "blank": blank, "bpp": bpp}
report["framebuffer"] = fb_info

# 6. Input Devices
inputs = []
for ev in glob.glob("/sys/class/input/event*"):
    name_path = os.path.join(ev, "device/name")
    dev_name = open(name_path).read().strip() if os.path.exists(name_path) else "unknown"
    inputs.append({"event": os.path.basename(ev), "name": dev_name})
report["input_devices"] = inputs

# 7. I2C Adapters and Attached Devices
i2c_adapters = {}
for ad in glob.glob("/sys/class/i2c-adapter/*"):
    name = os.path.basename(ad)
    if "i2c-2" in name:
        i2c_adapters[name] = {"scanned_devices": "skipped (unconnected bus)"}
        continue
    bus_num = int(name.replace("i2c-", ""))
    dev_path = f"/dev/{name}"
    acks = []
    if os.path.exists(dev_path):
        import fcntl
        try:
            fd = os.open(dev_path, os.O_RDWR)
            for a in range(0x08, 0x78):
                try:
                    fcntl.ioctl(fd, 0x0703, a)
                    # Try 1-byte read
                    os.read(fd, 1)
                    acks.append(hex(a))
                except OSError:
                    try:
                        os.write(fd, bytes([0x00]))
                        acks.append(hex(a))
                    except:
                        pass
            os.close(fd)
        except Exception as e:
            acks = f"error: {e}"
    i2c_adapters[name] = {"scanned_devices": acks}
report["i2c_buses"] = i2c_adapters

# 8. MMC / SDIO Controllers
mmc_info = {}
for m in glob.glob("/sys/class/mmc_host/*"):
    name = os.path.basename(m)
    mmc_info[name] = {}
    cards = glob.glob(f"/sys/bus/mmc/devices/{name}:*")
    mmc_info[name]["devices"] = [os.path.basename(c) for c in cards]
report["mmc_hosts"] = mmc_info

# 9. Serial Ports / UARTs & Bluetooth HCI Probe on ttyS1
uarts = {}
for s in glob.glob("/sys/class/tty/ttyS*"):
    name = os.path.basename(s)
    dev_path = f"/dev/{name}"
    uarts[name] = {"exists": os.path.exists(dev_path)}

# Test HCI Reset on ttyS1 (Bluetooth)
bt_hci = "No response"
if os.path.exists("/dev/ttyS1"):
    try:
        import serial
        ser = serial.Serial('/dev/ttyS1', 115200, timeout=0.2)
        # Send HCI Reset: 0x01 0x03 0x0c 0x00
        ser.write(bytes([0x01, 0x03, 0x0c, 0x00]))
        resp = ser.read(10)
        ser.close()
        if resp:
            bt_hci = f"ACK: {list(resp)}"
        else:
            bt_hci = "No reply to HCI Reset at 115200"
    except Exception as e:
        bt_hci = f"Error: {e}"
report["bluetooth_hci_ttyS1"] = bt_hci

# 10. Port L & Port G Physical Levels
try:
    fd_mem = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
    rpio = mmap.mmap(fd_mem, 4096, offset=0x01f02000)
    cfg0 = struct.unpack('<I', rpio[0xc00:0xc04])[0]
    cfg1 = struct.unpack('<I', rpio[0xc04:0xc08])[0]
    dat  = struct.unpack('<I', rpio[0xc10:0xc14])[0]
    rpio.close()
    
    pio = mmap.mmap(fd_mem, 4096, offset=0x01c20000)
    pg_cfg0 = struct.unpack('<I', pio[0x8d8:0x8dc])[0]
    pg_dat  = struct.unpack('<I', pio[0x8e8:0x8ec])[0]
    pio.close()
    os.close(fd_mem)
    
    report["gpio_hardware_state"] = {
        "port_l": {"cfg0": hex(cfg0), "cfg1": hex(cfg1), "dat": hex(dat)},
        "port_g": {"cfg0": hex(pg_cfg0), "dat": hex(pg_dat)}
    }
except Exception as e:
    report["gpio_hardware_state"] = f"error: {e}"

print(json.dumps(report, indent=2))
