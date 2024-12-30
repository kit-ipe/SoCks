import sys
import pathlib
import shutil
import inspect
import zipfile

import socks.pretty_print as pretty_print
from builders.amd_builder import AMD_Builder
from builders.builder import Builder
from builders.versal_amd_image_model import Versal_AMD_Image_Model


class Versal_AMD_Image_Builder(AMD_Builder):
    """
    AMD Image builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        project_cfg_files: list,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "image",
        block_description: str = "Build the boot image for Versal devices",
        model_class: type[object] = Versal_AMD_Image_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            project_cfg_files=project_cfg_files,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        # Source images to be used in this block
        self._atf_img_path = self._dependencies_dir / "atf/bl31.elf"
        self._dt_img_path = self._dependencies_dir / "devicetree/system.dtb"
        self._plm_img_path = self._dependencies_dir / "plm/plm.elf"
        self._psmfw_img_path = self._dependencies_dir / "psm_fw/psmfw.elf"
        self._kernel_img_path = self._dependencies_dir / "kernel/Image"
        self._uboot_img_path = self._dependencies_dir / "uboot/u-boot.elf"
        self._vivado_pdi_file_path = None  # Must be initialized outside the constructor, as the file needs to be extracted and the name of the file it not fixed.

        # Project directories
        self._config_dir = self._block_src_dir / "config"
        self._xsa_extracted_dir = self._xsa_dir / "extracted"

        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        self._block_deps = {
            "atf": ["bl31.elf"],
            "devicetree": ["system.dtb"],
            "kernel": ["Image.gz"],
            "plm": ["plm.elf"],
            "psm_fw": ["psmfw.elf"],
            "ramfs": [".*.cpio.gz"],
            "rootfs": [".*.tar.xz"],
            "uboot": ["u-boot.elf"],
            "vivado": [".*.xsa"],
        }

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {"prepare": [], "build": [], "clean": [], "start-container": []}
        self.block_cmds["clean"].extend(
            [
                self.container_executor.build_container_image,
                self.clean_download,
                self.clean_work,
                self.clean_dependencies,
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self.block_cfg.source == "build":
            self.block_cmds["prepare"].extend(
                [self.container_executor.build_container_image, self.import_dependencies, self.import_xsa]
            )
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend([self.bootscr_img, self.boot_img, self.export_block_package])
            self.block_cmds["start-container"].extend(
                [self.container_executor.build_container_image, self.start_container]
            )
        elif self.block_cfg.source == "import":
            self.block_cmds["build"].extend([self.import_prebuilt])

    def validate_srcs(self):
        """
        Check whether all sources required to build this block are present.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        super().validate_srcs()
        self.import_src_tpl()

    def start_container(self):
        """
        Starts an interactive container with which the block can be built.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        self.check_amd_tools(required_tools=["vitis"])

        potential_mounts = [
            (pathlib.Path(self._amd_tools_path), "ro"),
            (self._config_dir, "Z"),
            (self._dependencies_dir, "Z"),
            (self._xsa_dir, "Z"),
            (self._work_dir, "Z"),
            (self._output_dir, "Z"),
        ]

        self.container_executor.start_container(potential_mounts=potential_mounts)

    def bootscr_img(self):
        """
        Creates boot script image boot.scr for U-Boot

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the boot script image needs to be built
        if not Versal_AMD_Image_Builder._check_rebuild_required(
            src_search_list=[self._config_dir / "boot.cmd"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to rebuild boot.scr. No altered source files detected...")
            return

        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Remove old build artifacts
        (self._output_dir / "boot.scr").unlink(missing_ok=True)

        pretty_print.print_build("Building boot.scr...")

        bootscr_img_build_commands = [
            f"mkimage -c none -A arm -T script -d {self._config_dir}/boot.cmd {self._output_dir}/boot.scr"
        ]

        self.container_executor.exec_sh_commands(
            commands=bootscr_img_build_commands, dirs_to_mount=[(self._config_dir, "Z"), (self._output_dir, "Z")]
        )

        # Log success of this function
        self._build_log.log_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

    def boot_img(self):
        """
        Creates the primary boot image BOOT.BIN

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        xsa_files = list(self._xsa_dir.glob("*.xsa"))

        # Check if there is more than one XSA file in the xsa directory
        if len(xsa_files) != 1:
            pretty_print.print_error(f"Not exactly one XSA archive in {self._xsa_dir}")
            sys.exit(1)

        if not self._xsa_extracted_dir.is_dir():
            self._xsa_extracted_dir.mkdir(parents=True)

            # Extract all contents of the XSA file
            with zipfile.ZipFile(xsa_files[0], "r") as archive:
                archive.extractall(path=str(self._xsa_extracted_dir))

        # Get *.pdi file from vivado block package
        pdi_files = list(self._xsa_extracted_dir.glob("*.pdi"))

        if len(pdi_files) != 1:
            pretty_print.print_error(f"Not exactly one *.pdi file in {self._xsa_extracted_dir}")
            sys.exit(1)

        self._vivado_pdi_file_path = pdi_files[0]

        # Check whether the boot script image needs to be built
        if not Versal_AMD_Image_Builder._check_rebuild_required(
            src_search_list=self._project_cfg_files
            + [
                self._config_dir / "bootgen.bif.tpl",
                self._plm_img_path,
                self._psmfw_img_path,
                self._vivado_pdi_file_path,
                self._atf_img_path,
                self._dt_img_path,
                self._uboot_img_path,
                self._output_dir / "image.ub",
                self._output_dir / "boot.scr",
            ],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to rebuild BOOT.BIN. No altered source files detected...")
            return

        self.check_amd_tools(required_tools=["vitis"])

        self._work_dir.mkdir(parents=True, exist_ok=True)

        # Remove old build artifacts
        (self._output_dir / "BOOT.BIN").unlink(missing_ok=True)

        pretty_print.print_build("Building BOOT.BIN...")

        boot_img_build_commands = [
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"source {self._amd_vitis_path}/settings64.sh",
            f"cp {self._config_dir}/bootgen.bif.tpl {self._work_dir}/bootgen.bif",
            f'sed -i "s:<PLM_PATH>:{self._plm_img_path}:g;" {self._work_dir}/bootgen.bif',
            f'sed -i "s:<PSMFW_PATH>:{self._psmfw_img_path}:g;" {self._work_dir}/bootgen.bif',
            f'sed -i "s:<PDI_PATH>:{self._vivado_pdi_file_path}:g;" {self._work_dir}/bootgen.bif',
            f'sed -i "s:<ATF_PATH>:{self._atf_img_path}:g;" {self._work_dir}/bootgen.bif',
            f'sed -i "s:<DTB_PATH>:{self._dt_img_path}:g;" {self._work_dir}/bootgen.bif',
            f'sed -i "s:<UBOOT_PATH>:{self._uboot_img_path}:g;" {self._work_dir}/bootgen.bif',
            f'sed -i "s:<LINUX_PATH>:{self._output_dir / "image.ub"}:g;" {self._work_dir}/bootgen.bif',
            f'sed -i "s:<BSCR_PATH>:{self._output_dir / "boot.scr"}:g;" {self._work_dir}/bootgen.bif',
            f"bootgen -arch versal -image {self._work_dir}/bootgen.bif -o {self._output_dir}/BOOT.BIN",
        ]

        self.container_executor.exec_sh_commands(
            commands=boot_img_build_commands,
            dirs_to_mount=[
                (pathlib.Path(self._amd_tools_path), "ro"),
                (self._config_dir, "Z"),
                (self._dependencies_dir, "Z"),
                (self._xsa_dir, "Z"),
                (self._work_dir, "Z"),
                (self._output_dir, "Z"),
            ],
        )

        # Log success of this function
        self._build_log.log_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
