import builder

class ATFBuilder(builder.Builder):
    """
    ATF builder class
    """

    def __init__(self):
        self.block_name = 'atf'

        super().__init__(self.block_name)

        self.source_repo_url = 'https://github.com/Xilinx/arm-trusted-firmware.git' # Should be read from YAML
        self.source_repo_branch = 'xilinx-v2022.2' # Should be read from YAML. At least the 2022.2 part.
        self.source_repo_dir = self.repo_dir+'/arm-trusted-firmware-'+self.source_repo_branch