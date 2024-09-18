import sys
import pathlib
import shutil
import hashlib

import pretty_print
import amd_builder

class ZynqMP_AMD_PMUFW_Builder_Alma9(amd_builder.AMD_Builder):
    """
    AMD PMU firmware builder class
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path):
        block_name = 'pmu-fw'

        super().__init__(project_cfg=project_cfg,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_name=block_name)

        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        self._block_deps = {
            'vivado': ['.*.xsa']
        }


    def create_pmufw_project(self):
        """
        Creates the PMU firmware project.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        pretty_print.print_build('Creating the PMU Firmware project...')

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
            pretty_print.print_warning('No new XSA archive recognized. PMU Firmware project is not created.')
            return
        
        # Check if Xilinx tools are available
        if not pathlib.Path(self._pc_xilinx_path).is_dir():
            pretty_print.print_error(f'Directory {self._pc_xilinx_path} not found.')
            sys.exit(1)

        self.clean_work()
        self.clean_repo()
        self._work_dir.mkdir(parents=True)
        self._repo_dir.mkdir(parents=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        create_pmufw_project_commands = f'\'export XILINXD_LICENSE_FILE={self._pc_xilinx_license} && ' \
                                            f'source {self._pc_xilinx_path}/Vitis/{self._pc_xilinx_version}/settings64.sh && ' \
                                            f'SOURCE_XSA_PATH=$(ls {self._xsa_dir}/*.xsa) && ' \
                                            'printf \"set hwdsgn [hsi open_hw_design ${SOURCE_XSA_PATH}]' \
                                            f'    \r\nhsi generate_app -hw \$hwdsgn -os standalone -proc psu_pmu_0 -app zynqmp_pmufw -sw pmufw -dir {self._source_repo_dir}\" > {self._work_dir}/generate_pmufw_prj.tcl && ' \
                                            f'xsct -nodisp {self._work_dir}/generate_pmufw_prj.tcl && ' \
                                            f'git -C {self._source_repo_dir} init --initial-branch=main && ' \
                                            f'git -C {self._source_repo_dir} config user.email "container-user@example.com" && ' \
                                            f'git -C {self._source_repo_dir} config user.name "container-user" && ' \
                                            f'git -C {self._source_repo_dir} add {self._source_repo_dir}/. && ' \
                                            f'git -C {self._source_repo_dir} commit --quiet -m "Initial commit"\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                ZynqMP_AMD_PMUFW_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._pc_xilinx_path}:{self._pc_xilinx_path}:ro', '-v', f'{self._xsa_dir}:{self._xsa_dir}:Z', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._work_dir}:{self._work_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', create_pmufw_project_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while creating the PMU Firmware project: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_PMUFW_Builder_Alma9._run_sh_command(['sh', '-c', create_pmufw_project_commands])
        else:
            self._err_unsup_container_tool()

        # Create new branch self._git_local_ref_branch. This branch is used as a reference where all existing patches are applied to the git sources
        ZynqMP_AMD_PMUFW_Builder_Alma9._run_sh_command(['git', '-C', str(self._source_repo_dir), 'switch', '-c', self._git_local_ref_branch])
        # Create new branch self._git_local_dev_branch. This branch is used as the local development branch. New patches can be created from this branch.
        ZynqMP_AMD_PMUFW_Builder_Alma9._run_sh_command(['git', '-C', str(self._source_repo_dir), 'switch', '-c', self._git_local_dev_branch])

        # Save checksum in file
        with self._source_xsa_md5_file.open('w') as f:
            print(md5_new_file, file=f, end='')


    def build_pmufw(self):
        """
        Builds the PMU Firmware.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the PMU Firmware needs to be built
        if not ZynqMP_AMD_PMUFW_Builder_Alma9._check_rebuilt_required(src_search_list=[self._patch_dir, self._source_repo_dir], src_ignore_list=[self._source_repo_dir / 'executable.elf'], out_search_list=[self._source_repo_dir / 'executable.elf']):
            pretty_print.print_build('No need to rebuild the PMU Firmware. No altered source files detected...')
            return

        pretty_print.print_build('Building the PMU Firmware...')

        # Check if Xilinx tools are available
        if not pathlib.Path(self._pc_xilinx_path).is_dir():
            pretty_print.print_error(f'Directory {self._pc_xilinx_path} not found.')
            sys.exit(1)

        pmufw_build_commands = f'\'export XILINXD_LICENSE_FILE={self._pc_xilinx_license} && ' \
                                f'source {self._pc_xilinx_path}/Vitis/{self._pc_xilinx_version}/settings64.sh && ' \
                                f'cd {self._source_repo_dir} && ' \
                                'make clean && ' \
                                'make\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                ZynqMP_AMD_PMUFW_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._pc_xilinx_path}:{self._pc_xilinx_path}:ro', '-v', f'{self._xsa_dir}:{self._xsa_dir}:Z', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', pmufw_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building the PMU Firmware: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_PMUFW_Builder_Alma9._run_sh_command(['sh', '-c', pmufw_build_commands])
        else:
            self._err_unsup_container_tool()

        # Create symlink to the output file
        (self._output_dir / 'pmufw.elf').unlink(missing_ok=True)
        (self._output_dir / 'pmufw.elf').symlink_to(self._source_repo_dir / 'executable.elf')