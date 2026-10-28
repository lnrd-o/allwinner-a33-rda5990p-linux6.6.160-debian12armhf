#include <linux/module.h>
#include <linux/init.h>
#include <linux/device.h>
#include <linux/platform_device.h>
#include <linux/mmc/host.h>
#include <linux/mmc/card.h>
#include <linux/io.h>
#include <linux/delay.h>

static void __iomem *pio;

/* PB03 = SCL, PB02 = SDA */
static void set_scl(int val)
{
    u32 cfg = readl(pio + 0x24);
    if (val) {
        cfg &= ~(7 << 12); /* PB3 input */
        writel(cfg, pio + 0x24);
    } else {
        u32 dat = readl(pio + 0x34) & ~(1 << 3);
        writel(dat, pio + 0x34);
        cfg = (cfg & ~(7 << 12)) | (1 << 12); /* PB3 output low */
        writel(cfg, pio + 0x24);
    }
}

static void set_sda(int val)
{
    u32 cfg = readl(pio + 0x24);
    if (val) {
        cfg &= ~(7 << 8); /* PB2 input */
        writel(cfg, pio + 0x24);
    } else {
        u32 dat = readl(pio + 0x34) & ~(1 << 2);
        writel(dat, pio + 0x34);
        cfg = (cfg & ~(7 << 8)) | (1 << 8); /* PB2 output low */
        writel(cfg, pio + 0x24);
    }
}

static int get_sda(void)
{
    return (readl(pio + 0x34) >> 2) & 1;
}

static void i2c_d(void) { udelay(20); }

static void i2c_start(void)
{
    set_sda(1); set_scl(1); i2c_d();
    set_sda(0); i2c_d();
    set_scl(0); i2c_d();
}

static void i2c_stop(void)
{
    set_sda(0); i2c_d();
    set_scl(1); i2c_d();
    set_sda(1); i2c_d();
}

static int i2c_wb(u8 b)
{
    int i, ack;
    for (i = 0; i < 8; i++) {
        int bit = (b >> (7 - i)) & 1;
        set_sda(bit); i2c_d();
        set_scl(1); i2c_d();
        set_scl(0); i2c_d();
    }
    set_sda(1); i2c_d();
    set_scl(1); i2c_d();
    ack = (get_sda() == 0);
    set_scl(0); i2c_d();
    return ack;
}

static u8 i2c_rb(int ack_bit)
{
    int i;
    u8 byte = 0;
    set_sda(1); i2c_d();
    for (i = 0; i < 8; i++) {
        set_scl(1); i2c_d();
        byte = (byte << 1) | get_sda();
        set_scl(0); i2c_d();
    }
    set_sda(ack_bit ? 0 : 1); i2c_d();
    set_scl(1); i2c_d();
    set_scl(0); i2c_d();
    set_sda(1); i2c_d();
    return byte;
}

static int rda_write(u8 addr, u8 reg, u16 val)
{
    i2c_start();
    if (!i2c_wb((addr << 1) | 0)) { i2c_stop(); return -EIO; }
    if (!i2c_wb(reg)) { i2c_stop(); return -EIO; }
    if (!i2c_wb((val >> 8) & 0xff)) { i2c_stop(); return -EIO; }
    if (!i2c_wb(val & 0xff)) { i2c_stop(); return -EIO; }
    i2c_stop();
    return 0;
}

static int rda_read(u8 addr, u8 reg, u16 *val)
{
    u8 b1, b2;
    i2c_start();
    if (!i2c_wb((addr << 1) | 0)) { i2c_stop(); return -EIO; }
    if (!i2c_wb(reg)) { i2c_stop(); return -EIO; }
    i2c_start();
    if (!i2c_wb((addr << 1) | 1)) { i2c_stop(); return -EIO; }
    b1 = i2c_rb(1);
    b2 = i2c_rb(0);
    i2c_stop();
    *val = (b1 << 8) | b2;
    return 0;
}

#define CHIP_ADDR 0x14

static const u16 wifi_en_data[][2] = {
    {0x3f, 0x0001}, {0x23, 0x8FA1}, {0x31, 0x0B40}, {0x24, 0x80C8},
    {0x27, 0x4925}, {0x31, 0x8140}, {0x32, 0x0113}, {0x3F, 0x0000},
};

/* Version E RF table (for chip version 0x0045) */
static const u16 wifi_rf_init_data_verE[][2] = {
    {0x3f, 0x0000}, {0x06, 0x0101}, {0x07, 0x0101}, {0x08, 0x0101},
    {0x09, 0x0101}, {0x0A, 0x002C}, {0x0D, 0x0507}, {0x0E, 0x2300},
    {0x0F, 0x5689}, {0x10, 0x0f78}, {0x11, 0x0602}, {0x13, 0x0652},
    {0x14, 0x8886}, {0x15, 0x0990}, {0x16, 0x049f}, {0x17, 0x0990},
    {0x18, 0x049F}, {0x19, 0x3C01}, {0x1C, 0x0934}, {0x1D, 0xFF00},
    {0x20, 0x06E4}, {0x21, 0x0ACF}, {0x22, 0x24DC}, {0x23, 0x23FF},
    {0x24, 0x00FC}, {0x26, 0x004F}, {0x27, 0x171D}, {0x28, 0x031D},
    {0x2A, 0x2860}, {0x2B, 0x0800},
};

static const u16 wifi_dc_cal_data[][2] = {
    {0x3f, 0x0000}, {0x30, 0x0248}, {0x30, 0x0249},
};

static const u16 wifi_dig_reset_data[][2] = {
    {0x3F, 0x0001}, {0x31, 0x8D40}, {0x31, 0x8F40}, {0x31, 0x8b40}, {0x3F, 0x0000},
};

static int __init rescan_init(void)
{
    struct device *dev;
    struct mmc_host *host;
    void (*fn_mmc_rescan)(struct work_struct *);
    void (*fn_mmc_power_up)(struct mmc_host *, u32);
    void __iomem *rtc;
    void __iomem *rpio;
    u32 val;
    int i;
    u16 temp, wlan_ver = 0;

    pr_info("rescan_mmc: [1] Initializing hardware lines for RDA5990 combo chip...\n");

    /* 1. Enable RTC 32.768 kHz LOSC clock output */
    rtc = ioremap(0x01f00000, 0x1000);
    if (rtc) {
        val = readl(rtc + 0x60);
        writel(val | 1, rtc + 0x60);
        iounmap(rtc);
    }

    /* 2. Configure Port L pins: PL06, PL11, PL08 */
    rpio = ioremap(0x01f02c00, 0x400);
    if (rpio) {
        writel(0x11111100, rpio + 0x00);
        writel(0x00001111, rpio + 0x04);
        writel(0, rpio + 0x10);
        msleep(100);
        writel((1 << 6) | (1 << 11) | (1 << 2) | (1 << 3) | (1 << 4), rpio + 0x10);
        msleep(50);
        writel((1 << 6) | (1 << 11) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 8), rpio + 0x10);
        msleep(100);
        iounmap(rpio);
    }

    /* 3. Setup Port B for bit-bang I2C */
    pio = ioremap(0x01c20800, 0x400);
    if (!pio) {
        pr_err("rescan_mmc: Failed to map PIO!\n");
        return -ENOMEM;
    }
    val = readl(pio + 0x44);
    val = (val & ~0x000000f0) | 0x00000050;
    writel(val, pio + 0x44);
    set_scl(1);
    set_sda(1);
    msleep(10);

    /* 4. Find mmc host on 1c10000.mmc */
    dev = bus_find_device_by_name(&platform_bus_type, NULL, "1c10000.mmc");
    if (!dev) {
        pr_err("rescan_mmc: 1c10000.mmc device not found\n");
        iounmap(pio);
        return -ENODEV;
    }
    host = dev_get_drvdata(dev);
    if (!host) {
        pr_err("rescan_mmc: mmc_host not found on 1c10000.mmc\n");
        iounmap(pio);
        put_device(dev);
        return -ENODEV;
    }

    host->pwrseq = NULL;
    host->caps |= MMC_CAP_NONREMOVABLE;

    fn_mmc_power_up = (void (*)(struct mmc_host *, u32))0xc06ce2b0;
    pr_info("rescan_mmc: Calling mmc_power_up...\n");
    fn_mmc_power_up(host, host->ocr_avail);
    msleep(50);

    /* 5. Execute RDA Vendor I2C Wakeup Sequence */
    pr_info("rescan_mmc: Executing RDA5990 I2C wakeup sequence on PB03/PB02...\n");
    for (i = 0; i < ARRAY_SIZE(wifi_en_data); i++) {
        rda_write(CHIP_ADDR, wifi_en_data[i][0], wifi_en_data[i][1]);
        if (wifi_en_data[i][0] == 0x31) msleep(10);
    }

    rda_write(CHIP_ADDR, 0x3f, 0x0001);
    if (rda_read(CHIP_ADDR, 0x22, &temp) == 0) {
        temp = (temp | 0x0200) & ~(1 << 14);
        rda_write(CHIP_ADDR, 0x22, temp);
    }
    rda_read(CHIP_ADDR, 0x21, &wlan_ver);
    pr_info("rescan_mmc: RDA5990 WLAN Version = 0x%04x (Configuring VerE RF table)\n", wlan_ver);

    /* Write VerE RF initialization table */
    for (i = 0; i < ARRAY_SIZE(wifi_rf_init_data_verE); i++)
        rda_write(CHIP_ADDR, wifi_rf_init_data_verE[i][0], wifi_rf_init_data_verE[i][1]);
    msleep(5);

    for (i = 0; i < ARRAY_SIZE(wifi_dc_cal_data); i++)
        rda_write(CHIP_ADDR, wifi_dc_cal_data[i][0], wifi_dc_cal_data[i][1]);
    msleep(50);

    for (i = 0; i < ARRAY_SIZE(wifi_dig_reset_data); i++)
        rda_write(CHIP_ADDR, wifi_dig_reset_data[i][0], wifi_dig_reset_data[i][1]);
    msleep(20);

    pr_info("rescan_mmc: RDA5990 Silicon successfully energized over I2C with VerE RF settings!\n");
    iounmap(pio);

    /* 6. Trigger MMC Rescan */
    host->rescan_entered = 0;
    host->rescan_disable = 0;

    fn_mmc_rescan = (void (*)(struct work_struct *))0xc06ce978;
    pr_info("rescan_mmc: Directly calling mmc_rescan on %s...\n", mmc_hostname(host));
    fn_mmc_rescan(&host->detect.work);

    pr_info("rescan_mmc: mmc_rescan finished! card=%p\n", host->card);
    put_device(dev);
    return 0;
}

static void __exit rescan_exit(void) {}

module_init(rescan_init);
module_exit(rescan_exit);
MODULE_LICENSE("GPL");
