# SoCks (SoC Blocks)

SoCks (short for SoC blocks) is a lightweight and modular framework to build complete embedded Linux images for SoC devices. Currently, the framework focuses on AMD Xilinx ZynqMP devices, but also offers experimental support for AMD Xilinx Versal devices.

## Quick start

### Installation

SoCks is available as a python package, but currently only in this repo and not in a software repository like PyPI. This might change in the future.

It is recommended to install SoCks in a python environment. You can create a new one with the following command:
```
$ python3.10 -m venv ~/py_envs/socks
```

In the python environment run:
```
$ cd <THIS REPO>/tool
$ pip install -U .
```

For a development installation use the following commands instead:
```
$ cd <THIS REPO>/tool
$ pip install -e .
```

### Building an image

This section assumes that you already have a SoCks project. To be able to use the SoCks command you have to be in a SoCks project directory (A directory that contains `project.yml`).
In such a directory you can run the following command to build the full image:
```
$ socks all build
```
It is also possible to build individual blocks with:
```
$ socks <BLOCK> build
```
If you need further assistance you can put `--help` behind every sub-command. E.g. like this:
```
$ socks --help
$ socks fsbl --help
```
SoCks supports tab completion, but you have to enable it manually in every new shell with the following command:
```
$ eval "$(register-python-argcomplete socks)"
```

## Development flow

### Project Configuration

A SoCks project is fully described by the YAML file `project.yml`. This file must be present in the root directory of a SoCks project. To support the reuse of project configuration snippets, SoCks allows to import such snippets as follows:

```
import:
  - project-zynqmp-default.yml
```

The imported files are imported in the order in which they are declared and before anything else in the file is processed. This means that it is posible to overwrite the information from the imported configuration file in the file that imports it.

The SoCks framework provides a base configuration files for every architecture that is supported. It is recommended to use one of these files in every SoCks project, to reduce the information in the project configuration file to project specific configurations. The following list gives an overview:
- `project-zynqmp-default.yml`
- `project-versal-default.yml`

SoCks can print the full project configuration with all includes resolved to the standard output:
```
$ socks --show-configuration
```

### Creating patch files

In some case one needs to modify source files for a block without having access to the source repo. Examples are the source repo of the Linux Kernel or U-Boot. For such cases SoCks allows to patch the source repo. The patches are automatically applied to the repo after download. In case you plan to do major changes to the repo, it might be more suitable to fork the original repo instead of patching it.

1. Fetch the source repo of the block, if it does not already exist:
    ```
    $ socks fsbl prepare
    ```

2. Enter the local repo and do the modifications you would like to do:
    ```
    $ cd temp/fsbl/repo/runtime-generated
    $ nano xfsbl_hooks.c
    ```

3. Create one or multiple commits:
    ```
    $ git add xfsbl_hooks.c
    $ git commit -m "Add a meaningful description here"
    ```

4. Move back to the root directory of the SoCks project and create the patches:
    ```
    $ socks fsbl create-patches
    ```

## Available Builders (ZynqMP)

### ZynqMP_AlmaLinux_RootFS_Builder

This builder is designed to build an AlmaLinux 8 or 9 root file system. Furthermore, it allows to modify the base root file system by adding files built by other blocks like Kernel modules, device tree overlays and FPGA bitstreams. It is also possible to add external files to the root file system and to modify it in various ways with a custom shell script.

#### Block Configuration

The default configuration `project-zynqmp-default` does not contain any configuration for this block. The entire configuration must be carried out in the project configuration file.

Configuration example:
```
rootfs:
  source: "build"
  builder: "ZynqMP_AlmaLinux_RootFS_Builder"
  project:
    release: "9"
    extra_rpms: ["python3", "nano", "vim"]
    build_time_fs_layer:
      - src_block: "vivado"
        src_name: "*.bit"
        dest_path: "/lib/firmware"
        dest_name: "serenity_s1_k26_pl.bit"
        dest_owner_group: "root:root"
        dest_permissions: "u=rw,go=r"
      - src_block: "devicetree"
        src_name: "*.dtbo"
        dest_path: "/etc/dt-overlays"
        dest_owner_group: "root:root"
        dest_permissions: "u=rwX,go=rX"
      - src_block: "vivado"
        src_name: "addrtab"
        dest_path: "/etc/serenity"
        dest_name: "zynq-addrtab"
    users:
      - name: "root"
        pw_hash: "$1$abFTnq2K$2Obyh.ZKwwExNujN/aCjQ." # alma
      - name: "kria"
        pw_hash: "$1$DaewGWW3$9Qauc9z14L7B9PbF5SuE8." # regular.user
        groups: ["wheel", "dialout"]
    import_src: "https://serenity.web.cern.ch/.../almalinux9_rootfs.tar.gz"
    add_build_info: false
    dependencies:
      kernel: "temp/kernel/output/bp_kernel_*.tar.gz"
      devicetree: "temp/devicetree/output/bp_devicetree*.tar.gz"
      vivado: "temp/vivado/output/bp_vivado*.tar.gz"
  container:
    image: "alma9-rootfs-builder-alma9"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_AMD_Kernel_Builder`.
- **project -> release**: The release version of AlmaLinux to be built. Options are:
  - 8
  - 9
- **project -> extra_rpms [optional]**: A list of additional rpm packages to be installed in the root file system. Make sure the repos that contain these files are available to dnf. See section *External Source Files* for more details.
- **project -> build_time_fs_layer [optional]**: A list of dicts describing files and folders generated by other blocks and are to be added to the root file system.
- **project -> build_time_fs_layer -> [N] -> src_block**: The ID of the block that generates this file or folder.
- **project -> build_time_fs_layer -> [N] -> src_name**: The name of the file or folder in the block package of the source block.
- **project -> build_time_fs_layer -> [N] -> dest_path**: The target path in the root file system where this file or folder is to be placed.
- **project -> build_time_fs_layer -> [N] -> dest_name [optional]**: This parameter allows to rename the file or folder in the target location. It can be omitted if the source name is to be used.
- **project -> build_time_fs_layer -> [N] -> dest_owner_group [optional]**: This parameter allows to set owner and group of the file or directory in the target location.
- **project -> build_time_fs_layer -> [N] -> dest_permissions [optional]**: This parameter allows to set the file permission in the target location.
- **project -> users**: A list of dicts describing users to be added to the root file system.
- **project -> users -> [N] -> name**: The name of the user.
- **project -> users -> [N] -> pw_hash**: The password of the user in hashed form. The hashed password can be generated with the following command: `openssl passwd -1`.
- **project -> users -> [N] -> groups**: A list of groups the users is to be added to.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> add_build_info**: A binary parameter that specifies whether build-related information should be built into the root file system. If it is set to `true`, SoCks creates the file `/etc/fs_build_info` with build related information in the root file system.
- **project -> dependencies**: A dict with all dependencies required by this builder to build this block. The keys of the dict are block IDs. The values of the dict are paths to the respective block packages. All paths are relative to the SoCks project directory. In almost all cases, the values from the example configuration can be used.
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of AlmaLinux to be built. The following images are available for this block:
  - `petalinux-rootfs-builder-alma8`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks requires external files in order to build this block. The following template packages are available:
- **AlmaLinux8**: Contains template files to build an AlmaLinux 8 root file system. The optional file `mod_base_install.sh` allows to modify the base root file system after all packages have been added, but before any other modifications have been made to it. The optional folder `predefined_fs_layers` allows to add static layers that are added to the base root file system. Every layer requires a shell script that is used to add the layer. The file `dnf_build_time.conf` is the dnf configuration used at build time. This file must contain all repositories that are required to build the root file system including all package specified.
- **AlmaLinux9**: Contains template files to build an AlmaLinux 9 root file system. The files and folders in this package are equivalent to the ones in the *AlmaLinux8* package.

### ZynqMP_AMD_ATF_Builder

This builder is designed to build the [AMD fork](https://github.com/Xilinx/arm-trusted-firmware) of the [Trusted Firmware](https://developer.arm.com/documentation/102418/0101/Software-architecture/Trusted-Firmware) for ARM processors of the Armv8-A architecture. This software is recommended for the Application Processing Unit (APU) of AMD ZynqMP SoCs.

#### Block Configuration

The default configuration `project-zynqmp-default` contains a complete configuration for this block. You can use it in your SoCks project configuration as follows:
```
import:
  - project-zynqmp-default.yml
``` 

Configuration example:
```
atf:
  source: "build"
  builder: "ZynqMP_AMD_ATF_Builder"
  project:
    build_srcs:
      source: "https://github.com/Xilinx/arm-trusted-firmware.git"
      branch: "xilinx-v{{external_tools/xilinx/version}}"
    import_src: "https://serenity.web.cern.ch/.../atf.tar.gz"
  container:
    image: "atf-builder-alma9"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_AMD_Kernel_Builder`.
- **project -> build_srcs -> source**: The source to be used to build this block in URI format. Options are:
  - The URL of a git repository. In this case the string must start with `https://` or `ssh://`.
  - The path to a local folder, e.g. if the repo was checked out manually. In this case the string must start with `file://`.
- **project -> build_srcs -> branch [optional]**: Specifies the branch of the source repo to be used. Only permitted if *project -> build_srcs -> source* contains the URL of a git repo.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> patches**: A list of patch files that are automatically applied to the build sources (*project -> build_srcs*) by SoCks. SoCks will automatically add new patches here if you create them with the command `create-patches`. Patch files must be located in `src/atf/patches`.
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of the Vivado toolset you are using. The following images are available for this block:
  - `atf-builder-alma8`
  - `atf-builder-alma9`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks does not require any external files in order to build this block. However, it is possible to create patches for the source repo.

### ZynqMP_AMD_Devicetree_Builder

This builder is designed to build the Devicetree for U-Boot and the Linux system running on the Application Processing Unit (APU) of AMD ZynqMP SoCs.

#### Block Configuration

The default configuration `project-zynqmp-default` contains a complete configuration for this block. You can use it in your SoCks project configuration as follows:
```
import:
  - project-zynqmp-default.yml
``` 

Configuration example:
```
devicetree:
  source: "build"
  builder: "ZynqMP_AMD_Devicetree_Builder"
  project:
    build_srcs:
      source: "https://github.com/Xilinx/device-tree-xlnx.git"
      branch: "xilinx_v{{external_tools/xilinx/version}}"
    import_src: "https://serenity.web.cern.ch/.../devicetree.tar.gz"
    dependencies:
      vivado: "temp/vivado/output/bp_vivado_*.tar.gz"
    dt_includes:
      - system-user.dtsi
  container:
    image: "amd-xilinx-tools-alma8"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_AMD_Kernel_Builder`.
- **project -> build_srcs -> source**: The source to be used to build this block in URI format. Options are:
  - The URL of a git repository. In this case the string must start with `https://` or `ssh://`.
  - The path to a local folder, e.g. if the repo was checked out manually. In this case the string must start with `file://`.
- **project -> build_srcs -> branch [optional]**: Specifies the branch of the source repo to be used. Only permitted if *project -> build_srcs -> source* contains the URL of a git repo.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> dependencies**: A dict with all dependencies required by this builder to build this block. The keys of the dict are block IDs. The values of the dict are paths to the respective block packages. All paths are relative to the SoCks project directory. In almost all cases, the values from the example configuration can be used.
- **project -> dt_includes**: A list of user defined device tree source files to be included in the device tree. The files must be located in `src/devicetree/dt_includes`.
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of the Vivado toolset you are using. The following images are available for this block:
  - `amd-xilinx-tools-alma8`
  - `amd-xilinx-tools-alma9`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks requires external files in order to build this block and it is possible to create patches for the source repo. The following template packages are available:
- **dt_includes_only**: Contains a template of `system-user.dtsi`. This file can be used to add project specific information to the devicetree.
- **dt_includes_and_dt_overlays**: Same as **dt_includes_only** plus a template that shows how to add sources for devicetree overlays that can be applied at runtime. All files in `dt_overlays` that match `*.dtsi` are automatically build as devicetree overlays. There is no need to specify them in `project.yml`. It is possible to include `pl.dtsi` in devicetree overlays. The file `pl.dtsi` contains an autogenerated devicetree snippet that covers the Programmable Logic (PL).

### ZynqMP_AMD_FSBL_Builder

This builder is designed to build the First Stage Boot Loader (FSBL) for the Application Processing Unit (APU) of AMD ZynqMP SoCs.

#### Block Configuration

The default configuration `project-zynqmp-default` contains a complete configuration for this block. You can use it in your SoCks project configuration as follows:
```
import:
  - project-zynqmp-default.yml
``` 

Configuration example:
```
fsbl:
  source: "build"
  builder: "ZynqMP_AMD_FSBL_Builder"
  project:
    import_src: "https://serenity.web.cern.ch/.../fsbl.tar.gz"
    dependencies:
      vivado: "temp/vivado/output/bp_vivado_*.tar.gz"
    patches:
      - 0001-Add-gitignore.patch
  container:
    image: "amd-xilinx-tools-alma8"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_AMD_FSBL_Builder`.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> dependencies**: A dict with all dependencies required by this builder to build this block. The keys of the dict are block IDs. The values of the dict are paths to the respective block packages. All paths are relative to the SoCks project directory. In almost all cases, the values from the example configuration can be used.
- **project -> patches**: A list of patch files that are automatically applied to the build sources (*project -> build_srcs*) by SoCks. SoCks will automatically add new patches here if you create them with the command `create-patches`. Patch files must be located in `src/fsbl/patches`.
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of the Vivado toolset you are using. The following images are available for this block:
  - `amd-xilinx-tools-alma8`
  - `amd-xilinx-tools-alma9`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks does not require any external files in order to build this block. However, it is possible to create patches for the source repo. The following template packages are available:
- **universal**: Contains a default gitignore file for the autogenerated repo.

### ZynqMP_AMD_Image_Builder

This builder is designed to build deployable image files for AMD ZynqMP SoCs (`BOOT.BIN`, `boot.scr`, `image.ub`). Furthermore, it allows to build a fully contained Image file that can e.g. be written to an SD card using `dd`. 

#### Block Configuration

The default configuration `project-zynqmp-default` contains an almost complete configuration for this block. At least one of the dependencies `ramfs` or `rootfs` has to be added. You can use the default configuration in your SoCks project configuration as follows:
```
import:
  - project-zynqmp-default.yml
blocks:
  image:
    project:
      dependencies:
        ramfs: "temp/ramfs/output/bp_ramfs_*.tar.gz"
        rootfs: "temp/rootfs/output/bp_rootfs_*.tar.gz"
``` 

Configuration example:
```
image:
  source: "build"
  builder: "ZynqMP_AMD_Image_Builder"
  project:
    import_src: "https://serenity.web.cern.ch/.../image.tar.gz"
    dependencies:
      atf: "temp/atf/output/bp_atf_*.tar.gz"
      devicetree: "temp/devicetree/output/bp_devicetree_*.tar.gz"
      fsbl: "temp/fsbl/output/bp_fsbl_*.tar.gz"
      kernel: "temp/kernel/output/bp_kernel_*.tar.gz"
      pmu_fw: "temp/pmu_fw/output/bp_pmu_fw_*.tar.gz"
      uboot: "temp/uboot/output/bp_uboot_*.tar.gz"
      vivado: "temp/vivado/output/bp_vivado_*.tar.gz"
      ramfs: "temp/ramfs/output/bp_ramfs_*.tar.gz"
      rootfs: "temp/rootfs/output/bp_rootfs_*.tar.gz"
  container:
    image: "amd-image-builder-alma9"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_AMD_Kernel_Builder`.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> dependencies**: A dict with all dependencies required by this builder to build this block. The keys of the dict are block IDs. The values of the dict are paths to the respective block packages. All paths are relative to the SoCks project directory. In almost all cases, the values from the example configuration can be used.
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of the Vivado toolset you are using. The following images are available for this block:
  - `amd-image-builder-alma8`
  - `amd-image-builder-alma9`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks requires external files in order to build this block. The following template packages are available:
- **universal**: Contains template files to build an image that uses an external root file system for Linux. The file system can be mounted e.g. from a second partition on the SD card or from the network via NFS.
- **qspi-flash**: Contains template files to build an image that can be deployed to a QSPI flash memory.
- **ram-filesystem**: Contains template files to build an image that uses a RAM filesystem.
- **split-boot**: Contains template files to build an image that uses Split Boot v2 for the boot process (Used for the Serenity ATCA blade in CMS at CERN).

### ZynqMP_AMD_Kernel_Builder

This builder is designed to build the [AMD fork](https://github.com/Xilinx/linux-xlnx) of the Linux Kernel.

#### Block Configuration

The default configuration `project-zynqmp-default` contains a complete configuration for this block. You can use it in your SoCks project configuration as follows:
```
import:
  - project-zynqmp-default.yml
``` 

Configuration example:
```
kernel:
  source: "build"
  builder: "ZynqMP_AMD_Kernel_Builder"
  project:
    build_srcs:
      source: "https://github.com/Xilinx/linux-xlnx.git"
      branch: "xilinx-v{{external_tools/xilinx/version}}"
    import_src: "https://serenity.web.cern.ch/.../kernel.tar.gz"
    add_build_info: false
    patches:
      - 0001-Add-default-config.patch
  container:
    image: "kernel-builder-alma9"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_AMD_Kernel_Builder`.
- **project -> build_srcs -> source**: The source to be used to build this block in URI format. Options are:
  - The URL of a git repository. In this case the string must start with `https://` or `ssh://`.
  - The path to a local folder, e.g. if the repo was checked out manually. In this case the string must start with `file://`.
- **project -> build_srcs -> branch [optional]**: Specifies the branch of the source repo to be used. Only permitted if *project -> build_srcs -> source* contains the URL of a git repo.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> add_build_info**: A binary parameter that specifies whether build-related information should be built into the Kernel. If it is set to `true`, SoCks creates a file with build related information encoded in a C-array in the source repo under `include/build_info.h`. This file can then be used to add this information to the `/proc` filesystem of the Kernel.
- **project -> patches**: A list of patch files that are automatically applied to the build sources (*project -> build_srcs*) by SoCks. SoCks will automatically add new patches here if you create them with the command `create-patches`. Patch files must be located in `src/kernel/patches`.
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of the Vivado toolset you are using. The following images are available for this block:
  - `kernel-builder-alma8`
  - `kernel-builder-alma9`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks does not require any external files in order to build this block. However, it is possible to create patches for the source repo.

### ZynqMP_AMD_PetaLinux_RAMFS_Builder

This builder is designed to build a Petalinux RAM file system with yocto. Furthermore, it allows to modify the base root file system by adding files built by other blocks like Kernel modules, device tree overlays and FPGA bitstreams. This builder is a slightly adapted version of the `ZynqMP_AMD_PetaLinux_RootFS_Builder`. Visit the section of `ZynqMP_AMD_PetaLinux_RootFS_Builder` for details on how to use this builder.

### ZynqMP_AMD_PetaLinux_RootFS_Builder

This builder is designed to build a Petalinux root file system with yocto. Furthermore, it allows to modify the base root file system by adding files built by other blocks like Kernel modules, device tree overlays and FPGA bitstreams.

#### Block Configuration

The default configuration `project-zynqmp-default` does not contain any configuration for this block. The entire configuration must be carried out in the project configuration file.

Configuration example:
```
rootfs:
  source: "build"
  builder: "ZynqMP_AMD_PetaLinux_RootFS_Builder"
  project:
    build_srcs:
      source: "https://github.com/Xilinx/yocto-manifests.git"
      branch: "rel-v{{external_tools/xilinx/version}}"
    import_src: "https://serenity.web.cern.ch/.../petalinux_rootfs.tar.gz"
    add_build_info: true
    dependencies:
      kernel: "temp/kernel/output/bp_kernel_*.tar.gz"
    patches:
      - project: meta-xilinx
        patch: 0001-Strip-everything-except-the-rootfs-from-core-image-m.patch
  container:
    image: "petalinux-rootfs-builder-alma8"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_AMD_Kernel_Builder`.
- **project -> build_srcs -> source**: The source to be used to build this block in URI format. Options are:
  - The URL of a git repository. In this case the string must start with `https://` or `ssh://`.
  - The path to a local folder, e.g. if the repo was checked out manually. In this case the string must start with `file://`.
- **project -> build_srcs -> branch [optional]**: Specifies the branch of the source repo to be used. Only permitted if *project -> build_srcs -> source* contains the URL of a git repo.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> add_build_info**: A binary parameter that specifies whether build-related information should be built into the root file system. If it is set to `true`, SoCks creates the file `/etc/fs_build_info` with build related information in the root file system.
- **project -> dependencies**: A dict with all dependencies required by this builder to build this block. The keys of the dict are block IDs. The values of the dict are paths to the respective block packages. All paths are relative to the SoCks project directory. In almost all cases, the values from the example configuration can be used.
- **project -> patches**: A list of dicts describing patch files that are automatically applied to the build sources (*project -> build_srcs*) by SoCks. In contrast to most other blocks dict are used to describe the patches. This is because yocto uses one git repo per layer. SoCks will automatically add new patches here if you create them with the command `create-patches`. Patch files must be located in `src/rootfs/patches`.
- **project -> patches -> [N] -> project**: The target git repo of this patch.
- **project -> patches -> [N] -> patch**: The path of the patch file.
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of the Vivado toolset you are using. The following images are available for this block:
  - `petalinux-rootfs-builder-alma8`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks requires external files in order to build this block. The following template packages are available:
- **universal_2022_2**: Contains a template file `local.conf.append`. This file can be used to extend the yocto configuration file `local.conf`. SoCks automatically appends `local.conf.append` to the end of `local.conf`. Furthermore, this template package contains a patch that modifies the Petalinux yocto configuration so that only the root file system is built and nothing else (No FSBL, U-Boot, Kernel, ...). This patch is tested with Petalinux 2022.2.

### ZynqMP_AMD_PMUFW_Builder

This builder is designed to build the Platform Management Unit (PMU) firmware for an AMD ZynqMP SoCs.

#### Block Configuration

The default configuration `project-zynqmp-default` contains a complete configuration for this block. You can use it in your SoCks project configuration as follows:
```
import:
  - project-zynqmp-default.yml
``` 

Configuration example:
```
pmu_fw:
  source: "build"
  builder: "ZynqMP_AMD_PMUFW_Builder"
  project:
    import_src: "https://serenity.web.cern.ch/.../pmu_fw.tar.gz"
    dependencies:
      vivado: "temp/vivado/output/bp_vivado_*.tar.gz"
    patches:
      - 0001-Add-gitignore.patch
  container:
    image: "amd-xilinx-tools-alma8"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_AMD_PMUFW_Builder`.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> dependencies**: A dict with all dependencies required by this builder to build this block. The keys of the dict are block IDs. The values of the dict are paths to the respective block packages. All paths are relative to the SoCks project directory. In almost all cases, the values from the example configuration can be used.
- **project -> patches**: A list of patch files that are automatically applied to the build sources (*project -> build_srcs*) by SoCks. SoCks will automatically add new patches here if you create them with the command `create-patches`. Patch files must be located in `src/fsbl/patches`.
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of the Vivado toolset you are using. The following images are available for this block:
  - `amd-xilinx-tools-alma8`
  - `amd-xilinx-tools-alma9`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks does not require any external files in order to build this block. However, it is possible to create patches for the source repo. The following template packages are available:
- **universal**: Contains a default gitignore file for the autogenerated repo.

### ZynqMP_AMD_UBoot_Builder

This builder is designed to build the [AMD fork](https://github.com/Xilinx/u-boot-xlnx) of das U-Boot.

#### Block Configuration

The default configuration `project-zynqmp-default` contains a complete configuration for this block. You can use it in your SoCks project configuration as follows:
```
import:
  - project-zynqmp-default.yml
``` 

Configuration example:
```
uboot:
  source: "build"
  builder: "ZynqMP_AMD_UBoot_Builder"
  project:
    build_srcs:
      source: "https://github.com/Xilinx/u-boot-xlnx.git"
      branch: "xilinx-v{{external_tools/xilinx/version}}"
    import_src: "https://serenity.web.cern.ch/.../uboot.tar.gz"
    add_build_info: false
    dependencies:
      atf: "temp/atf/output/bp_atf_*.tar.gz"
    patches:
      - 0001-Add-default-config.patch
  container:
    image: "kernel-builder-alma9"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_AMD_UBoot_Builder`.
- **project -> build_srcs -> source**: The source to be used to build this block in URI format. Options are:
  - The URL of a git repository. In this case the string must start with `https://` or `ssh://`.
  - The path to a local folder, e.g. if the repo was checked out manually. In this case the string must start with `file://`.
- **project -> build_srcs -> branch [optional]**: Specifies the branch of the source repo to be used. Only permitted if *project -> build_srcs -> source* contains the URL of a git repo.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> add_build_info**: A binary parameter that specifies whether build-related information should be built into das U-Boot. If it is set to `true`, SoCks creates a file with build related information encoded in a C-array in the source repo under `include/build_info.h`. This file can then be used e.g. to create a custom U-Boot command that shows this information.
- **project -> patches**: A list of patch files that are automatically applied to the build sources (*project -> build_srcs*) by SoCks. SoCks will automatically add new patches here if you create them with the command `create-patches`. Patch files must be located in `src/uboot/patches`.
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of the Vivado toolset you are using. The following images are available for this block:
  - `kernel-builder-alma8`
  - `kernel-builder-alma9`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks does not require any external files in order to build this block. However, it is possible to create patches for the source repo.

### ZynqMP_AMD_Vivado_Hog_Builder

This builder is designed to build a Vivado project with Hog.

#### Block Configuration

The default configuration `project-zynqmp-default` contains an incomplete base configuration for this block. You can use the default configuration in your SoCks project configuration as follows:
```
import:
  - project-zynqmp-default.yml
blocks:
  vivado:
    builder: "ZynqMP_AMD_Vivado_Hog_Builder"
    project:
      build_srcs:
        source: "ssh://git@gitlab.cern.ch:7999/p2-xware/zynq/serenity-s1-k26c-fw.git"
        branch: "test"
      name: "serenity-s1-kria"
``` 

Configuration example:
```
vivado:
  source: "build"
  builder: "ZynqMP_AMD_Vivado_Hog_Builder"
  project:
    build_srcs:
      source: "ssh://git@gitlab.cern.ch:7999/p2-xware/zynq/serenity-s1-k26c-fw.git"
      branch: "test"
    import_src: "https://serenity.web.cern.ch/.../vivado.tar.gz"
    name: "serenity-s1-kria"
  container:
    image: "amd-xilinx-tools-alma8"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_AMD_Vivado_Hog_Builder`.
- **project -> build_srcs -> source**: The source to be used to build this block in URI format. Options are:
  - The URL of a git repository. In this case the string must start with `https://` or `ssh://`.
  - The path to a local folder, e.g. if the repo was checked out manually. In this case the string must start with `file://`.
- **project -> build_srcs -> branch [optional]**: Specifies the branch of the source repo to be used. Only permitted if *project -> build_srcs -> source* contains the URL of a git repo.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> name**: Name of the Hog project
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of the Vivado toolset you are using. The following images are available for this block:
  - `amd-xilinx-tools-alma8`
  - `amd-xilinx-tools-alma9`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks does not require any external files in order to build this block.

### ZynqMP_AMD_Vivado_IPBB_Builder

This builder is designed to build a Vivado project with the IPbus Builder (IPBB) framework.

#### Block Configuration

The default configuration `project-zynqmp-default` contains an incomplete base configuration for this block. You can use the default configuration in your SoCks project configuration as follows:
```
import:
  - project-zynqmp-default.yml
blocks:
  vivado:
    builder: "ZynqMP_AMD_Vivado_IPBB_Builder"
    project:
      build_srcs:
        - source: "https://github.com/ipbus/ipbus-firmware.git"
          branch: "-r 60d7efed3ddba10e551790de7505bfea5bfc738b"
        - source: "ssh://git@gitlab.cern.ch:7999/p2-xware/firmware/serenity-service.git"
          branch: "-b v0.4.4"
        - source: "ssh://git@gitlab.cern.ch:7999/p2-xware/zynq/serenity-s1-k26c-fw"
          branch: "-b main"
      name: "s1-kria"
    container:
      image: "ipbb-builder-alma8"
``` 

Configuration example:
```
vivado:
  source: "build"
  builder: "ZynqMP_AMD_Vivado_IPBB_Builder"
  project:
    build_srcs:
      - source: "https://github.com/ipbus/ipbus-firmware.git"
        branch: "-r 60d7efed3ddba10e551790de7505bfea5bfc738b"
      - source: "ssh://git@gitlab.cern.ch:7999/p2-xware/firmware/serenity-service.git"
        branch: "-b v0.4.4"
      - source: "ssh://git@gitlab.cern.ch:7999/p2-xware/zynq/serenity-s1-k26c-fw"
        branch: "-b main"
    import_src: "https://serenity.web.cern.ch/.../vivado.tar.gz"
    name: "s1-kria"
  container:
    image: "ipbb-builder-alma8"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_AMD_Vivado_IPBB_Builder`.
- **project -> build_srcs [optional]**: A list of dicts describing git repos to be used by IPBB.
- **project -> build_srcs -> [N] -> source**: The source to be used to build this block in URI format. Options are:
  - The URL of a git repository. In this case the string must start with `https://` or `ssh://`.
  - The path to a local folder, e.g. if the repo was checked out manually. In this case the string must start with `file://`.
- **project -> build_srcs -> [N] -> branch [optional]**: Specifies the branch of the source repo to be used. Only permitted if *project -> build_srcs -> source* contains the URL of a git repo. The string has to start with '-b ' for branches and tags or with '-r ' for commit ids.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> name**: Name of the IPBB project
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of the Vivado toolset you are using. The following images are available for this block:
  - `ipbb-builder-alma8`
  - `ipbb-builder-alma9`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks does not require any external files in order to build this block.

### ZynqMP_AMD_Vivado_logicc_Builder

This builder is designed to build a Vivado project with the logicc framework.

#### Block Configuration

The default configuration `project-zynqmp-default` contains an incomplete base configuration for this block. You can use the default configuration in your SoCks project configuration as follows:
```
import:
  - project-zynqmp-default.yml
blocks:
  vivado:
    builder: "ZynqMP_AMD_Vivado_logicc_Builder"
    project:
      build_srcs:
        source: "ssh://git@gitlab.kit.edu/kit/ipe-sdr/ipe-sdr-dev/hardware/sdr_hardware.git"
        branch: "master"
      name: "qup:zcu216_rfdc_full"
    container:
      image: "logicc-builder-alma8"
``` 

Configuration example:
```
vivado:
  source: "build"
  builder: "ZynqMP_AMD_Vivado_logicc_Builder"
  project:
    build_srcs:
      source: "ssh://git@gitlab.kit.edu/kit/ipe-sdr/ipe-sdr-dev/hardware/sdr_hardware.git"
      branch: "master"
    import_src: "file:///home/marvin/Projects/SDR/SoCks/zcu216_demo_SoCks/vivado.tar.gz"
    name: "qup:zcu216_rfdc_full"
  container:
    image: "logicc-builder-alma8"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_AMD_Vivado_logicc_Builder`.
- **project -> build_srcs -> source**: The source to be used to build this block in URI format. Options are:
  - The URL of a git repository. In this case the string must start with `https://` or `ssh://`.
  - The path to a local folder, e.g. if the repo was checked out manually. In this case the string must start with `file://`.
- **project -> build_srcs -> branch [optional]**: Specifies the branch of the source repo to be used. Only permitted if *project -> build_srcs -> source* contains the URL of a git repo.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> name**: Name of the logicc project. The format for regular projects is `<project>`. For grouped projects the format is `<group>:<project>`.
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of the Vivado toolset you are using. The following images are available for this block:
  - `logicc-builder-alma8`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks does not require any external files in order to build this block.

### ZynqMP_BusyBox_RAMFS_Builder

This builder is designed to build a BusyBox RAM file system. Kernel modules are automatically added, and it is also possible to add external files automatically.

#### Block Configuration

The default configuration `project-zynqmp-default` does not contain any configuration for this block. The entire configuration must be carried out in the project configuration file.

Configuration example:
```
ramfs:
  source: "build"
  builder: "ZynqMP_BusyBox_RAMFS_Builder"
  project:
    build_srcs:
      source: "https://git.busybox.net/busybox/"
      branch: "1_36_1"
    import_src: "https://serenity.web.cern.ch/.../busybox_ramfs.tar.gz"
    source_repo_fs_layer:
      - src_name: "examples/udhcp/simple.script"
        dest_path: "/usr/share/udhcpc"
        dest_name: "default.script"
        dest_owner_group: "root:root"
        dest_permissions: "u=rwx,go=rx"
    add_build_info: false
    dependencies:
      kernel: "temp/kernel/output/bp_kernel_*.tar.gz"
    patches:
      - 0001-Add-default-config.patch
  container:
    image: "busybox-ramfs-builder-alma9"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_BusyBox_RAMFS_Builder`.
- **project -> build_srcs -> source**: The source to be used to build this block in URI format. Options are:
  - The URL of a git repository. In this case the string must start with `https://` or `ssh://`.
  - The path to a local folder, e.g. if the repo was checked out manually. In this case the string must start with `file://`.
- **project -> build_srcs -> branch [optional]**: Specifies the branch of the source repo to be used. Only permitted if *project -> build_srcs -> source* contains the URL of a git repo.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> source_repo_fs_layer [optional]**: A list of dicts describing files and folders from the sorce repo to be added to the RAM file system without any modifications. The file `simple.script` in the configuration example is required to enable dhcp support.
- **project -> source_repo_fs_layer -> [N] -> src_name**: The name of the file or folder in the source repo.
- **project -> source_repo_fs_layer -> [N] -> dest_path**: The target path in the RAM file system where this file or folder is to be placed.
- **project -> source_repo_fs_layer -> [N] -> dest_name [optional]**: This parameter allows to rename the file or folder in the target location. It can be omitted if the source name is to be used.
- **project -> source_repo_fs_layer -> [N] -> dest_owner_group [optional]**: This parameter allows to set owner and group of the file or directory in the target location.
- **project -> source_repo_fs_layer -> [N] -> dest_permissions [optional]**: This parameter allows to set the file permission in the target location.
- **project -> add_build_info**: A binary parameter that specifies whether build-related information should be built into the RAM file system. If it is set to `true`, SoCks creates the file `/etc/fs_build_info` with build related information in the RAM file system.
- **project -> dependencies**: A dict with all dependencies required by this builder to build this block. The keys of the dict are block IDs. The values of the dict are paths to the respective block packages. All paths are relative to the SoCks project directory. In almost all cases, the values from the example configuration can be used.
- **project -> patches**: A list of patch files that are automatically applied to the build sources (*project -> build_srcs*) by SoCks. SoCks will automatically add new patches here if you create them with the command `create-patches`. Patch files must be located in `src/ramfs/patches`.
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of the Vivado toolset you are using. The following images are available for this block:
  - `busybox-ramfs-builder-alma8`
  - `busybox-ramfs-builder-alma9`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks requires external files in order to build this block. The following template packages are available:
- **mounts-nfs-rootfs**: Contains template files for building a busybox RAM file system with network support that is able to mount an NFS root file system. The optional folder `predefined_fs_layers` allows to add static layers that are added to the base RAM file system. Every layer requires a shell script that is used to add the layer. The file `predefined_fs_layers/common/init` is the init script of the RAM file system. It contains all steps required to initialize the RAM file system, mount the NFS root file system, and do the handover from busybox RAMFS to NFS RootFS. The folder `predefined_fs_layers/common/etc/network` contains files and folders required to establish a connection to the network.
- **mounts-overlay-rootfs**: Contains template files for building a busybox RAM file system with network support that is able to mount an overlay root file system consisting of an NFS file system used as the read-only base layer and a read/write layer on a local media such as SSD or an SD card. This template package contains equivalent files to `mounts-nfs-rootfs`, but the init script is modfied to enable the overlay root file system.

### ZynqMP_Debian_RootFS_Builder

This builder is designed to build a Debian root file system. Furthermore, it allows to modify the base root file system by adding files built by other blocks like Kernel modules, device tree overlays and FPGA bitstreams. It is also possible to add external files to the root file system and to modify it in various ways with a custom shell script.

#### Block Configuration

The default configuration `project-zynqmp-default` does not contain any configuration for this block. The entire configuration must be carried out in the project configuration file.

Configuration example:
```
rootfs:
  source: "build"
  builder: "ZynqMP_Debian_RootFS_Builder"
  project:
    release: "bookworm"
    mirror: "http://ftp.de.debian.org/debian/"
    extra_debs: ["sudo", "python3", "openssh-server", "nano", "vim"]
    build_time_fs_layer:
      - src_block: "vivado"
        src_name: "*.bit"
        dest_path: "/lib/firmware"
        dest_name: "serenity_s1_k26_pl.bit"
        dest_owner_group: "root:root"
        dest_permissions: "u=rw,go=r"
      - src_block: "devicetree"
        src_name: "*.dtbo"
        dest_path: "/etc/dt-overlays"
        dest_owner_group: "root:root"
        dest_permissions: "u=rwX,go=rX"
      - src_block: "vivado"
        src_name: "addrtab"
        dest_path: "/etc/serenity"
        dest_name: "zynq-addrtab"
    users:
      - name: "root"
        pw_hash: "$6$vZIHKtcF/ibXBtIg$8hD7jbElXZVHNBhUIL4G97lqgsZ.7hq1YtjwdZpG.YRwqFy9kWwACLgf4hEFbXQYr81X08B2EJIDSKO3ZeBF4/" # debian
      - name: "kria"
        pw_hash: "$6$G5Sswo/P0ILiqfS1$zqLYE2HP22Eg2WeTAQNJCrItEbs1utYN6TLF6nKbaoRHuyEUd8peeWPQ59Jx4jVpAto6brgV9FxA3veBYUg8.1" # regular.user
        groups: ["sudo", "dialout"]
    import_src: "https://serenity.web.cern.ch/.../debian_rootfs.tar.gz"
    add_build_info: false
    dependencies:
      kernel: "temp/kernel/output/bp_kernel_*.tar.gz"
      devicetree: "temp/devicetree/output/bp_devicetree*.tar.gz"
      vivado: "temp/vivado/output/bp_vivado*.tar.gz"
  container:
    image: "debian-rootfs-builder-debian12"
    tag: "socks"
```

Key:
- **source**: The source of the block. Options are:
  - **build**: Build the block locally
  - **import**: Import an already built block package
- **builder**: The builder to be used to build this block. For this builder always `ZynqMP_Debian_RootFS_Builder`.
- **project -> release**: The release version of Debian to be built. Options are:
  - bookworm
- **project -> mirror**: Debian mirror to be used. Choose a local mirror to speed up the build process.
- **project -> extra_debs [optional]**: A list of additional deb packages to be installed in the root file system.
- **project -> build_time_fs_layer [optional]**: A list of dicts describing files and folders generated by other blocks and are to be added to the root file system.
- **project -> build_time_fs_layer -> [N] -> src_block**: The ID of the block that generates this file or folder.
- **project -> build_time_fs_layer -> [N] -> src_name**: The name of the file or folder in the block package of the source block.
- **project -> build_time_fs_layer -> [N] -> dest_path**: The target path in the root file system where this file or folder is to be placed.
- **project -> build_time_fs_layer -> [N] -> dest_name [optional]**: This parameter allows to rename the file or folder in the target location. It can be omitted if the source name is to be used.
- **project -> build_time_fs_layer -> [N] -> dest_owner_group [optional]**: This parameter allows to set owner and group of the file or directory in the target location.
- **project -> build_time_fs_layer -> [N] -> dest_permissions [optional]**: This parameter allows to set the file permission in the target location.
- **project -> users**: A list of dicts describing users to be added to the root file system.
- **project -> users -> [N] -> name**: The name of the user.
- **project -> users -> [N] -> pw_hash**: The password of the user in hashed form. The hashed password can be generated with the following command: `openssl passwd -6`.
- **project -> users -> [N] -> groups**: A list of groups the users is to be added to.
- **project -> import_src [optional]**: The pre-built block package to be imported for this block. This information is only used if the value of *source* is *import*. Options are:
  - The URL of a file online. In this case the string must start with `https://`.
  - The path of a local file. In this case the string must start with `file://`.
- **project -> add_build_info**: A binary parameter that specifies whether build-related information should be built into the root file system. If it is set to `true`, SoCks creates the file `/etc/fs_build_info` with build related information in the root file system.
- **project -> dependencies**: A dict with all dependencies required by this builder to build this block. The keys of the dict are block IDs. The values of the dict are paths to the respective block packages. All paths are relative to the SoCks project directory. In almost all cases, the values from the example configuration can be used.
- **container -> image**: The container image to be used for building. The selection should be compatible with the version of Debian to be built. The following images are available for this block:
  - `debian-rootfs-builder-debian12`
- **container -> tag**: The tag of the container image in the database of the containerization tool. This should always be set to `socks`.

#### External Source Files

SoCks requires external files in order to build this block. The following template packages are available:
- **universal**: Contains universal template files to build a Debian root file system. The optional file `mod_base_install.sh` allows to modify the base root file system after all packages have been added, but before any other modifications have been made to it. The optional folder `predefined_fs_layers` allows to add static layers that are added to the base root file system. Every layer requires a shell script that is used to add the layer.

## Background

SoCks is designed as a lightweigtht framework to build production-ready SoC images. It aims at beeing as transparent as possible by hiding nothing and using internal "smartness" only where it is really needed. Furthermore, SoCks provides understandable and comprehensive warnings and error messages that support you in finding the root cause of a problem as quickly as possible. To achive this while not flooding you with information, SoCks uses the simple approach of divide and conquer. The SoC image is partitioned into a small number of so called blocks that represent a mostly self-contained unit each. Examples are the Vivado block, boot loader blocks or the Linux Kernel block. SoCks builds one block after the other and uses so called block packages as a uniform interface to pass files from one block to another, when needed.

This approach gives full controll to the developer, which enables a reliable and fast build process for the SoC image, a quick process to develop updates, and full compatibility and freedome when it comes to gitlab CI/CD integration. All of this is especially handy if you have to provide support for a system that is deployed in the field and fulfills a mission critcal task.

The main downside of full controll is that setting up a new SoCks project from scratch requires detailed knowledge of the platform you are developing for and the software stack that you want to deploy. So, if your aim is to do rapid prototyping or to explore a new SoC architecture, SoCks is probably not the right tool for you. But if you are an experienced SoC developer that wants to know exactly what is going, SoCks is exactly what you are looking for!

### Basics

SoCks uses a modular approach to build SoC images. To achieve this, the image is partitioned into sections, called blocks. The following image shows the partitioning of an AMD ZynqMP image:

![Complete ZynqMP Image](../doc/diagrams/Complete_ZynqMP_image.drawio.png)

The blocks `RAM File System` and `RAM File System` are slightly grayed out, because they are optional. An image can utilize only a RAMFS, only a RootFS or both. But at least one of the two components is always required.

Each block represents a separate sub-project that can be regarded as largely independent. All blocks have their own source files, their own build process where they utilize dedicated build tools, and they produce their own output files. But of cause there are build time dependencies between the blocks. For example, some blocks use the output files of other blocks as sources of information. To enable the transfer of such information, all blocks contain interfaces to import and export so called block packages.

To unlock the full potential of the modular approach of SoCks, it must be possible to exchange how each block is build. For this purpose, SoCks uses so calles builders. A builder is implemented as a python class and defines how a block is build, which tools are used in the process, which sources are utilized, and which output products are generated. At build time, exactly one builder must be assigned to each block. The following image shows the selection of a builder for the RootFS block:

![Complete ZynqMP Image](../doc/diagrams/Block_plus_builder.drawio.png)

The AlmaLinux builder that is selected in the image uses qemu and dnf to build the file system for the target platform. Furthermore, it expects a certain set of configuration files that specify for instance which repos should be used, which additional packages should be installed on top of the base installation, which additional files should be add, which systemd services should be enabled, etc.. If one wants to use a Yocto or PetaLinux file system instead, there is the yocto builder that can be used instead. This builder requires a entirely different set of repos, build tools and configuration files, but the output of both builders will the exchangable. Both of them generate an archive that contains the compressed root file system, so they are both valid root file system builders.

The pictograms of the builds show which version of the block they build. The AlmaLinux builder uses official AlmaLinux sources to build the root file system, while the yocto builder uses the AMD version of yocto sources to build a PetaLinux root file system that is specifically tailored for AMD SoCs.

The following image shows a full ZynqMP image with builders assigned to all blocks.

![Complete ZynqMP Image](../doc/diagrams/Complete_ZynqMP_image_with_builders.drawio.png)

The configuration of a SoCks project is done in a single file: `project.yml`. This file contains global settings that apply to all blocks, like the version of the Vivado toolset or the containerization tool to be use, but it also contains a section for every block that is needed for the SoC image it describes. The section of a block contains for instance which builder is to be used to build this block.

### Builders

Builders are a core component of the SoCks framework. They bundle the mechanisms needed to build a specific version of a block in a python class and therefore allow to automate the process. All of them follow the same overarching pattern, which is presented below:

![Complete ZynqMP Image](../doc/diagrams/SoCks_block_build.drawio.png )

The builders of the blocks however have only access to the global information and to the information that is dedicated to the block they are building. 

Builders can collect source information from multiple places. Every builder has access to a subset of the information in the file `project.yml`, that configures the SoCks project. The access is limited to the global information in this file and to the information that is dedicated to the block this builder is building. The primary source of input is in most cases a git repository. This git repository can be automaticaly downoaded by SoCks or the user can provide a local folder that contains the equivalent files. Furthermore, most blocks require additional files with information. This can be a dnf config file that is used while building the files system, a template file that is used by SoCks to build the boot image or patches that are applied to the downloaded repo. Such patches allow to save modifications to the content of a git repository if one is not allowed to push to it. Finally, most builders use block backages of other blocks as input. One example is the block packages of the Vivado block, which contains amongst other things the XSA file. The blocks devicetree, FSBL, and PMU Firmware need the Vivado block package as input to be able to extract the ZynqMP PS configuration from the XSA file. The builder checks the content of the block package during the import process and raises an error if it does not contain all expected files.

In addition, a builders also needs a set of tools to be able to build the source files into output files. SoCks uses containers to provide the block with these tools in a suitable build environment. The framework itself contains a set of suitable container files and builds the required container images at build-time automatically. It is also possible to disable the container feature in SoCks, which is for instance required if one uses SoCks already in a suitable build container in a CI/CD pipeline. In this case, SoCks uses the tools in this environment.

If all build stages are completed, the final step that is executed by the builder is to package all required output files of the build process into a block package.

But it is not always required or desired that a builder builds the output files for its block package. Builders can also import a pre-build block package and provide it as their own output. The source for this pre-built block package can either be provided as a URL or as a path to a local file. Importing a pre-built block package can be usefull in many different cases. It can save time and space during development if one downloads pre-built block packages from gitlab CI/CD pipelines, especially if one works on a different blocks that needs these block packages only as an input. For instance the ATF, the SSBL (U-Boot) and the Kernel are often not touched when one developes a new feature. Using a pre-built block package is also useful if one does not have the required license or tools installed to build for instance a Vivado project.
