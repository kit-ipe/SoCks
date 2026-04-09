import pathlib

from abstract_builders.ubuntu_rootfs_builder import Ubuntu_RootFS_Builder
from amd_zynqmp_support.zynqmp_ubuntu_rootfs_model import ZynqMP_Ubuntu_RootFS_Model


class ZynqMP_Ubuntu_RootFS_Builder(Ubuntu_RootFS_Builder):
    """
    Ubuntu root file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "rootfs",
        block_description: str = "Build a Ubuntu root file system",
        model_class: type[object] = ZynqMP_Ubuntu_RootFS_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

    @property
    def _target_arch_dist(self):
        return "arm64"  # Ubuntu refers to this architecture as 'arm64' rather than 'aarch64'

    @property
    def _target_arch_qemu(self):
        return "aarch64"
