import os
import re

DIR = '/root/a33-build/rda5990_ported'

def patch_file(filename, replacements):
    path = os.path.join(DIR, filename)
    if not os.path.exists(path):
        print(f"Skipping {path}: not found")
        return
    with open(path, 'r', encoding='latin-1') as f:
        content = f.read()
    orig = content
    for old, new in replacements:
        content = content.replace(old, new)
    if content != orig:
        with open(path, 'w', encoding='latin-1') as f:
            f.write(content)
        print(f"Successfully patched {filename}")
    else:
        print(f"No changes made to {filename}")

# 1. rda5890_dev.h
patch_file('rda5890_dev.h', [
    ('#include <linux/wakelock.h>', '''#include <linux/version.h>
#include <linux/uaccess.h>
#include <linux/etherdevice.h>
#ifndef compare_ether_addr
static inline int compare_ether_addr(const u8 *a, const u8 *b) {
    return !ether_addr_equal(a, b);
}
#endif
#if LINUX_VERSION_CODE >= KERNEL_VERSION(2, 6, 37)
struct wake_lock { int dummy; };
#define WAKE_LOCK_SUSPEND 0
static inline void wake_lock_init(struct wake_lock *lock, int type, const char *name) {}
static inline void wake_lock_destroy(struct wake_lock *lock) {}
static inline void wake_lock(struct wake_lock *lock) {}
static inline void wake_unlock(struct wake_lock *lock) {}
#else
#include <linux/wakelock.h>
#endif''')
])

# 2. rda5890_if_sdio.c
patch_file('rda5890_if_sdio.c', [
    ('extern void rk29_sdio_irq_enable(int enable);', '// extern void rk29_sdio_irq_enable(int enable);'),
    ('extern void mmc_rescan_slot(int id);', '// extern void mmc_rescan_slot(int id);'),
    ('mmc_rescan_slot(0);', '// mmc_rescan_slot(0);'),
    ('extern void mmc_remove(int id);', '// extern void mmc_remove(int id);'),
    ('mmc_remove(0);', '// mmc_remove(0);'),
    ('''out:
    RDA5890_DBGLAP(RDA5890_DA_SDIO, RDA5890_DL_DEBUG,
    	"%s <<< ret=%d \\n", __func__, ret);   
    return ret;
}''', '''out:
    RDA5890_DBGLAP(RDA5890_DA_SDIO, RDA5890_DL_DEBUG,
    	"%s <<< ret=%d \\n", __func__, ret);   
    return;
}'''),
])

# 3. rda5890_txrx.c
patch_file('rda5890_txrx.c', [
    ('dev->trans_start = jiffies;', '''#if LINUX_VERSION_CODE >= KERNEL_VERSION(4, 7, 0)
	netif_trans_update(dev);
#else
	dev->trans_start = jiffies;
#endif'''),
    ('netif_rx_ni(skb);', '''#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 18, 0)
		netif_rx(skb);
#else
		netif_rx_ni(skb);
#endif'''),
])

# 4. rda5890_dev.c
patch_file('rda5890_dev.c', [
    ('#include <linux/jiffies.h>', '''#include <linux/jiffies.h>
#include <linux/etherdevice.h>'''),
    ('static void rda5890_tx_timeout(struct net_device *dev)', '''#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 6, 0)
static void rda5890_tx_timeout(struct net_device *dev, unsigned int txqueue)
#else
static void rda5890_tx_timeout(struct net_device *dev)
#endif'''),
    ('dev = alloc_netdev_mq(sizeof(struct rda5890_private), "wlan%d", ether_setup, 1);', '''#if LINUX_VERSION_CODE >= KERNEL_VERSION(3, 17, 0)
	dev = alloc_etherdev(sizeof(struct rda5890_private));
	if (dev) strscpy(dev->name, "wlan%d", sizeof(dev->name));
#else
	dev = alloc_netdev_mq(sizeof(struct rda5890_private), "wlan%d", ether_setup, 1);
#endif'''),
    ('.ndo_do_ioctl = rda5890_ioctl', '''#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 15, 0)
	.ndo_siocdevprivate = (void *)rda5890_ioctl,
#else
	.ndo_do_ioctl = rda5890_ioctl,
#endif'''),
    ('memcpy(priv->dev->dev_addr, phwaddr->sa_data, ETH_ALEN);', '''#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 17, 0)
	eth_hw_addr_set(priv->dev, phwaddr->sa_data);
#else
	memcpy(priv->dev->dev_addr, phwaddr->sa_data, ETH_ALEN);
#endif'''),
    ('random_ether_addr(mac_addr);', '''#if LINUX_VERSION_CODE >= KERNEL_VERSION(3, 6, 0)
            eth_random_addr(mac_addr);
#else
            random_ether_addr(mac_addr);
#endif'''),
    ('memcpy(priv->dev->dev_addr, mac_addr, ETH_ALEN);', '''#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 17, 0)
    	eth_hw_addr_set(priv->dev, mac_addr);
#else
    	memcpy(priv->dev->dev_addr, mac_addr, ETH_ALEN);
#endif'''),
])

# 5. rda5890_wid.c
patch_file('rda5890_wid.c', [
    ('*ssid_len > 0? ssid:"NULL"', '*ssid_len > 0 ? (char *)ssid : "NULL"'),
])

# 6. rda5890_wext.c
patch_file('rda5890_wext.c', [
    ('!compare_ether_addr(', 'ether_addr_equal('),
])

# 7. rda5890_sdio_patch.c
patch_file('rda5890_sdio_patch.c', [
    ('4, &ptr_payload);', '4, (char **)&ptr_payload);'),
    ('ret = rda5890_set_core_init_polling(priv, data[8*index], 8);', 'ret = rda5890_set_core_init_polling(priv, &data[8*index], 8);'),
    ('ret = rda5890_set_core_init_polling(priv, data[8*index], count%8);', 'ret = rda5890_set_core_init_polling(priv, &data[8*index], count%8);'),
    ('ret = rda5890_set_core_init(priv, data[8*index], 8);', 'ret = rda5890_set_core_init(priv, &data[8*index], 8);'),
    ('ret = rda5890_set_core_init(priv, data[8*index], count%8);', 'ret = rda5890_set_core_init(priv, &data[8*index], count%8);'),
    ('ret = rda5890_set_core_patch_polling(priv, data[8*index], 8);', 'ret = rda5890_set_core_patch_polling(priv, &data[8*index], 8);'),
    ('ret = rda5890_set_core_patch_polling(priv, data[8*index], count%8);', 'ret = rda5890_set_core_patch_polling(priv, &data[8*index], count%8);'),
    ('ret = rda5890_set_core_patch(priv, data[8*index], 8);', 'ret = rda5890_set_core_patch(priv, &data[8*index], 8);'),
    ('ret = rda5890_set_core_patch(priv, data[8*index], count%8);', 'ret = rda5890_set_core_patch(priv, &data[8*index], count%8);'),
    ('extern void export_wifi_eirq_enable();', 'void __attribute__((weak)) export_wifi_eirq_enable(void) {}'),
])

# 8. rda5890_scan.c
patch_file('rda5890_scan.c', [
    ('case WLAN_EID_GENERIC:', '''#ifndef WLAN_EID_GENERIC
#ifdef WLAN_EID_VENDOR_SPECIFIC
#define WLAN_EID_GENERIC WLAN_EID_VENDOR_SPECIFIC
#else
#define WLAN_EID_GENERIC 221
#endif
#endif
		case WLAN_EID_GENERIC:'''),
])

# 9. rda5890_nvram.c
nvram_code = '''#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/version.h>

#define WIFI_NVRAM_FILE_NAME "/data/nvram/APCFG/APRDEB/RDAWIFI"

static int nvram_read(char *filename, char *buf, ssize_t len, int offset)
{
    struct file *fd;
    ssize_t retLen = -1;
    loff_t pos = offset;

    fd = filp_open(filename, O_RDONLY, 0);
    if (IS_ERR(fd)) {
        return -1;
    }

#if LINUX_VERSION_CODE >= KERNEL_VERSION(4, 14, 0)
    retLen = kernel_read(fd, buf, len, &pos);
#else
    {
        mm_segment_t old_fs = get_fs();
        set_fs(KERNEL_DS);
        if (fd->f_op && fd->f_op->read)
            retLen = fd->f_op->read(fd, buf, len, &pos);
        set_fs(old_fs);
    }
#endif

    filp_close(fd, NULL);
    return retLen;
}

static int nvram_write(char *filename, char *buf, ssize_t len, int offset)
{
    struct file *fd;
    ssize_t retLen = -1;
    loff_t pos = offset;

    fd = filp_open(filename, O_WRONLY | O_CREAT, 0644);
    if (IS_ERR(fd)) {
        return -1;
    }

#if LINUX_VERSION_CODE >= KERNEL_VERSION(4, 14, 0)
    retLen = kernel_write(fd, buf, len, &pos);
#else
    {
        mm_segment_t old_fs = get_fs();
        set_fs(KERNEL_DS);
        if (fd->f_op && fd->f_op->write)
            retLen = fd->f_op->write(fd, buf, len, &pos);
        set_fs(old_fs);
    }
#endif

    filp_close(fd, NULL);
    return retLen;
}

int rda5890_read_mac(char* buf)
{
    return nvram_read(WIFI_NVRAM_FILE_NAME, buf, 6, 0);
}

int rda5890_write_mac(char * buf)
{
    return nvram_write(WIFI_NVRAM_FILE_NAME, buf, 6, 0);
}
'''
with open(os.path.join(DIR, 'rda5890_nvram.c'), 'w', encoding='latin-1') as f:
    f.write(nvram_code)
print("Successfully replaced rda5890_nvram.c")

# 6. rda5890_debugfs.c
patch_file('rda5890_debugfs.c', [
    ('.open = open_file_generic,', '.open = simple_open,'),
])

print("Patching complete!")
