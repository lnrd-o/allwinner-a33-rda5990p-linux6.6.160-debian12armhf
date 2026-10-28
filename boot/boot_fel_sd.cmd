# FEL boot of the NEW kernel with the root filesystem on the SD card (no big initramfs upload).
setenv fdt_high ffffffff
setenv bootargs console=ttyS0,115200 console=tty1 console=ttyGS0,115200 root=/dev/mmcblk0p2 rootwait rw panic=10
bootz 0x41000000 - 0x43000000
