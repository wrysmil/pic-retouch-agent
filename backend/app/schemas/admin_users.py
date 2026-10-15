"""后台用户管理请求与响应模型。"""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class AdminUserOut(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    is_active: bool
    auth_version: int
    last_login_at: str | None = None
    created_at: str
    password_changed_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminUserList(BaseModel):
    total: int
    items: list[AdminUserOut]


class AdminCreateUser(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    role: str = Field(default="user", pattern="^(user|admin)$")
    is_active: bool = True


class AdminRoleUpdate(BaseModel):
    role: str = Field(pattern="^(user|admin)$")


class AdminActiveUpdate(BaseModel):
    is_active: bool


class AdminResetPassword(BaseModel):
    new_password: str = Field(min_length=6, max_length=64)