import sys
import pathlib
import shutil
import hashlib
import tarfile
import stat
import urllib
import validators
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from amd_zynqmp_support.zynqmp_amd_petalinux_rootfs_builder import ZynqMP_AMD_PetaLinux_RootFS_Builder
from amd_zynqmp_support.zynqmp_amd_petalinux_ramfs_model import ZynqMP_AMD_PetaLinux_RAMFS_Model


class ZynqMP_AMD_PetaLinux_RAMFS_Builder(ZynqMP_AMD_PetaLinux_RootFS_Builder):
    """
    AMD PetaLinux RAM file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "ramfs",
        block_description: str = "Build an AMD PetaLinux RAM file system",
        model_class: type[object] = ZynqMP_AMD_PetaLinux_RAMFS_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

    def build_archive(self, prebuilt: bool = False):
        """
        Packs the entire ram file system in an archive.

        Args:
            prebuilt:
                Set to True if the archive will contain pre-built files
                instead of a complete project file system.

        Returns:
            None

        Raises:
            None
        """

        if prebuilt:
            archive_name = f"petalinux_zynqmp_pre-built"
        else:
            archive_name = self._file_system_name

        self._build_archive(archive_name=archive_name, file_extension="cpio.gz")
