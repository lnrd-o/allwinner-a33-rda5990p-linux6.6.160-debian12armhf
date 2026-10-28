# SPDX-License-Identifier: GPL-2.0
#
# RDA5990 / RDA5890 SDIO Wireless LAN Kernel Module
# Ported for Linux 6.x
#

MODULE_NAME := rda5890

obj-m := $(MODULE_NAME).o

$(MODULE_NAME)-objs := \
	rda5890_if_sdio.o \
	rda5890_dev.o \
	rda5890_txrx.o \
	rda5890_wid.o \
	rda5890_wext.o \
	rda5890_debugfs.o \
	rda5890_sdio_patch.o \
	rda5890_nvram.o \
	rda5890_scan.o

# Disable unused function/variable and alignment warnings from legacy vendor code
ccflags-y += -Wno-unused-function -Wno-unused-variable -Wno-unused-label -Wno-misleading-indentation

KDIR ?= /root/a33-build/linux
ARCH ?= arm
CROSS_COMPILE ?= arm-linux-gnueabihf-

default:
	$(MAKE) -C $(KDIR) M=$(PWD) ARCH=$(ARCH) CROSS_COMPILE=$(CROSS_COMPILE) modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean
	rm -f *.o *.ko *.mod *.mod.c *.mod.o modules.order Module.symvers
