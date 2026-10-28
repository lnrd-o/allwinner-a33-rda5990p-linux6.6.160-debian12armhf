import serial
import time
import sys

def run_cmd(cmd, timeout=10):
    ser = serial.Serial('COM22', 115200, timeout=0.5)
    ser.write(b'\x03\n')
    time.sleep(0.15)
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    
    # send command with marker
    marker = "DONE_CMD_XYZ_123"
    full_cmd = f"{cmd}; echo {marker}_$?\n"
    ser.write(full_cmd.encode('utf-8'))
    
    t0 = time.time()
    out = b''
    # Discard echo of command line
    time.sleep(0.2)
    while time.time() - t0 < timeout:
        n = ser.in_waiting
        if n:
            chunk = ser.read(n)
            out += chunk
            if f"\n{marker}_".encode('utf-8') in out or f"\r\n{marker}_".encode('utf-8') in out:
                break
        else:
            time.sleep(0.05)
    ser.close()
    text = out.decode('utf-8', errors='ignore')
    return text

def send_file(local_path, remote_path):
    import base64
    with open(local_path, 'rb') as f:
        data = f.read()
    b64 = base64.b64encode(data).decode('ascii')
    
    ser = serial.Serial('COM22', 115200, timeout=1)
    ser.write(b'\x03\n')
    time.sleep(0.2)
    ser.read(ser.in_waiting or 1)
    
    ser.write(f"rm -f {remote_path}.b64 {remote_path}\n".encode('utf-8'))
    time.sleep(0.1)
    
    chunk_size = 1000
    for i in range(0, len(b64), chunk_size):
        chunk = b64[i:i+chunk_size]
        ser.write(f"printf '%s' '{chunk}' >> {remote_path}.b64\n".encode('utf-8'))
        time.sleep(0.1)
    
    marker = "DONE_UPLOAD_XYZ"
    cmd = f"base64 -d {remote_path}.b64 > {remote_path} && rm -f {remote_path}.b64 && chmod +x {remote_path} && ls -l {remote_path}; echo {marker}_$?\n"
    ser.write(cmd.encode('utf-8'))
    
    t0 = time.time()
    out = b''
    while time.time() - t0 < 10:
        if ser.in_waiting:
            out += ser.read(ser.in_waiting)
            if marker.encode('utf-8') in out:
                break
        time.sleep(0.05)
    ser.close()
    return out.decode('utf-8', errors='ignore')

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    cmd = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "uname -a"
    print(run_cmd(cmd))
