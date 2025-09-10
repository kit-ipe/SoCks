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
from amd_zynqmp_support.zynqmp_debian_rootfs_builder import ZynqMP_Debian_RootFS_Builder
from amd_versal_support.versal_debian_rootfs_model import Versal_Debian_RootFS_Model


class Versal_Debian_RootFS_Builder(ZynqMP_Debian_RootFS_Builder):
    """
    Debian root file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "rootfs",
        block_description: str = "Build a Debian root file system",
        model_class: type[object] = Versal_Debian_RootFS_Model,
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
    def _file_system_name(self):
        return f"debian_{self.block_cfg.project.release}_versal_{self.project_cfg.project.name}"
