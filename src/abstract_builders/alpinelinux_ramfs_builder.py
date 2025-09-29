import pathlib

from abstract_builders.alpinelinux_rootfs_builder import AlpineLinux_RootFS_Builder


class AlpineLinux_RAMFS_Builder(AlpineLinux_RootFS_Builder):
    """
    Alpine Linux RAM file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        model_class: type[object],
        block_id: str = "ramfs",
        block_description: str = "Build an Alpine Linux RAM file system",
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
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = {
            "kernel": [".*"],
        }
        return block_deps

    def build_archive(self, prebuilt: bool = False):
        """
        Packs the entire RAM file system in an archive.

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
            archive_name = f"{self._file_system_name}_pre-built"
        else:
            archive_name = self._file_system_name

        self._build_archive(archive_name=archive_name, file_extension="cpio.gz")
