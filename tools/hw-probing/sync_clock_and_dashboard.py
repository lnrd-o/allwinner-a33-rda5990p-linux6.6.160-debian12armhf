import exec_com
import datetime

now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
print(f"[+] Laptop current time: {now}")
print("[+] Syncing tablet date & time...")
res = exec_com.run_cmd(f'date -s "{now}"')
print("    Date result:", res.strip())

print("[+] Uploading live ticking lcd_dashboard.py...")
exec_com.send_file('lcd_dashboard.py', '/usr/local/bin/lcd_dashboard.py')

print("[+] Starting dashboard daemon on tablet...")
out = exec_com.run_cmd('pkill -f lcd_dashboard.py; nohup python3 /usr/local/bin/lcd_dashboard.py --daemon >/dev/null 2>&1 & sleep 1; ps aux | grep lcd_dashboard')
print(out)
