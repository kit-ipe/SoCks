import sys
import pathlib
import shutil
import hashlib
import zipfile
from dateutil import parser
import urllib
import requests
import validators
import tqdm

import pretty_print
import builder

class ZynqMP_Alma_RootFS_Builder_Alma8(builder.Builder):
    """
    AlmaLinux root file system builder class
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path):
        block_name = 'rootfs'

        super().__init__(project_cfg=project_cfg,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_name=block_name)

        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        self._block_deps = {
            'kernel': ['kernel_modules.tar.gz'],
            'devicetree': ['system.dtb', 'system.dts'],
            'vivado': ['.*.xsa'],
            'rootfs': ['.*tar...']
        }

        # Import project configuration
        self._pc_alma_release = project_cfg['blocks']['rootfs']['release']

        self._rootfs_name = f'almalinux{self._pc_alma_release}_zynqmp_{self._pc_prj_name}'
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
        # File for saving the checksum of the Kernel module archive used
        self._source_kmods_md5_file = self._work_dir / 'source_kmodules.md5'
        # File for saving the checksum of the XSA archive used
        self._source_xsa_md5_file = self._work_dir / 'source_xsa.md5'


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
                ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command(['docker', 'pull', 'multiarch/qemu-user-static'])
                ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command(['docker', 'run', '--rm', '--privileged', 'multiarch/qemu-user-static', '--reset', '-p', 'yes'])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while activating multiarch for docker: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'podman':
            try:
                ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command(['sudo', 'podman', 'pull', 'multiarch/qemu-user-static'])
                ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command(['sudo', 'podman', 'run', '--rm', '--privileged', 'multiarch/qemu-user-static', '--reset', '-p', 'yes'])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while activating multiarch for docker: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            pretty_print.print_warning(f'Multiarch is not activated in native mode.')
            return
        else:
            self._err_unsup_container_tool()


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

        # Check whether the base root file system needs to be built
        if not ZynqMP_Alma_RootFS_Builder_Alma8._check_rebuilt_required(src_search_list=[self._repo_dir], src_ignore_list=[self._repo_dir / 'predefined_fs_layers', self._repo_dir / 'users'], out_search_list=[self._work_dir]):
            pretty_print.print_build('No need to rebuild the base root file system. No altered source files detected...')
            return

        pretty_print.print_build('Building the base root file system...')

        self._work_dir.mkdir(parents=True, exist_ok=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Create ID file. This file will be added to the RootFS as a read only file
        with self._version_file.open('w') as f:
            print("Filesystem version:", file=f)
            results = ZynqMP_Alma_RootFS_Builder_Alma8._get_sh_results(['git', '-C', str(self._project_dir), '--no-pager', 'show', '-s', '--format="Commit date: %ci  %d"'])
            print(results.stdout, file=f, end='')
            results = ZynqMP_Alma_RootFS_Builder_Alma8._get_sh_results(['git', '-C', str(self._project_dir), 'describe', '--dirty', '--always', '--tags', '--abbrev=14'])
            print(results.stdout, file=f, end='')

        # In the last step, the service auditd.service is deactivated because it breaks things
        base_rootfs_build_commands = f'\'cd {self._repo_dir} && ' \
                                    f'python3 mkrootfs.py --root={self._build_dir} --arch={self._target_arch} --extra=extra_rpms.txt --releasever={self._pc_alma_release} && ' \
                                    f'mv {self._work_dir}/fs_version {self._build_dir}/etc/fs_version && ' \
                                    f'chmod 0444 {self._build_dir}/etc/fs_version && ' \
                                    f'rm -f {self._build_dir}/etc/systemd/system/multi-user.target.wants/auditd.service\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                # The root user is used in this container. This is necessary in order to build a RootFS image.
                ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-u', 'root', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._work_dir}:{self._work_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', base_rootfs_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building the base root file system: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command(['sh', '-c', base_rootfs_build_commands])
        else:
            self._err_unsup_container_tool()

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

        # Check whether a RootFS is present
        if not self._build_dir.is_dir():
            pretty_print.print_error(f'RootFS at {self._build_dir} not found.')
            sys.exit(1)

        # Check whether the predefined file system layers need to be added
        if self._pfs_added_flag.is_file() and not ZynqMP_Alma_RootFS_Builder_Alma8._check_rebuilt_required(src_search_list=[self._repo_dir / 'predefined_fs_layers'], out_search_list=[self._work_dir]):
            pretty_print.print_build('No need to add predefined file system layers. No altered source files detected...')
            return

        pretty_print.print_build('Adding predefined file system layers...')

        add_fs_layers_commands = f'\'cd {self._repo_dir / "predefined_fs_layers"} && ' \
                                f'for dir in ./*; do "$dir"/install_layer.sh {self._build_dir}/; done\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                # The root user is used in this container. This is necessary in order to build a RootFS image.
                ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-u', 'root', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._work_dir}:{self._work_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', add_fs_layers_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while adding predefined file system layers: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command(['sh', '-c', add_fs_layers_commands])
        else:
            self._err_unsup_container_tool()

        # Create the flag if it doesn't exist and update the timestamps
        self._pfs_added_flag.touch()


    def add_users(self):
        """
        Adds users to the root file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether a RootFS is present
        if not self._build_dir.is_dir():
            pretty_print.print_error(f'RootFS at {self._build_dir} not found.')
            sys.exit(1)

        # Check whether users need to be added
        if self._users_added_flag.is_file() and not ZynqMP_Alma_RootFS_Builder_Alma8._check_rebuilt_required(src_search_list=[self._repo_dir / 'users'], out_search_list=[self._work_dir]):
            pretty_print.print_build('No need to add users. No altered source files detected...')
            return

        pretty_print.print_build('Adding users...')

        add_users_commands = f'\'cp -r {self._repo_dir / "users"} {self._build_dir / "tmp"} && ' \
                            f'chroot {self._build_dir} /bin/bash /tmp/users/add_users.sh && ' \
                            f'rm -rf {self._build_dir}/tmp/users\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                # The root user is used in this container. This is necessary in order to build a RootFS image.
                ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-u', 'root', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._work_dir}:{self._work_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', add_users_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while adding users: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command(['sh', '-c', add_users_commands])
        else:
            self._err_unsup_container_tool()

        # Create the flag if it doesn't exist and update the timestamps
        self._users_added_flag.touch()


    def add_kmodules(self):
        """
        Adds kernel modules to the root file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether a RootFS is present
        if not self._build_dir.is_dir():
            pretty_print.print_error(f'RootFS at {self._build_dir} not found.')
            sys.exit(1)

        kmods_archive = self._dependencies_dir / 'kernel' / 'kernel_modules.tar.gz'
        temp_kmods_archive = self._work_dir / kmods_archive.name

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(kmods_archive.read_bytes()).hexdigest()
        # Read md5 of previously used Kernel module archive, if any
        md5_existsing_file = 0
        if self._source_kmods_md5_file.is_file():
            with self._source_kmods_md5_file.open('r') as f:
                md5_existsing_file = f.read()

        # Check whether the Kernel modules need to be added
        if md5_existsing_file == md5_new_file:
            pretty_print.print_build('No need to add Kernel Modules. No altered source files detected...')
            return

        pretty_print.print_build('Adding Kernel Modules...')

        # Create copy of the Kernel module archive
        shutil.copy(kmods_archive, temp_kmods_archive)

        add_kmodules_commands = f'\'cd {self._work_dir} && ' \
                                f'tar -xzf kernel_modules.tar.gz && ' \
                                f'chown -R root:root lib && ' \
                                f'chmod -R 000 lib && ' \
                                f'chmod -R u=rwX,go=rX lib && ' \
                                f'rm -rf {self._build_dir}/lib/modules/* && ' \
                                f'mv lib/modules/* {self._build_dir}/lib/modules/ && ' \
                                f'rm -rf lib\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                # The root user is used in this container. This is necessary in order to build a RootFS image.
                ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-u', 'root', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._work_dir}:{self._work_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', add_kmodules_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while adding Kernel Modules: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command(['sh', '-c', add_kmodules_commands])
        else:
            self._err_unsup_container_tool()

        # Save checksum in file
        with self._source_kmods_md5_file.open('w') as f:
            print(md5_new_file, file=f, end='')

        # Delete copy of the Kernel module archive
        temp_kmods_archive.unlink()


    def add_pl(self):
        """
        Adds configuration files for the programmable logic (PL).

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether a RootFS is present
        if not self._build_dir.is_dir():
            pretty_print.print_error(f'RootFS at {self._build_dir} not found.')
            sys.exit(1)

        xsa_files = list((self._dependencies_dir / 'vivado').glob('*.xsa'))

        # Check if there is more than one XSA file in the xsa directory
        if len(xsa_files) != 1:
            pretty_print.print_error(f'Not exactly one XSA archive in {self._dependencies_dir / "vivado"}.')
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_xsa_file = hashlib.md5(xsa_files[0].read_bytes()).hexdigest()
        # Read md5 of previously used XSA archive, if any
        md5_existsing_xsa_file = 0
        if self._source_xsa_md5_file.is_file():
            with self._source_xsa_md5_file.open('r') as f:
                md5_existsing_xsa_file = f.read()

        # Check if the PL files need to be added
        if md5_existsing_xsa_file == md5_new_xsa_file and (self._build_dir / 'etc/dt-overlays').is_dir() and not ZynqMP_Alma_RootFS_Builder_Alma8._check_rebuilt_required(src_search_list=[self._dependencies_dir / 'devicetree'], out_search_list=[self._build_dir / 'etc/dt-overlays']):
            pretty_print.print_build('No need to add files for the programmable logic (PL). No altered source files detected...')
            return

        pretty_print.print_build('Adding files for the programmable logic (PL)...')

        # Extract .bit file from XSA archive
        bit_file = None
        with zipfile.ZipFile(xsa_files[0], 'r') as archive:
            # Find all .bit files in the archive
            bit_files = [file for file in archive.namelist() if file.endswith('.bit')]
            # Check if there is more than one bit file
            if len(bit_files) != 1:
                pretty_print.print_error(f'Not exactly one *.bit archive in {xsa_files[0]}.')
                sys.exit(1)
            # Extract the single .bit file
            archive.extract(bit_files[0], path=str(self._work_dir))
            # Rename the extracted file
            temp_bit_file = self._work_dir / bit_files[0]
            bit_file = self._work_dir / 'system.bit'
            temp_bit_file.rename(bit_file)

        # Copy all device tree overlays
        for file in (self._dependencies_dir / 'devicetree').glob('*.dtbo'):
            shutil.copy(file, self._work_dir / file.name)

        add_pl_commands = f'\'chown -R root:root {self._work_dir}/system.bit {self._work_dir}/*.dtbo && ' \
                        f'chmod -R u=rw,go=r {self._work_dir}/system.bit {self._work_dir}/*.dtbo && ' \
                        f'mv {self._work_dir}/system.bit {self._build_dir}/lib/firmware/ && ' \
                        f'mkdir -p {self._build_dir}/etc/dt-overlays && ' \
                        f'mv {self._work_dir}/*.dtbo {self._build_dir}/etc/dt-overlays/\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                # The root user is used in this container. This is necessary in order to build a RootFS image.
                ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-u', 'root', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._work_dir}:{self._work_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', add_pl_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while adding files for the programmable logic (PL): {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command(['sh', '-c', add_pl_commands])
        else:
            self._err_unsup_container_tool()

        # Save checksum in file
        with self._source_xsa_md5_file.open('w') as f:
            print(md5_new_xsa_file, file=f, end='')


    def build_tarball(self):
        """
        Packs the entire rootfs in a tarball.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check if the tarball needs to be built
        if not ZynqMP_Alma_RootFS_Builder_Alma8._check_rebuilt_required(src_search_list=[self._work_dir], out_search_list=[self._output_dir]):
            pretty_print.print_build('No need to rebuild tarball. No altered source files detected...')
            return

        pretty_print.print_build('Building tarball...')

        # Tar was tested with three compression options:
        # Option	Size	Duration
        # --xz	872M	real	17m59.080s
        # -I pxz	887M	real	3m43.987s
        # -I pigz	1.3G	real	0m20.747s
        tarball_build_commands = f'\'cd {self._build_dir} && ' \
                                f'tar -I pxz --numeric-owner -p -cf  {self._output_dir / f"{self._rootfs_name}.tar.xz"} ./ && ' \
                                f'if id {self._host_user} >/dev/null 2>&1; then ' \
                                f'    chown -R {self._host_user}:{self._host_user} {self._output_dir / f"{self._rootfs_name}.tar.xz"}; ' \
                                f'fi\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                # The root user is used in this container. This is necessary in order to build a RootFS image.
                ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-u', 'root', '-v', f'{self._work_dir}:{self._work_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', tarball_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building the tarball: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command(['sh', '-c', tarball_build_commands])
        else:
            self._err_unsup_container_tool()


    def build_prebuilt(self):
        """
        This target can be used to pre-build the RootFS, e.g. in a CI pipeline.
        The tarball is renamed to underline that it is only a pre-built and not
        a complete project file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        pretty_print.print_error(f'ToDo: This needs to be implemented!')
        sys.exit(1)


    def import_prebuilt(self):
        """
        Imports a pre-built root file system and overwrites the existing one.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Get path of the pre-built root file system
        if self._pc_project_prebuilt is None:
            pretty_print.print_error(f'The property blocks/{self._block_name}/project/pre-built is required to import the block, but it is not set.')
            sys.exit(1)
        elif validators.url(self._pc_project_prebuilt):
            self._download_prebuilt()
            downloads = list(self._download_dir.glob('*'))
            # Check if there is more than one file in the download directory
            if len(downloads) != 1:
                pretty_print.print_error(f'Not exactly one file in {self._download_dir}.')
                sys.exit(1)
            prebuilt_block_package = downloads[0]
        else:
            try:
                prebuilt_block_package = pathlib.Path(self._pc_project_prebuilt)
            except ValueError:
                pretty_print.print_error(f'{self._pc_project_prebuilt} is not a valid URL and not a valid path')
                sys.exit(1)

        # Check whether the file is a supported archive
        if prebuilt_block_package.name.partition('.')[2] not in ['tar.gz', 'tgz', 'tar.xz', 'txz']:
            pretty_print.print_error(f'Unable to import block package. The following archive type is not supported: {prebuilt_block_package.name.partition(".")[2]}')
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(prebuilt_block_package.read_bytes()).hexdigest()
        # Read md5 of previously used file, if any
        md5_existsing_file = 0
        if self._source_pb_md5_file.is_file():
            with self._source_pb_md5_file.open('r') as f:
                md5_existsing_file = f.read()

        # Check if the pre-built root file system needs to be imported
        if md5_existsing_file == md5_new_file:
            pretty_print.print_build('No need to import the pre-built root file system. No altered source files detected...')
            return

        self.clean_work(as_root=True)
        self.clean_output()
        self._work_dir.mkdir(parents=True)
        self._output_dir.mkdir(parents=True)

        # Create a copy of the pre-built archive in a location that is available in the container
        temp_prebuilt_rootfs_file = self._work_dir / prebuilt_block_package.name
        shutil.copy(prebuilt_block_package, temp_prebuilt_rootfs_file)

        pretty_print.print_build('Importing pre-built root file system...')

        extract_pb_rootfs_commands = f'\'mkdir -p {self._build_dir} && ' \
                                    f'tar --numeric-owner -p -xf {temp_prebuilt_rootfs_file} -C {self._build_dir}\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                # The root user is used in this container. This is necessary in order to build a RootFS image.
                ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-u', 'root', '-v', f'{self._work_dir}:{self._work_dir}:Z', self._container_image, 'sh', '-c', extract_pb_rootfs_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while importing the pre-built root file system: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_Alma_RootFS_Builder_Alma8._run_sh_command(['sh', '-c', extract_pb_rootfs_commands])
        else:
            self._err_unsup_container_tool()

        # Save checksum in file
        with self._source_pb_md5_file.open('w') as f:
            print(md5_new_file, file=f, end='')

        # Delete copy of the pre-built archive
        temp_prebuilt_rootfs_file.unlink()