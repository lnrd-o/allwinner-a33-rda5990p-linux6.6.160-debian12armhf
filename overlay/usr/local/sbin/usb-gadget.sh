#!/bin/sh
# usb-gadget.sh - composite USB gadget on the OTG port: RNDIS (network, usb0) + ACM (serial, ttyGS0).
# Replaces the old g_serial-only setup. Windows binds RNDIS automatically (MS OS descriptors).
set -e
mountpoint -q /sys/kernel/config || mount -t configfs none /sys/kernel/config
G=/sys/kernel/config/usb_gadget/a33
[ -d "$G" ] && exit 0
mkdir -p "$G"; cd "$G"
echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0200 > bcdUSB
echo 0x0100 > bcdDevice
echo 0xEF > bDeviceClass
echo 0x02 > bDeviceSubClass
echo 0x01 > bDeviceProtocol
mkdir -p strings/0x409
echo "a33-q8-0001"      > strings/0x409/serialnumber
echo "A33 Q8 Tablet"    > strings/0x409/manufacturer
echo "A33 Linux (USB net + serial)" > strings/0x409/product
mkdir -p configs/c.1/strings/0x409
echo "RNDIS + ACM" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower
mkdir -p functions/rndis.usb0
# Windows: bind the in-box RNDIS driver
echo 1 > os_desc/use
echo 0xcd > os_desc/b_vendor_code
echo MSFT100 > os_desc/qw_sign
echo RNDIS   > functions/rndis.usb0/os_desc/interface.rndis/compatible_id
echo 5162001 > functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id
# fixed MAC addresses so the Windows adapter keeps its identity across boots
echo "02:a3:30:00:00:01" > functions/rndis.usb0/host_addr
echo "02:a3:30:00:00:02" > functions/rndis.usb0/dev_addr
mkdir -p functions/acm.GS0
ln -s functions/rndis.usb0 configs/c.1/
ln -s functions/acm.GS0   configs/c.1/
ln -s configs/c.1 os_desc/
UDC=$(ls /sys/class/udc | head -n1)
[ -n "$UDC" ] || { echo "no UDC found" >&2; exit 1; }
echo "$UDC" > UDC
