from pydantic import BaseModel, Field, ConfigDict, StringConstraints
from typing import Optional
from typing_extensions import Annotated


class File_System_Installable_Build_Time_Item_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    src_block: str = Field(
        default=..., description="Name of the block in whose block package the source file is located"
    )
    src_name: str = Field(default=..., description="Path to the source item in the block package")
    dest_path: str = Field(
        default=..., description="Directory in the destination file system in which the item is to be placed"
    )
    dest_name: Optional[str] = Field(
        default="",
        description="Name of the item at the destination. If nothing is specified here, the name of the source file is used.",
    )
    dest_owner_group: Optional[str] = Field(
        default=None, description="A string to be passed to chown to set the file owner and group"
    )
    dest_permissions: Optional[str] = Field(
        default=None, description="A string to be passed to chmod to set the file permissions"
    )


class File_System_User_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(default=..., description="Username")
    pw_hash: str = Field(default=..., description="Password hash generated with 'openssl passwd -1'")
    groups: Optional[list[str]] = Field(default=[], description="Groups to which the user is to be added")
    ssh_key: Optional[Annotated[str, StringConstraints(pattern=r"^.*.pub$")]] = Field(
        default=None,
        description="A public SSH key on the host system that is copied to the file system to enable SSH access without using a password.",
    )
