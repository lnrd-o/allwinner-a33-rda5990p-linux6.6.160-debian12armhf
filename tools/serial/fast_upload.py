import serial
import time
import base64
import hashlib
import sys

def upload_file(local_path, remote_path):
    with open(local_path, 'rb') as f:
        data = f.read()
    local_md5 = hashlib.md5(data).hexdigest()
    b64 = base64.b64encode(data).decode('ascii')
    
    print(f"[*] Uploading {local_path} ({len(data)} bytes, md5={local_md5}) -> {remote_path}")
    
    ser = serial.Serial('COM22', 115200, timeout=1)
    # Clear any pending prompt
    ser.write(b'\x03\n\x03\n')
    time.sleep(0.3)
    if ser.in_waiting:
        ser.read(ser.in_waiting)
        
    # Disable echo
    ser.write(b"stty -echo\n")
    time.sleep(0.2)
    if ser.in_waiting:
        ser.read(ser.in_waiting)
        
    # Start base64 decoder
    ser.write(f"base64 -d > {remote_path}\n".encode('ascii'))
    time.sleep(0.2)
    if ser.in_waiting:
        ser.read(ser.in_waiting)
        
    # Send base64 data in lines of 76 chars with \n
    chunk_size = 512
    total = len(b64)
    sent = 0
    t0 = time.time()
    
    for i in range(0, total, chunk_size):
        chunk = b64[i:i+chunk_size] + "\n"
        ser.write(chunk.encode('ascii'))
        sent += len(chunk)
        # Drain any stray bytes
        if ser.in_waiting:
            ser.read(ser.in_waiting)
        time.sleep(0.02)
        if (i // chunk_size) % 10 == 0 or i + chunk_size >= total:
            pct = int((i + len(chunk)) / total * 100)
            sys.stdout.write(f"\rProgress: {min(pct, 100)}% ({sent}/{total} b64 chars)")
            sys.stdout.flush()
            
    print()
    # Send EOF (Ctrl-D) to terminate base64 input
    time.sleep(0.2)
    ser.write(b"\n\x04\x04\n")
    time.sleep(0.5)
    
    # Re-enable echo
    ser.write(b"stty echo\n")
    time.sleep(0.2)
    if ser.in_waiting:
        ser.read(ser.in_waiting)
        
    # Verify MD5
    marker = "DONE_MD5_CHECK"
    cmd = f"md5sum {remote_path}; echo {marker}_$?\n"
    ser.write(cmd.encode('ascii'))
    
    t0 = time.time()
    out = b''
    while time.time() - t0 < 5:
        if ser.in_waiting:
            out += ser.read(ser.in_waiting)
            if marker.encode('ascii') in out:
                break
        time.sleep(0.05)
        
    ser.close()
    resp = out.decode('utf-8', errors='ignore')
    print("[*] Output:", resp.strip())
    if local_md5 in resp:
        print(f"[OK] {remote_path} transferred and verified successfully!\n")
        return True
    else:
        print(f"[FAIL] MD5 verification failed for {remote_path}!\n")
        return False

if __name__ == '__main__':
    ok2 = upload_file('output/rescan_mmc.ko', '/root/rescan_mmc.ko')
    if ok2:
        print("[OK] rescan_mmc.ko UPLOADED AND VERIFIED!")
