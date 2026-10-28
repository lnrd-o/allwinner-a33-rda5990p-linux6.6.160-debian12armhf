#!/bin/sh
# The tablet has no battery-backed clock: set the date from an HTTP Date header once the network is up.
for i in $(seq 1 120); do
    D=$(python3 -c "import urllib.request as u;print(u.urlopen('http://deb.debian.org',timeout=8).headers['Date'])" 2>/dev/null)
    if [ -n "$D" ]; then date -s "$D" >/dev/null && echo "clock set: $D" && exit 0; fi
    sleep 5
done
echo "could not sync clock"; exit 1
