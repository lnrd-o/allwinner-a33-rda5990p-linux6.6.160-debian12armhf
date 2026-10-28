#include <linux/fs.h>
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
