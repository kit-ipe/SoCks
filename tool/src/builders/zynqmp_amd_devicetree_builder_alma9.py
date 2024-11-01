import sys
import pathlib
import shutil
import urllib
import hashlib

import socks.pretty_print as pretty_print
from socks.amd_builder import AMD_Builder

class ZynqMP_AMD_Devicetree_Builder_Alma9(AMD_Builder):
    """
    AMD devicetree builder class
    """

    def __init__(self, project_cfg: dict, project_cfg_files: list, socks_dir: pathlib.Path, project_dir: pathlib.Path, block_id: str = 'devicetree', block_description: str = 'Build the Devicetree for ZynqMP devices'):

        super().__init__(project_cfg=project_cfg,
                        project_cfg_files=project_cfg_files,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_id=block_id,
                        block_description=block_description)

        # Import project configuration
        self._pc_project_source = project_cfg['blocks'][self.block_id]['project']['build-srcs']['source']
        if 'branch' in project_cfg['blocks'][self.block_id]['project']['build-srcs']:
            self._pc_project_branch = project_cfg['blocks'][self.block_id]['project']['build-srcs']['branch']

        # Find sources for this block
        self._source_repo, self._local_source_dir = self._get_single_source()

        # Project directories
        self._source_repo_dir = self._repo_dir / f'{pathlib.Path(urllib.parse.urlparse(url=self._source_repo["url"]).path).stem}-{self._source_repo["branch"]}'
        self._dt_incl_dir = self._block_src_dir / 'dt_includes'
        self._dt_overlay_dir = self._block_src_dir / 'dt_overlays'
        self._base_work_dir = self._work_dir / 'base'
        self._overlay_work_dir = self._work_dir / 'overlays'

        # Project files
        # ASCII file with all devicetree includes for the base devicetree
        self._dt_incl_list_file = self._dt_incl_dir / 'includes.cfg'

        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        self._block_deps = {
            'vivado': ['.*.xsa']
        }

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {
            'prepare': [],
            'build': [],
            'clean': [],
            'create-patches': [],
            'start-container': []
        }
        self.block_cmds['clean'].extend([self.build_container_image, self.clean_download, self.clean_work, self.clean_repo, self.clean_source_xsa, self.clean_dependencies, self.clean_output, self.clean_block_temp])
        if self._pc_block_source == 'build':
            self.block_cmds['prepare'].extend([self.build_container_image, self.import_dependencies, self.init_repo, self.apply_patches, self.import_xsa, self.prepare_dt_sources, self.apply_patches])
            self.block_cmds['build'].extend(self.block_cmds['prepare'])
            self.block_cmds['build'].extend([self.build_base_devicetree, self.build_dt_overlays, self.export_block_package])
            self.block_cmds['create-patches'].extend([self.create_patches])
            self.block_cmds['start-container'].extend([self.build_container_image, self.start_container])
        elif self._pc_block_source == 'import':
            self.block_cmds['build'].extend([self.import_prebuilt])


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

        xsa_files = list(self._xsa_dir.glob('*.xsa'))

        # Check if there is more than one XSA file in the xsa directory
        if len(xsa_files) != 1:
            pretty_print.print_error(f'Not exactly one XSA archive in {self._xsa_dir}.')
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(xsa_files[0].read_bytes()).hexdigest()
        # Read md5 of previously used XSA archive, if any
        md5_existsing_file = 0
        if self._source_xsa_md5_file.is_file():
            with self._source_xsa_md5_file.open('r') as f:
                md5_existsing_file = f.read()

        # Check if the project needs to be created
        if md5_existsing_file == md5_new_file:
            pretty_print.print_warning('No new XSA archive recognized. Devicetree sources are not recreated.')
            return

        self.check_amd_tools(required_tools=['vitis'])

        self.clean_work()
        self._base_work_dir.mkdir(parents=True)

        pretty_print.print_build('Preparing devicetree sources...')

        prep_dt_srcs_commands = f'\'export XILINXD_LICENSE_FILE={self._amd_license} && ' \
                                f'source {self._amd_vitis_path}/settings64.sh && ' \
                                f'SOURCE_XSA_PATH=$(ls {self._xsa_dir}/*.xsa) && ' \
                                'printf \"hsi open_hw_design ${SOURCE_XSA_PATH}' \
                                f'    \r\nhsi set_repo_path {self._source_repo_dir} ' \
                                '    \r\nhsi create_sw_design device-tree -os device_tree -proc psu_cortexa53_0 ' \
                                f'    \r\nhsi generate_target -dir {self._base_work_dir} ' \
                                f'    \r\nhsi close_hw_design [hsi current_hw_design]\" > {self._base_work_dir}/generate_dts_prj.tcl && ' \
                                f'xsct -nodisp {self._base_work_dir}/generate_dts_prj.tcl\''

        self.run_containerizable_sh_command(command=prep_dt_srcs_commands,
                    dirs_to_mount=[(pathlib.Path(self._amd_tools_path), 'ro'), (self._xsa_dir, 'Z'),
                                (self._repo_dir, 'Z'), (self._base_work_dir, 'Z')])

        # Save checksum in file
        with self._source_xsa_md5_file.open('w') as f:
            print(md5_new_file, file=f, end='')


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
        if not ZynqMP_AMD_Devicetree_Builder_Alma9._check_rebuild_required(src_search_list=[self._dt_incl_dir, self._patch_dir, self._source_repo_dir], out_search_list=[self._base_work_dir / 'system.dtb']):
            pretty_print.print_build('No need to rebuild the devicetree. No altered source files detected...')
            return

        pretty_print.print_build('Building the base devicetree...')

        if self._dt_incl_list_file.is_file():
            with self._dt_incl_list_file.open('r') as incl_list_file:
                for incl in incl_list_file:
                    incl = incl.strip()
                    if incl:
                        # Devicetree includes are copied before every build to make sure they are up to date
                        shutil.copy(self._dt_incl_dir / incl, self._base_work_dir / incl)
                        # Check if this file is already included, and if not, include it
                        with (self._base_work_dir / 'system-top.dts').open('r+') as dts_top_file:
                            contents = dts_top_file.read()
                            incl_line = f'#include "{incl}"\n'
                            if incl_line not in contents:
                                # If the line was not found, the file pointer is now at the end
                                # Write the include line
                                dts_top_file.write(incl_line)

        # The *.dts file created by gcc is for humans difficult to read. Therefore, in the last step, it is replaced by one created with the devicetree compiler.
        dt_build_commands = f'\'cd {self._base_work_dir} && ' \
                            'gcc -E -nostdinc -undef -D__DTS__ -x assembler-with-cpp -o system.dts system-top.dts && ' \
                            'dtc -I dts -O dtb -@ -o system.dtb system.dts && ' \
                            'dtc -I dtb -O dts -o system.dts system.dtb\''

        self.run_containerizable_sh_command(command=dt_build_commands,
                    dirs_to_mount=[(self._base_work_dir, 'Z')])

        self._output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create symlink to the output files
        (self._output_dir / 'system.dtb').unlink(missing_ok=True)
        (self._output_dir / 'system.dtb').symlink_to(self._base_work_dir / 'system.dtb')
        (self._output_dir / 'system.dts').unlink(missing_ok=True)
        (self._output_dir / 'system.dts').symlink_to(self._base_work_dir / 'system.dts')


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
        if not self._dt_overlay_dir.is_dir() or not any(self._dt_overlay_dir.iterdir()) or not ZynqMP_AMD_Devicetree_Builder_Alma9._check_rebuild_required(src_search_list=[self._dt_overlay_dir], out_search_list=list(self._overlay_work_dir.glob('*.dtbo'))):
            pretty_print.print_build('No need to rebuild devicetree overlays. No altered source files detected...')
            return

        # Clean overlay work directory
        try:
            shutil.rmtree(self._overlay_work_dir)
        except FileNotFoundError:
            pass # Ignore if the directory does not exist
        self._overlay_work_dir.mkdir(parents=True)

        pretty_print.print_build('Building devicetree overlays...')

        # Copy and adapt generated device tree sources that can be used as includes in devicetree overlays
        includes_dir = self._overlay_work_dir / 'include'
        includes_dir.mkdir(parents=True)
        shutil.copy(self._base_work_dir / 'pl.dtsi', includes_dir / 'pl.dtsi')
        with (includes_dir / 'pl.dtsi').open('r') as f:
            pl_dtsi_content = f.readlines()

        # Modify pl.dtsi so that it can be used in devicetree overlays
        for i, line in enumerate(pl_dtsi_content):
            if '/ {' in line:
                del pl_dtsi_content[i]
                break
        for i, line in enumerate(pl_dtsi_content):
            if 'amba_pl: amba_pl@0 {' in line:
                pl_dtsi_content[i] = pl_dtsi_content[i].replace('amba_pl: amba_pl@0 {', '&amba_pl {')
                break
        for i, line in enumerate(reversed(pl_dtsi_content)):
            if '};' in line:
                del pl_dtsi_content[-i-1]
                break

        with (includes_dir / 'pl.dtsi').open('w') as f:
            f.writelines(pl_dtsi_content)

        # Copy all overlays to the work directory to make them accessable in the container
        # The overlays are copied before every build to make sure they are up to date
        for overlay in self._dt_overlay_dir.glob('*.dtsi'):
            shutil.copy(overlay, self._overlay_work_dir / overlay.name)

        dt_overlays_build_commands = f'\'cd {self._overlay_work_dir} && ' \
                                    'for file in *.dtsi; do ' \
                                    '   name=$(printf "${file}" | awk -F/ "{print \$(NF)}" | ' \
                                                'awk -F. "{print \$(NF-1)}") && ' \
                                    f'  gcc -I {includes_dir} -E -nostdinc -undef -D__DTS__ -x assembler-with-cpp ' \
                                                '-o ${name}_res.dtsi ${name}.dtsi && ' \
                                    '   dtc -O dtb -o ${name}.dtbo -@ ${name}_res.dtsi; ' \
                                    'done\''

        self.run_containerizable_sh_command(command=dt_overlays_build_commands,
                    dirs_to_mount=[(self._overlay_work_dir, 'Z')])

        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Create symlink to the output files
        for symlink in self._output_dir.glob('*.dtbo'):
            (symlink).unlink()
        for symlink in self._overlay_work_dir.glob('*.dtbo'):
            (self._output_dir / symlink.name).symlink_to(symlink)