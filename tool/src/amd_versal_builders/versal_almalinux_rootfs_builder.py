import sys
import pathlib
import hashlib
import tarfile
from dateutil import parser
import urllib
import requests
import validators
import tqdm
import inspect

import socks.pretty_print as pretty_print
from amd_zynqmp_builders.zynqmp_almalinux_rootfs_builder import ZynqMP_AlmaLinux_RootFS_Builder
from amd_versal_builders.versal_almalinux_rootfs_model import Versal_AlmaLinux_RootFS_Model


class Versal_AlmaLinux_RootFS_Builder(ZynqMP_AlmaLinux_RootFS_Builder):
    """
    AlmaLinux root file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "rootfs",
        block_description: str = "Build an AlmaLinux root file system",
        model_class: type[object] = Versal_AlmaLinux_RootFS_Model,
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
            "This block is experimental, it should not be used for production. "
            "Versal blocks should use the Vitis SDT flow instead of the XSCT flow, as soon as it is stable."
        )

    @property
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = {"kernel": [".*"]}
        return block_deps

    @property
    def _rootfs_name(self):
        return f"almalinux{self.block_cfg.project.release}_versal_{self.project_cfg.project.name}"
