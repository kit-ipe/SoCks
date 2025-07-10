import sys
import pathlib
import shutil
import inspect
import zipfile

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.amd_builder import AMD_Builder
from abstract_builders.builder import Builder
from amd_versal_support.versal_amd_image_model import Versal_AMD_Image_Model


class Versal_AMD_Image_Builder(AMD_Builder):
    """
    AMD Image builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "image",
        block_description: str = "Build the boot image for Versal devices",
        model_class: type[object] = Versal_AMD_Image_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
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
        self._ssbl_img_path = self._dependencies_dir / "ssbl/u-boot.elf"
        self._vivado_pdi_file_path = None  # Must be initialized outside the constructor, as the file needs to be extracted and the name of the file it not fixed.

        # Project directories
        self._resources_dir = self._block_src_dir / "resources"
        self._xsa_extracted_dir = self._xsa_dir / "extracted"

    @property
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = {
            "atf": ["bl31.elf"],
            "devicetree": ["system.dtb"],
            "kernel": ["Image.gz"],
            "plm": ["plm.elf"],
            "psm_fw": ["psmfw.elf"],
            "ramfs": [".*.cpio.gz"],
            "rootfs": [".*.tar.xz"],
            "ssbl": ["u-boot.elf"],
            "vivado": [".*.xsa"],
        }
        return block_deps

    @property
    def block_cmds(self):
        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        block_cmds = {"prepare": [], "build": [], "clean": [], "start-container": []}
        block_cmds["clean"].extend(
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
            block_cmds["prepare"].extend(
                [
                    self._build_validator.del_project_cfg,
                    self.container_executor.build_container_image,
                    self.import_dependencies,
                    self.import_xsa,
                    self._build_validator.save_project_cfg_prepare,
                ]
            )
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [
                    self.bootscr_img,
                    self.boot_img,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
            block_cmds["start-container"].extend([self.container_executor.build_container_image, self.start_container])
        elif self.block_cfg.source == "import":
            block_cmds["build"].extend([self.container_executor.build_container_image, self.import_prebuilt])
        return block_cmds

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
        self.import_req_src_tpl()

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
            (self._resources_dir, "Z"),
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
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._resources_dir / "boot.cmd"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to rebuild boot.scr. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self._output_dir.mkdir(parents=True, exist_ok=True)

            # Remove old build artifacts
            (self._output_dir / "boot.scr").unlink(missing_ok=True)

            pretty_print.print_build("Building boot.scr...")

            bootscr_img_build_commands = [
                f"mkimage -c none -A arm -T script -d {self._resources_dir}/boot.cmd {self._output_dir}/boot.scr"
            ]

            self.container_executor.exec_sh_commands(
                commands=bootscr_img_build_commands,
                dirs_to_mount=[(self._resources_dir, "Z"), (self._output_dir, "Z")],
                print_commands=True,
            )

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
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[
                self._resources_dir / "bootgen.bif.tpl",
                self._plm_img_path,
                self._psmfw_img_path,
                self._vivado_pdi_file_path,
                self._atf_img_path,
                self._dt_img_path,
                self._ssbl_img_path,
                self._output_dir / "image.ub",
                self._output_dir / "boot.scr",
            ],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._build_validator.check_rebuild_bc_config(keys=[["external_tools", "xilinx"]]):
            pretty_print.print_build("No need to rebuild BOOT.BIN. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self.check_amd_tools(required_tools=["vitis"])

            self._work_dir.mkdir(parents=True, exist_ok=True)

            # Remove old build artifacts
            (self._output_dir / "BOOT.BIN").unlink(missing_ok=True)

            pretty_print.print_build("Building BOOT.BIN...")

            boot_img_build_commands = [
                f"export XILINXD_LICENSE_FILE={self._amd_license}",
                f"source {self._amd_vitis_path}/settings64.sh",
                f"cp {self._resources_dir}/bootgen.bif.tpl {self._work_dir}/bootgen.bif",
                f'sed -i "s:<PLM_PATH>:{self._plm_img_path}:g;" {self._work_dir}/bootgen.bif',
                f'sed -i "s:<PSMFW_PATH>:{self._psmfw_img_path}:g;" {self._work_dir}/bootgen.bif',
                f'sed -i "s:<PDI_PATH>:{self._vivado_pdi_file_path}:g;" {self._work_dir}/bootgen.bif',
                f'sed -i "s:<ATF_PATH>:{self._atf_img_path}:g;" {self._work_dir}/bootgen.bif',
                f'sed -i "s:<DTB_PATH>:{self._dt_img_path}:g;" {self._work_dir}/bootgen.bif',
                f'sed -i "s:<SSBL_PATH>:{self._ssbl_img_path}:g;" {self._work_dir}/bootgen.bif',
                f'sed -i "s:<LINUX_PATH>:{self._output_dir / "image.ub"}:g;" {self._work_dir}/bootgen.bif',
                f'sed -i "s:<BSCR_PATH>:{self._output_dir / "boot.scr"}:g;" {self._work_dir}/bootgen.bif',
                f"bootgen -arch versal -image {self._work_dir}/bootgen.bif -o {self._output_dir}/BOOT.BIN",
            ]

            self.container_executor.exec_sh_commands(
                commands=boot_img_build_commands,
                dirs_to_mount=[
                    (pathlib.Path(self._amd_tools_path), "ro"),
                    (self._resources_dir, "Z"),
                    (self._dependencies_dir, "Z"),
                    (self._xsa_dir, "Z"),
                    (self._work_dir, "Z"),
                    (self._output_dir, "Z"),
                ],
                print_commands=True,
            )
