/dts-v1/;

/ {
	description = "Kernel fitImage for PetaLinux/5.15.36+gitAUTOINC+19984dd147/zynqmp-generic";
	#address-cells = <1>;

	images {
		kernel-1 {
			description = "Linux kernel";
			data = /incbin/("<KERNEL_IMG_PATH>");
			type = "kernel";
			arch = "arm64";
			os = "linux";
			compression = "gzip";
			load = <0x200000>;
			entry = <0x200000>;
			hash-1 {
				algo = "sha256";
			};
		};
		fdt-system-top.dtb {
			description = "Flattened Device Tree blob";
			data = /incbin/("<DT_IMG_PATH>");
			type = "flat_dt";
			arch = "arm64";
			compression = "none";
			hash-1 {
				algo = "sha256";
			};
		};
	};

	configurations {
		default = "conf-system-top.dtb";
		conf-system-top.dtb {
			description = "1 Linux kernel, FDT blob";
			kernel = "kernel-1";
			fdt = "fdt-system-top.dtb";
			hash-1 {
				algo = "sha256";
			};
		};
	};
};
