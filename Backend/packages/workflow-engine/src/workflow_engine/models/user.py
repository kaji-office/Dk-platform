from enum import StrEnum

from pydantic import BaseModel, Field


class UserRole(StrEnum):
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"

class UserModel(BaseModel):
    id: str = Field(...)
    email: str = Field(...)
    role: UserRole = Field(default=UserRole.VIEWER)
    mfa_enabled: bool = Field(default=False)
