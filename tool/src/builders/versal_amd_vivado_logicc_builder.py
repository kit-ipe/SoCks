import pathlib

from builders.zynqmp_amd_vivado_logicc_builder import ZynqMP_AMD_Vivado_logicc_Builder
from builders.versal_amd_vivado_logicc_model import Versal_AMD_Vivado_logicc_Model


class Versal_AMD_Vivado_logicc_Builder(ZynqMP_AMD_Vivado_logicc_Builder):
    """
    Builder class for AMD Vivado projects utilizing the logicc framework
    """

    def __init__(
        self,
        project_cfg: dict,
        project_cfg_files: list,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "vivado",
        block_description: str = "Build an AMD/Xilinx Vivado Project with logicc",
        model_class: type[object] = Versal_AMD_Vivado_logicc_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            project_cfg_files=project_cfg_files,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        self.pre_action_warnings.append(
            "This block is experimental, it should not be used for production. "
            "Versal blocks should use the Vitis SDT flow instead of the XSCT flow, as soon as it is stable."
        )
