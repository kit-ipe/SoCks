the_ROM_image:
{
	[bootloader, destination_cpu=a53-0] <FSBL_PATH>
	[pmufw_image] <PMUFW_PATH>
	[destination_cpu=a53-0, exception_level=el-3, trustzone] <ATF_PATH>
	[destination_cpu=a53-0, load=0x00100000, partition_owner=fsbl] <DTB_PATH>
	[destination_cpu=a53-0, exception_level=el-2] <UBOOT_PATH>
}
