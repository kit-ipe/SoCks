import pathlib

from abstract_builders.alpinelinux_rootfs_builder import AlpineLinux_RootFS_Builder
from amd_zynqmp_support.zynqmp_alpinelinux_rootfs_model import ZynqMP_AlpineLinux_RootFS_Model


class ZynqMP_AlpineLinux_RootFS_Builder(AlpineLinux_RootFS_Builder):
    """
    Alpine Linux root file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "rootfs",
        block_description: str = "Build an Alpine Linux root file system",
        model_class: type[object] = ZynqMP_AlpineLinux_RootFS_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )
