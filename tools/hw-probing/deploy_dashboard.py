import serial
import time

s = serial.Serial('COM22', 115200, timeout=1)

dashboard_script = open('lcd_dashboard.py', 'r', encoding='utf-8').read()

# Make sure root prompt is ready
s.write(b'\n')
time.sleep(0.2)
s.read(s.in_waiting or 1)

# Upload lcd_dashboard.py
s.write(b"cat << 'EOF' > /usr/local/bin/lcd_dashboard.py\n")
s.write(dashboard_script.encode('utf-8'))
s.write(b"\nEOF\n")
time.sleep(0.5)

# Execute dashboard
cmd = "chmod +x /usr/local/bin/lcd_dashboard.py; python3 /usr/local/bin/lcd_dashboard.py 'I2C SCAN & RDA5990 SILICON WAKEUP' 70\n"
s.write(cmd.encode('utf-8'))
time.sleep(1)

out = ""
while s.in_waiting:
    out += s.read(s.in_waiting).decode(errors='ignore')
    time.sleep(0.05)

print("Dashboard execution output:", out.encode('ascii', errors='replace').decode('ascii'))
s.close()
