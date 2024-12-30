the_ROM_image:
{
image {
	{ type=bootimage, file=<PDI_PATH> }
	{ type=bootloader, file=<PLM_PATH> }
	{ core=psm, file=<PSMFW_PATH> }

}
image {
	id = 0x1c000000, name=apu_subsystem
	{ type=raw, load=0x1000, file=<DTB_PATH> }
	{ core=a72-0, exception_level=el-3, trustzone, file=<ATF_PATH> }
	{ core=a72-0, exception_level=el-2, file=<UBOOT_PATH> }
}
}
