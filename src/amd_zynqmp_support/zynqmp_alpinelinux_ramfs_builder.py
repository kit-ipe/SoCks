import pathlib

from abstract_builders.alpinelinux_ramfs_builder import AlpineLinux_RAMFS_Builder
from amd_zynqmp_support.zynqmp_alpinelinux_ramfs_model import ZynqMP_AlpineLinux_RAMFS_Model


class ZynqMP_AlpineLinux_RAMFS_Builder(AlpineLinux_RAMFS_Builder):
    """
    Alpine Linux RAM file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "ramfs",
        block_description: str = "Build an Alpine Linux RAM file system",
        model_class: type[object] = ZynqMP_AlpineLinux_RAMFS_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )
