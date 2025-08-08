################
#
# This is a boot script for U-Boot
# Generate boot.scr:
# mkimage -c none -A arm -T script -d boot.cmd.default boot.scr
#
################
fitimage_name=image.ub
kernel_name=Image
ramdisk_name=ramdisk.cpio.gz.u-boot
rootfs_name=rootfs.cpio.gz.u-boot



setenv get_bootargs 'fdt addr $fdtcontroladdr;fdt get value bootargs /chosen bootargs;'
setenv update_bootargs 'if test -n ${launch_ramdisk_init} && test ${bootargs} = "";then if run get_bootargs;then setenv bootargs "\$bootargs launch_ramdisk_init=${launch_ramdisk_init} $extrabootargs";fi;fi'

for boot_target in ${boot_targets};
do
	echo "Trying to load boot images from ${boot_target}"
	if test "${boot_target}" = "jtag" ; then
		run update_bootargs
		booti 0x00200000 0x04000000 0x00001000
	fi
	if test "${boot_target}" = "mmc0" || test "${boot_target}" = "mmc1" || test "${boot_target}" = "usb0" || test "${boot_target}" = "usb1"; then
		if test -e ${devtype} ${devnum}:${distro_bootpart} /uEnv.txt; then
			fatload ${devtype} ${devnum}:${distro_bootpart} 0x00200000 uEnv.txt;
			echo "Importing environment(uEnv.txt) from ${boot_target}..."
			env import -t 0x00200000 $filesize
			if test -n $uenvcmd; then
				echo "Running uenvcmd ...";
				run uenvcmd;
			fi
		fi
		if test -e ${devtype} ${devnum}:${distro_bootpart} /${fitimage_name}; then
			fatload ${devtype} ${devnum}:${distro_bootpart} 0x10000000 ${fitimage_name};
			bootm 0x10000000;
                fi
		if test -e ${devtype} ${devnum}:${distro_bootpart} /${kernel_name}; then
			fatload ${devtype} ${devnum}:${distro_bootpart} 0x00200000 ${kernel_name};
		fi
		if test -e ${devtype} ${devnum}:${distro_bootpart} /system.dtb; then
			fatload ${devtype} ${devnum}:${distro_bootpart} 0x00001000 system.dtb;
			setenv fdtcontroladdr 0x00001000
		fi
		if test -e ${devtype} ${devnum}:${distro_bootpart} /devicetree/openamp.dtbo; then
			fatload ${devtype} ${devnum}:${distro_bootpart} 0x1f01000 devicetree/openamp.dtbo;
			fdt addr 0x00001000
			fdt resize 8192
			fdt apply 0x1f01000
		fi
		run update_bootargs
		if test -e ${devtype} ${devnum}:${distro_bootpart} /${ramdisk_name} && test "${skip_tinyramdisk}" != "yes"; then
			fatload ${devtype} ${devnum}:${distro_bootpart} 0x04000000 ${ramdisk_name};
			booti 0x00200000 0x04000000 0x00001000
		fi
		if test -e ${devtype} ${devnum}:${distro_bootpart} /${rootfs_name} && test "${skip_ramdisk}" != "yes"; then
			fatload ${devtype} ${devnum}:${distro_bootpart} 0x04000000 ${rootfs_name};
			booti 0x00200000 0x04000000 0x00001000
		fi
		booti 0x00200000 - 0x00001000
	fi
	if test "${boot_target}" = "xspi0" || test "${boot_target}" = "xspi1" || test "${boot_target}" = "qspi" || test "${boot_target}" = "qspi0"; then
		sf probe 0 0 0;
		sf read 0x10000000 0xF40000 0x6400000
		bootm 0x10000000;
		echo "Booting using Fit image failed"

		sf read 0x00200000 0xF00000 0x1D00000
		sf read 0x04000000 0x2E00000 0x4000000
		run update_bootargs
		booti 0x00200000 0x04000000 0x00001000;
		echo "Booting using Separate images failed"
	fi
	if test "${boot_target}" = "nand" || test "${boot_target}" = "nand0"; then
		nand info;
		nand read 0x10000000 0x4180000 0x6400000
		bootm 0x10000000;
		echo "Booting using Fit image failed"

		nand read 0x00200000 0x4100000 0x3200000
		nand read 0x04000000 0x8200000 0x3200000
		run update_bootargs
		booti 0x00200000 0x04000000 0x00001000;
		echo "Booting using Separate images failed"
	fi
	if test "${boot_target}" = "nor" || test "${boot_target}" = "nor0"; then
		cp.b 0xF40000 0x10000000 0x6400000
		bootm 0x10000000;
		echo "Booting using Fit image failed"

		cp.b 0xF00000 0x00200000 0x1D00000
		cp.b 0x2E00000 0x04000000 0x4000000
		run update_bootargs
		booti 0x00200000 0x04000000 0x00001000;
		echo "Booting using Separate images failed"
fi
done
