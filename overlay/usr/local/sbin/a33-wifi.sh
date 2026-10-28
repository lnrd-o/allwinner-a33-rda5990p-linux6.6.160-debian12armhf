#!/bin/sh
# a33-wifi.sh - start wpa_supplicant (WEXT) and keep DHCP running on wlan0.
# Credentials live ONLY in /etc/wpa_supplicant/a33-wlan0.conf (create it with: a33-wifi-setup "SSID").
CONF=/etc/wpa_supplicant/a33-wlan0.conf
if [ ! -f "$CONF" ]; then echo "no $CONF - run: a33-wifi-setup \"Your SSID\""; exit 0; fi
for i in $(seq 1 90); do [ -d /sys/class/net/wlan0 ] && break; sleep 1; done
[ -d /sys/class/net/wlan0 ] || { echo "wlan0 never appeared"; exit 1; }
ip link set wlan0 up
wpa_supplicant -B -D wext -i wlan0 -c "$CONF" -P /run/a33-wpa.pid
while true; do
    if wpa_cli -i wlan0 status 2>/dev/null | grep -q wpa_state=COMPLETED; then
        ip -4 addr show wlan0 | grep -q 'inet ' || dhclient -1 wlan0 2>&1 | tail -1
    fi
    sleep 5
done
