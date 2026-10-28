import sys

def patch_file(path, old, new):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if old in content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content.replace(old, new, 1))
        print(f"Patched {path}")
    else:
        print(f"Pattern not found in {path}")

# 1. sdio_ops.c
old_sdio = """\tif (rocr)
\t\t*rocr = cmd.resp[mmc_host_is_spi(host) ? 1 : 0];

\treturn err;"""

new_sdio = """\tif (rocr)
\t\t*rocr = cmd.resp[mmc_host_is_spi(host) ? 1 : 0];

\tpr_info("=== [MMC_DEBUG] %s: CMD5 ocr=0x%08x err=%d resp[0]=0x%08x ===\\n",
\t\tmmc_hostname(host), ocr, err, cmd.resp[0]);

\treturn err;"""

patch_file("/root/a33-build/linux/drivers/mmc/core/sdio_ops.c", old_sdio, new_sdio)

# 2. core.c
old_core = """\thost->f_init = freq;

\tpr_debug("%s: %s: trying to init card at %u Hz\\n",
\t\tmmc_hostname(host), __func__, host->f_init);"""

new_core = """\thost->f_init = freq;

\tpr_info("=== [MMC_DEBUG] %s: trying init at %u Hz ===\\n",
\t\tmmc_hostname(host), freq);"""

patch_file("/root/a33-build/linux/drivers/mmc/core/core.c", old_core, new_core)
