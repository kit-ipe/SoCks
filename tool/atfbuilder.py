import builder

class ATFBuilder(builder.Builder):
    """
    ATF builder class
    """

    def __init__(self, socks_dir, project_dir):
        block_name = 'atf'

        source_repo_name = 'arm-trusted-firmware'
        source_repo_url = 'https://github.com/Xilinx/arm-trusted-firmware.git' # Should be read from YAML
        source_repo_branch = 'xilinx-v2022.2' # Should be read from YAML. At least the 2022.2 part.

        container_tool = 'docker' # Should be read from YAML

        container_image_name = 'atf-builder-alma9'
        container_image_tag = source_repo_branch
        container_image = container_image_name+':'+container_image_tag

        super().__init__(socks_dir=socks_dir,
                        block_name=block_name,
                        project_dir=project_dir,
                        source_repo_name=source_repo_name,
                        source_repo_url=source_repo_url,
                        source_repo_branch=source_repo_branch,
                        container_tool=container_tool,
                        container_image=container_image)