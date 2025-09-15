import pathlib

from abstract_builders.debian_rootfs_builder import Debian_RootFS_Builder


class Ubuntu_RootFS_Builder(Debian_RootFS_Builder):
    """
    Ubuntu root file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        model_class: type[object],
        block_id: str = "rootfs",
        block_description: str = "Build a Ubuntu root file system",
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
    def _file_system_name(self):
        return f"ubuntu_{self.block_cfg.project.release}_{self.project_cfg.project.type.lower()}_{self.project_cfg.project.name}"
