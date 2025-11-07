import sys
import pathlib
import shutil
import urllib
import hashlib
import inspect
import os
import csv

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from socks.yaml_editor import YAML_Editor
from abstract_builders.amd_builder import AMD_Builder
from amd_zynqmp_support.zynqmp_amd_devicetree_model import ZynqMP_AMD_Devicetree_Model


class ZynqMP_AMD_Devicetree_Builder(AMD_Builder):
    """
    AMD devicetree builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "devicetree",
        block_description: str = "Build the Devicetree for ZynqMP devices",
        model_class: type[object] = ZynqMP_AMD_Devicetree_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        # Project directories
        self._dt_incl_dir = self._block_src_dir / "dt_includes"
        self._dt_overlay_dir = self._block_src_dir / "dt_overlays"
        self._base_work_dir = self._work_dir / "base"
        self._overlay_work_dir = self._work_dir / "overlays"

    @property
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = {"vivado": [".*.xsa"]}
        return block_deps

    @property
    def block_cmds(self):
        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        block_cmds = {"prepare": [], "build": [], "clean": [], "create-patches": [], "start-container": []}
        block_cmds["clean"].extend(
            [
                self.container_executor.build_container_image,
                self.clean_download,
                self.clean_work,
                self.clean_repo,
                self.clean_source_xsa,
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
                    self.init_repo,
                    self.apply_patches,
                    self.import_xsa,
                    self.prepare_dt_sources,
                    self._build_validator.save_project_cfg_prepare,
                ]
            )
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [
                    self.build_base_devicetree,
                    self.build_dt_overlays,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
            block_cmds["create-patches"].extend([self.create_patches])
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
            "    \r\nhsi create_sw_design device-tree -os device_tree -proc psu_cortexa53_0 ",
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

    def build_base_devicetree(self):
        """
        Builds the base devicetree.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the devicetree needs to be built
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._dt_incl_dir, self._base_work_dir, self._dependencies_dir / "block_pkg_vivado.md5"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "dt_includes"]]
        ):
            pretty_print.print_build("No need to rebuild the devicetree. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            # Remove old build artifacts
            (self._output_dir / "system.dtb").unlink(missing_ok=True)
            (self._output_dir / "system.dts").unlink(missing_ok=True)

            pretty_print.print_build("Building the base devicetree...")

            # Add devicetree include files from vivado block
            dt_include_files = []
            for dt_incl in [path.name for path in (self._dependencies_dir / "vivado").glob("*.dtsi")]:
                # Devicetree includes are copied before every build to make sure they are up to date
                shutil.copy(self._dependencies_dir / "vivado" / dt_incl, self._base_work_dir / dt_incl)
                dt_include_files.append(dt_incl)

            # Add user defined devicetree include files
            if self.block_cfg.project.dt_includes != None:
                for dt_incl in self.block_cfg.project.dt_includes:
                    if not (self._dt_incl_dir / dt_incl).is_file():
                        pretty_print.print_error(
                            f"File '{dt_incl}' specified in 'blocks -> {self.block_id} -> project -> dt_includes' does not exist in {self._dt_incl_dir}/"
                        )
                        sys.exit(1)

                    # Devicetree includes are copied before every build to make sure they are up to date
                    shutil.copy(self._dt_incl_dir / dt_incl, self._base_work_dir / dt_incl)
                    dt_include_files.append(dt_incl)

            # Include files in top level
            for dt_incl in dt_include_files:
                # Check if this file is already included, and if not, include it
                with (self._base_work_dir / "system-top.dts").open("r+") as dts_top_file:
                    contents = dts_top_file.read()
                    incl_line = f'#include "{dt_incl}"\n'
                    if incl_line not in contents:
                        # If the line was not found, the file pointer is now at the end
                        # Write the include line
                        dts_top_file.write(incl_line)

            # The *.dts file created by gcc is for humans difficult to read. Therefore, in the last step, it is replaced by one created with the devicetree compiler.
            dt_build_commands = [
                f"cd {self._base_work_dir}",
                "gcc -E -nostdinc -undef -D__DTS__ -x assembler-with-cpp -I include -o system.dts system-top.dts",
                "dtc -I dts -O dtb -A -@ -o system.dtb system.dts",
                "dtc -I dtb -O dts -o system.dts system.dtb",
            ]

            self.container_executor.exec_sh_commands(
                commands=dt_build_commands,
                dirs_to_mount=[(self._base_work_dir, "Z")],
                print_commands=True,
                logfile=self._block_temp_dir / "build_devicetree.log",
                output_scrolling=True,
            )

            self._output_dir.mkdir(parents=True, exist_ok=True)

            # Create symlink to the output files
            (self._output_dir / "system.dtb").symlink_to(self._base_work_dir / "system.dtb")
            (self._output_dir / "system.dts").symlink_to(self._base_work_dir / "system.dts")

    def build_dt_overlays(self):
        """
        Builds devicetree overlays.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the devicetree overlays need to be built
        if (
            not self._dt_overlay_dir.is_dir()
            or not any(self._dt_overlay_dir.iterdir())
            or not Build_Validator.check_rebuild_bc_timestamp(
                src_search_list=[self._dt_overlay_dir, self._base_work_dir],
                out_timestamp=self._build_log.get_logged_timestamp(
                    identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
                ),
            )
        ):
            pretty_print.print_build("No need to rebuild devicetree overlays. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            # Clean overlay work directory
            try:
                shutil.rmtree(self._overlay_work_dir)
            except FileNotFoundError:
                pass  # Ignore if the directory does not exist
            self._overlay_work_dir.mkdir(parents=True)

            # Remove old build artifacts
            for symlink in self._output_dir.glob("*.dtbo"):
                (symlink).unlink()

            pretty_print.print_build("Building devicetree overlays...")

            # Copy and adapt generated device tree sources that can be used as includes in devicetree overlays
            includes_dir = self._overlay_work_dir / "include"
            includes_dir.mkdir(parents=True)

            if (self._base_work_dir / "pl.dtsi").is_file():
                shutil.copy(self._base_work_dir / "pl.dtsi", includes_dir / "pl.dtsi")
                with (includes_dir / "pl.dtsi").open("r") as f:
                    pl_dtsi_content = f.readlines()

                # Modify pl.dtsi so that it can be used in devicetree overlays
                for i, line in enumerate(pl_dtsi_content):
                    if "/ {" in line:
                        del pl_dtsi_content[i]
                        break
                for i, line in enumerate(pl_dtsi_content):
                    if "amba_pl: amba_pl@0 {" in line:
                        pl_dtsi_content[i] = pl_dtsi_content[i].replace("amba_pl: amba_pl@0 {", "&amba_pl {")
                        break
                for i, line in enumerate(reversed(pl_dtsi_content)):
                    if "};" in line:
                        del pl_dtsi_content[-i - 1]
                        break

                with (includes_dir / "pl.dtsi").open("w") as f:
                    f.writelines(pl_dtsi_content)

            # Copy all overlays to the work directory to make them accessable in the container
            # The overlays are copied before every build to make sure they are up to date
            for overlay in self._dt_overlay_dir.glob("*.dtsi"):
                shutil.copy(overlay, self._overlay_work_dir / overlay.name)

            dt_overlays_build_commands = [
                f"cd {self._overlay_work_dir}",
                "for file in *.dtsi; do "
                '   name=$(printf "${file}" | awk -F/ "{print \$(NF)}" | awk -F. "{print \$(NF-1)}") && '
                f"  gcc -I {includes_dir} -E -nostdinc -undef -D__DTS__ -x assembler-with-cpp "
                "-o ${name}_res.dtsi ${name}.dtsi && "
                "   dtc -O dtb -o ${name}.dtbo -@ ${name}_res.dtsi; "
                "done",
            ]

            self.container_executor.exec_sh_commands(
                commands=dt_overlays_build_commands,
                dirs_to_mount=[(self._overlay_work_dir, "Z")],
                print_commands=True,
                logfile=self._block_temp_dir / "build_dt_overlays.log",
                output_scrolling=True,
            )

            self._output_dir.mkdir(parents=True, exist_ok=True)

            # Create symlink to the output files
            for symlink in self._overlay_work_dir.glob("*.dtbo"):
                (self._output_dir / symlink.name).symlink_to(symlink)

    def import_req_src_tpl(self):
        """
        This function checks whether there are already sources for this block
        and, if not, asks the user to import a source code template.

        Args:
            None

        Returns:
            None

        Raises:
            ValueError:
                If the CSV file that describes the devicetree includes has more than one column
        """

        super().import_req_src_tpl()

        # Import devicetree includes into the project configuration file
        try:
            dt_incl_list_file = self._dt_incl_dir / "includes.csv"
            with open(dt_incl_list_file, mode="r", newline="") as file:
                reader = csv.reader(file)
                dt_includes = list(reader)

            # Check the entire file before anything is done
            for dt_incl in dt_includes:
                if len(dt_incl) != 1:
                    raise ValueError(f"File '{dt_incl_list_file}' has more than one column")

            for dt_incl in dt_includes:
                # Add devicetree include to project configuration file
                # ToDo: Maybe the main project configuration file should not be hard coded here
                YAML_Editor.append_list_entry(
                    file=self._project_dir / "project.yml",
                    keys=["blocks", self.block_id, "project", "dt_includes"],
                    data=dt_incl[0],
                )
                # Add devicetree include to currently used project configuration
                if self.block_cfg.project.dt_includes == None:
                    self.block_cfg.project.dt_includes = [dt_incl[0]]
                else:
                    self.block_cfg.project.dt_includes.append(dt_incl[0])

            os.remove(dt_incl_list_file)
        except FileNotFoundError:
            pass
