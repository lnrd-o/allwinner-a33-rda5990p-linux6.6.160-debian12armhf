import exec_com

print("[1] Uploading updated lcd_dashboard.py with Clock & Battery Header...")
exec_com.send_file('lcd_dashboard.py', '/usr/local/bin/lcd_dashboard.py')
print(exec_com.run_cmd('python3 /usr/local/bin/lcd_dashboard.py "PROBING R_TWI FOR RDA5990 SILICON" 80'))

print("[2] Uploading fixed probe_r_twi_direct.py...")
exec_com.send_file('probe_r_twi_direct.py', '/tmp/probe_r_twi_direct.py')
print("[3] Executing probe_r_twi_direct.py...")
print(exec_com.run_cmd('python3 /tmp/probe_r_twi_direct.py'))
