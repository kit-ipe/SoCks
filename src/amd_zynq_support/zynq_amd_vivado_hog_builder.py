import pathlib

from amd_zynqmp_support.zynqmp_amd_vivado_hog_builder import ZynqMP_AMD_Vivado_Hog_Builder
from amd_zynq_support.zynq_amd_vivado_hog_model import Zynq_AMD_Vivado_Hog_Model


class Zynq_AMD_Vivado_Hog_Builder(ZynqMP_AMD_Vivado_Hog_Builder):
    """
    Builder class for AMD Vivado projects utilizing the Hog framework
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "vivado",
        block_description: str = "Build an AMD/Xilinx Vivado Project with HDL on git (Hog)",
        model_class: type[object] = Zynq_AMD_Vivado_Hog_Model,
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
