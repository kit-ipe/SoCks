import sys
import pathlib

import pretty_print
import builder

class ZynqMP_AMD_Alma_RootFS_Builder_Alma8(builder.Builder):
    """
    AlmaLinux root file system builder class
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path):
        block_name = 'rootfs'

        super().__init__(project_cfg=project_cfg,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_name=block_name)

        # Import project configuration
        self._pc_alma_release = project_cfg['blocks']['rootfs']['release']

        self._rootfs_name = f'almalinux{self._pc_alma_release}_rev1_xck26'
        self._target_arch = 'aarch64'
        
        # Project directories
        self._repo_dir = self._project_src_dir / self._block_name / 'src'
        self._build_dir = self._work_dir / self._rootfs_name

        # Project files
        # Version tracking file that will be deployed to the root file system
        self._version_file = self._work_dir / 'fs_version'
        # Flag to remember if predefined file system layers have already been added
        self._pfs_added_flag = self._work_dir / '.pfsladded'
        # Flag to remember if users have already been added
        self._users_added_flag = self._work_dir / '.usersadded'


    def enable_multiarch(self):
        """
        Enable to execute binaries for different architectures in containers
        that are launched afterwards. This enables to execute x86 and arm64
        binaries in the same container. QEMU is automatically used when it
        is needed.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if list(pathlib.Path('/proc/sys/fs/binfmt_misc').glob('qemu-*')):
            pretty_print.print_build('No need to activate multiarch support for containers. It is already active...')
            return

        pretty_print.print_build('Activating multiarch support for containers...')

        if self._pc_container_tool  == 'docker':
            try:
                ZynqMP_AMD_Alma_RootFS_Builder_Alma8._run_sh_command(['docker', 'pull', 'multiarch/qemu-user-static'])
                ZynqMP_AMD_Alma_RootFS_Builder_Alma8._run_sh_command(['docker', 'run', '--rm', '--privileged', 'multiarch/qemu-user-static', '--reset', '-p', 'yes'])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while activating multiarch for docker: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'podman':
            try:
                ZynqMP_AMD_Alma_RootFS_Builder_Alma8._run_sh_command(['sudo', 'podman', 'pull', 'multiarch/qemu-user-static'])
                ZynqMP_AMD_Alma_RootFS_Builder_Alma8._run_sh_command(['sudo', 'podman', 'run', '--rm', '--privileged', 'multiarch/qemu-user-static', '--reset', '-p', 'yes'])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while activating multiarch for docker: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            pretty_print.print_warning(f'Multiarch is not activated in native mode.')
            return
        else:
            Builder._err_unsup_container_tool()


    def build_base_rootfs(self):
        """
        Builds the base root file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # In the last step, the service auditd.service is deactivated because it breaks things
        base_rootfs_build_commands = f'\'cd {self._repo_dir} && ' \
                                    f'python3 mkrootfs.py --root={self._build_dir} --arch={self._target_arch} --extra=extra_rpms.txt --releasever={self._pc_alma_release} && ' \
                                    f'mv {self._work_dir}/fs_version {self._build_dir}/etc/fs_version && ' \
                                    f'chmod 0444 {self._build_dir}/etc/fs_version && ' \
                                    f'rm -f {self._build_dir}/etc/systemd/system/multi-user.target.wants/auditd.service\''

        # Check whether the base root file system needs to be built
        if not ZynqMP_AMD_Alma_RootFS_Builder_Alma8._check_rebuilt_required(src_search_list=[self._repo_dir], src_ignore_list=[self._repo_dir / 'predefined_fs_layers', self._repo_dir / 'users'], out_search_list=[self._work_dir]):
            pretty_print.print_build('No need to rebuild the base root file system. No altered source files detected...')
            return

        pretty_print.print_build('Building the base root file system...')

        self._work_dir.mkdir(parents=True, exist_ok=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Create ID file. This file will be added to the RootFS as a read only file
        with self._version_file.open('w') as f:
            print("Filesystem version:", file=f)
            results = ZynqMP_AMD_Alma_RootFS_Builder_Alma8._get_sh_results(['git', '-C', str(self._project_dir), '--no-pager', 'show', '-s', '--format="Commit date: %ci  %d"'])
            print(results.stdout, file=f, end='')
            results = ZynqMP_AMD_Alma_RootFS_Builder_Alma8._get_sh_results(['git', '-C', str(self._project_dir), 'describe', '--dirty', '--always', '--tags', '--abbrev=14'])
            print(results.stdout, file=f, end='')

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                # The root user is used in this container. This is necessary in order to build a RootFS image.
                ZynqMP_AMD_Alma_RootFS_Builder_Alma8._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-u', 'root', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._work_dir}:{self._work_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', base_rootfs_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building the base root file system: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_Alma_RootFS_Builder_Alma8._run_sh_command(['sh', '-c', base_rootfs_build_commands])
        else:
            Builder._err_unsup_container_tool()

        # Remove flags
        self._pfs_added_flag.unlink(missing_ok=True)
        self._users_added_flag.unlink(missing_ok=True)


    def add_fs_layers(self):
        """
        Adds predefined file system layers to the root file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        add_fs_layers_commands = f'\'cd {self._repo_dir / "predefined_fs_layers"} && ' \
                                f'for dir in ./*; do "$dir"/install_layer.sh {self._build_dir}/; done\''

        # Check whether a RootFS is present
        if not pathlib.Path(self._build_dir).is_dir():
            pretty_print.print_error(f'RootFS at {self._build_dir} not found.')
            sys.exit(1)

        # Check whether the predefined file system layers need to be added
        if self._pfs_added_flag.is_file() and not ZynqMP_AMD_Alma_RootFS_Builder_Alma8._check_rebuilt_required(src_search_list=[self._repo_dir / 'predefined_fs_layers'], out_search_list=[self._work_dir]):
            pretty_print.print_build('No need to add predefined file system layers. No altered source files detected...')
            return

        pretty_print.print_build('Adding predefined file system layers...')

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                # The root user is used in this container. This is necessary in order to build a RootFS image.
                ZynqMP_AMD_Alma_RootFS_Builder_Alma8._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-u', 'root', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._work_dir}:{self._work_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', add_fs_layers_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while adding predefined file system layers: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_Alma_RootFS_Builder_Alma8._run_sh_command(['sh', '-c', add_fs_layers_commands])
        else:
            Builder._err_unsup_container_tool()

        # Create the flag if it doesn't exist and update the timestamps
        self._pfs_added_flag.touch()