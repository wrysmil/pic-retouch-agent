import uuid

from pydantic import BaseModel, Field, field_validator


class Credentials(BaseModel):
    """用户登录凭证。"""

    username: str = Field(
        min_length=3,
        max_length=32,
        description="用户名，3-32 个字符，只能包含字母、数字和下划线",
    )
    password: str = Field(
        min_length=6,
        max_length=64,
        description="密码，6-64 个字符",
    )

    @field_validator("username")
    @classmethod
    def _normalize(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.replace("_", "").isalnum():
            raise ValueError("用户名只能包含字母、数字和下划线")
        return normalized


class UserOut(BaseModel):
    id: uuid.UUID
    username: str

    model_config = {"from_attributes": True}