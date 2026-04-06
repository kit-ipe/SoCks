import sys
import pathlib
import hashlib
import os

import socks.pretty_print as pretty_print
from amd_zynqmp_support.zynqmp_amd_devicetree_builder import ZynqMP_AMD_Devicetree_Builder
from amd_zynq_support.zynq_amd_devicetree_model import Zynq_AMD_Devicetree_Model


class Zynq_AMD_Devicetree_Builder(ZynqMP_AMD_Devicetree_Builder):
    """
    AMD devicetree builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "devicetree",
        block_description: str = "Build the Devicetree for Zynq devices",
        model_class: type[object] = Zynq_AMD_Devicetree_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        self.pre_action_warnings.append(
            f"Builder {self.__class__.__name__} is experimental and should not be used for production."
        )

    def prepare_dt_sources(self):
        """
        Prepares the devicetree sources.

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
            pretty_print.print_error(f"Not exactly one XSA archive in {self._xsa_dir}/")
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(xsa_files[0].read_bytes()).hexdigest()
        # Read md5 of previously used XSA archive, if any
        md5_existsing_file = 0
        if self._source_xsa_md5_file.is_file():
            with self._source_xsa_md5_file.open("r") as f:
                md5_existsing_file = f.read()

        # Check if the project needs to be created
        if (md5_existsing_file == md5_new_file) and not self._build_validator.check_rebuild_bc_config(
            keys=[["external_tools", "xilinx"], ["blocks", self.block_id, "project", "board"]], accept_prep=True
        ):
            pretty_print.print_info("No new XSA archive recognized. Devicetree sources are not recreated.")
            return

        self.check_amd_tools(required_tools=["vitis"])

        self.clean_work()
        self._base_work_dir.mkdir(parents=True)

        pretty_print.print_build("Preparing devicetree sources...")

        prep_dt_srcs_commands = [
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"source {self._amd_vitis_path}/settings64.sh",
            f"SOURCE_XSA_PATH=$(ls {self._xsa_dir}/*.xsa)",
            'printf "hsi open_hw_design ${SOURCE_XSA_PATH}'
            f"    \r\nhsi set_repo_path {self._source_repo_dir} "
            "    \r\nhsi create_sw_design device-tree -os device_tree -proc ps7_cortexa9_0 ",
        ]

        # If an evaluation card is used, include card specific devicetree section
        if self.block_cfg.project.board != "custom":
            # Check if board file exists in device tree repo
            board_name = self.block_cfg.project.board
            xilinx_version = self.project_cfg.external_tools.xilinx.version
            dt_file = self._source_repo_dir / f"device_tree/data/kernel_dtsi/{xilinx_version}/BOARD/{board_name}.dtsi"
            if not dt_file.is_file():
                pretty_print.print_error(
                    f"Pre-defined devicetree section for board '{board_name}' specified in "
                    f"'blocks -> {self.block_id} -> project -> board' not found. "
                    f"It is expected that the file is at this location: {dt_file}."
                )
                sys.exit(1)
            prep_dt_srcs_commands[-1] = (
                prep_dt_srcs_commands[-1]
                + f'    \r\nhsi set_property CONFIG.periph_type_overrides \\"{{BOARD {self.block_cfg.project.board}}}\\" [hsi get_os]'
            )

        prep_dt_srcs_commands[-1] = (
            prep_dt_srcs_commands[-1]
            + f"    \r\nhsi generate_target -dir {self._base_work_dir} "
            + f'    \r\nhsi close_hw_design [hsi current_hw_design]" > {self._base_work_dir}/generate_dts_prj.tcl'
        )
        prep_dt_srcs_commands.append(f"xsct -nodisp {self._base_work_dir}/generate_dts_prj.tcl")

        self.container_executor.exec_sh_commands(
            commands=prep_dt_srcs_commands,
            dirs_to_mount=[
                (pathlib.Path(self._amd_tools_path), "ro"),
                (self._xsa_dir, "Z"),
                (self._repo_dir, "Z"),
                (self._base_work_dir, "Z"),
            ],
            print_commands=True,
        )

        # Save checksum in file
        with self._source_xsa_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")
