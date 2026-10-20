"""后台模型配置请求与响应模型。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.services.provider_url import MOCK_BASE_URL


class AdminConnectionOut(BaseModel):
    id: uuid.UUID
    slug: str
    vendor: str
    adapter_type: str
    display_name: str
    status: str
    current_version_id: uuid.UUID | None
    current_version_seq: int | None = None
    key_mask: str = ""
    base_url: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminConnectionCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9_\-]+$")
    vendor: str = Field(min_length=2, max_length=32)
    adapter_type: str = Field(
        pattern="^(dashscope|openai_compat|openai_image|toookens|minimax|mock)$"
    )
    display_name: str = Field(min_length=2, max_length=128)
    # mock 适配器不连厂商，地址与密钥都可以留空，由下面的校验器补占位值；
    # 其它适配器仍要求地址至少 8 字符、密钥非空。
    base_url: str = Field(default="", max_length=512)
    api_key: str = Field(default="", max_length=512)
    extra: dict | None = None

    @model_validator(mode="after")
    def _check_by_adapter(self) -> "AdminConnectionCreate":
        if self.adapter_type == "mock":
            self.base_url = self.base_url.strip() or MOCK_BASE_URL
            self.api_key = self.api_key.strip()
            return self
        if len(self.base_url.strip()) < 8:
            raise ValueError("厂商地址至少 8 个字符")
        if not self.api_key.strip():
            raise ValueError("厂商 API Key 不能为空")
        self.base_url = self.base_url.strip()
        self.api_key = self.api_key.strip()
        return self


class AdminConnectionVersionCreate(BaseModel):
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=512)
    extra: dict | None = None


class AdminModelOut(BaseModel):
    id: uuid.UUID
    slug: str
    connection_id: uuid.UUID
    vendor_model_id: str
    edit_vendor_model_id: str | None
    display_name: str
    model_type: str
    param_schema: dict
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminModelToggleOut(AdminModelOut):
    """启用/停用的结果。

    published_seq 给出这次操作顺带自动重发布的运行版本号；没有重发布时为 None，
    前端据此提示「已自动重发布 vN，新任务立即生效」。
    """

    published_seq: int | None = None


class AdminModelCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9_\-]+$")
    connection_id: uuid.UUID
    vendor_model_id: str = Field(min_length=1, max_length=128)
    edit_vendor_model_id: str | None = Field(default=None, max_length=128)
    display_name: str = Field(min_length=2, max_length=128)
    model_type: Literal["text", "image"]
    param_schema: dict | None = None


class AdminRuntimeOut(BaseModel):
    current_version_seq: int | None
    revision: int
    published_at: datetime | None
    published_by: uuid.UUID | None
    note: str
    text_model_id: uuid.UUID
    image_model_id: uuid.UUID


class AdminRuntimePublish(BaseModel):
    text_model_id: uuid.UUID
    image_model_id: uuid.UUID
    runtime_params: dict | None = None
    test_summary: dict | None = None
    note: str = ""
    expected_revision: int


class AdminRuntimeApply(BaseModel):
    """一键切换。

    只给出要改的槽位；没给的槽位保持当前生效版本里的模型不变。
    这样「只把生图换成 mock」不必先准备一个本地规划模型。
    """

    text_model_id: uuid.UUID | None = None
    image_model_id: uuid.UUID | None = None
    note: str = ""
    expected_revision: int


class AdminRuntimeRollback(BaseModel):
    target_seq: int = Field(ge=1)
    expected_revision: int


class AdminRuntimeVersionOut(BaseModel):
    id: uuid.UUID
    version_seq: int
    text_model_id: uuid.UUID
    image_model_id: uuid.UUID
    rolled_back_from: int | None
    published_by: uuid.UUID
    published_at: datetime
    note: str

    model_config = {"from_attributes": True}


class AdminTestRequest(BaseModel):
    capability: Literal["text", "image.generate", "image.edit"] = "image.generate"
    prompt: str = Field(default="一朵云", max_length=500)


class AdminTestResult(BaseModel):
    capability: str
    ok: bool
    detail: str
    duration_ms: int