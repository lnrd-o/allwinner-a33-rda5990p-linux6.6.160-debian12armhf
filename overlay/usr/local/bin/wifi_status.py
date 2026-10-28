#!/usr/bin/env python3
# wifi_status.py - writes /tmp/wifi.json for the LCD dashboard (state, SSID, dBm, IP, scanned networks).
# Read-only: it never joins networks (wpa_supplicant owns the connection).
import subprocess, re, json, time, os
OUT = "/tmp/wifi.json"
def sh(c, t=40):
    try: return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=t).stdout
    except Exception: return ""
def save(d):
    d["ts"] = int(time.time())
    open(OUT + ".tmp", "w").write(json.dumps(d)); os.replace(OUT + ".tmp", OUT)
def link():
    t = sh("iwconfig wlan0 2>&1")
    a = re.search(r"Access Point: ([0-9A-Fa-f:]{17})", t); e = re.search(r'ESSID:"(.*?)"', t)
    s = re.search(r"Signal level[=:](-?\d+)", t)
    return (a.group(1) if a else None), (e.group(1) if e else ""), (int(s.group(1)) if s else None)
def scan():
    txt = ""
    for _ in range(5):
        txt = sh("iwlist wlan0 scan 2>&1", 30)
        if "Cell" in txt: break
        time.sleep(1)
    nets = []
    for blk in re.split(r"Cell \d+", txt)[1:]:
        e = re.search(r'ESSID:"(.*?)"', blk); s = re.search(r"Signal level[=:](-?\d+)", blk)
        ch = re.search(r"Channel[: ](\d+)", blk)
        nets.append((e.group(1) if e else "?", int(s.group(1)) if s else None, ch.group(1) if ch else "?"))
    return sorted(nets, key=lambda n: -(n[1] if n[1] is not None else -999))
while True:
    if not os.path.exists("/sys/class/net/wlan0"):
        save({"state": "NO wlan0", "ssid": "", "dbm": None, "ip": "", "nets": []}); time.sleep(5); continue
    ap, essid, dbm = link()
    if ap and ap != "00:00:00:00:00:00" and essid:
        ip = re.search(r"inet (\S+)", sh("ip -4 addr show wlan0"))
        # the driver reports the signal level of the last scan; refresh it while connected
        nets = scan(); cur = [n for n in nets if n[0] == essid]
        save({"state": "CONNECTED", "ssid": essid, "dbm": cur[0][1] if cur else dbm,
              "ip": ip.group(1) if ip else "no IP yet", "nets": nets[:6]})
        time.sleep(10); continue
    nets = scan()
    save({"state": "FOUND" if nets else "SCANNING", "ssid": "", "dbm": None, "ip": "", "nets": nets[:6]})
    time.sleep(5)
