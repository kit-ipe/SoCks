import pathlib

from abstract_builders.almalinux_rootfs_builder import AlmaLinux_RootFS_Builder
from raspberrypi_support.raspberrypi_almalinux_rootfs_model import RaspberryPi_AlmaLinux_RootFS_Model


class RaspberryPi_AlmaLinux_RootFS_Builder(AlmaLinux_RootFS_Builder):
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
        model_class: type[object] = RaspberryPi_AlmaLinux_RootFS_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        self.pre_action_warnings.append("This block is experimental, it should not be used for production.")

    @property
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = {"kernel": [".*"]}
        return block_deps
