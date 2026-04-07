import pathlib

from abstract_builders.debian_rootfs_builder import Debian_RootFS_Builder
from amd_zynq_support.zynq_debian_rootfs_model import Zynq_Debian_RootFS_Model


class Zynq_Debian_RootFS_Builder(Debian_RootFS_Builder):
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
        model_class: type[object] = Zynq_Debian_RootFS_Model,
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
            f"Builder '{self.__class__.__name__}' is experimental and should not be used for production."
        )

    @property
    def _target_arch_dist(self):
        return "armhf"

    @property
    def _target_arch_qemu(self):
        return "arm"
