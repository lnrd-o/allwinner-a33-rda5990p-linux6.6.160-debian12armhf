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
    
    print(f"[*] Uploading {local_path} ({len(data)} bytes, md5={local_md5}) to {remote_path}...")
    
    ser = serial.Serial('COM22', 115200, timeout=1)
    ser.write(b'\x03\n')
    time.sleep(0.2)
    ser.read(ser.in_waiting or 1)
    
    # Remove existing files
    ser.write(f"rm -f {remote_path}.b64 {remote_path}\n".encode('utf-8'))
    time.sleep(0.2)
    ser.read(ser.in_waiting or 1)
    
    chunk_size = 1024
    total_chunks = (len(b64) + chunk_size - 1) // chunk_size
    for i in range(0, len(b64), chunk_size):
        chunk = b64[i:i+chunk_size]
        ser.write(f"printf '%s' '{chunk}' >> {remote_path}.b64\n".encode('utf-8'))
        time.sleep(0.08)
        chunk_idx = i // chunk_size + 1
        if chunk_idx % 10 == 0 or chunk_idx == total_chunks:
            sys.stdout.write(f"\rUploaded chunk {chunk_idx}/{total_chunks}")
            sys.stdout.flush()
    print()
    
    # Decode and check md5
    marker = "DONE_DECODE"
    cmd = f"base64 -d {remote_path}.b64 > {remote_path} && md5sum {remote_path} && rm -f {remote_path}.b64; echo {marker}_$?\n"
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
    
    resp = out.decode('utf-8', errors='ignore')
    print("[*] Remote response:", resp.strip())
    if local_md5 in resp:
        print(f"[✓] File {remote_path} transferred and verified successfully!")
        return True
    else:
        print(f"[!] MD5 mismatch or error transferring {remote_path}!")
        return False

if __name__ == '__main__':
    ok1 = upload_file('output/rda5890.ko.gz', '/root/rda5890.ko.gz')
    ok2 = upload_file('output/rescan_mmc.ko', '/root/rescan_mmc.ko')
    if ok1 and ok2:
        print("[✓] All modules uploaded successfully!")
    else:
        print("[!] Upload failed!")
        sys.exit(1)
