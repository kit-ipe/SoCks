fatload mmc 0:1 ${kernel_addr_r} Image.gz
# fatload mmc 0:1 ${ramdisk_addr_r} uRamdisk
setenv bootargs " earlycon clk_ignore_unused console=serial0,115200 console=tty1 root=/dev/mmcblk0p2 rw rootwait"
# booti ${kernel_addr_r} ${ramdisk_addr_r} ${fdt_addr}
booti ${kernel_addr_r} - ${fdt_addr}
