"""后台模型配置请求与响应模型。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    adapter_type: str = Field(pattern="^(dashscope|openai_compat|openai_image|mock)$")
    display_name: str = Field(min_length=2, max_length=128)
    base_url: str = Field(min_length=8, max_length=512)
    api_key: str = Field(min_length=1, max_length=512)
    extra: dict | None = None


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