from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 运行环境: development | staging | production
    app_env: str = "development"
    # API 服务监听端口
    api_port: int = 7302

    # PostgreSQL 连接串（asyncpg 驱动）
    database_url: str = "postgresql+asyncpg://retouch:retouch_dev@localhost:7311/retouch"
    # Redis 连接串，用于缓存/队列等
    redis_url: str = "redis://localhost:7312"

    # S3/MinIO 对象存储服务地址
    s3_endpoint: str = "http://localhost:7313"
    # S3 访问密钥 ID
    s3_access_key: str = "retouch"
    # S3 访问密钥 Secret
    s3_secret_key: str = "retouch_dev"
    # S3 存储桶名称
    s3_bucket: str = "retouch"
    # 签名 URL 有效期，秒
    s3_url_ttl: int = 900

    # JWT 签名密钥，HS256 要求不低于 32 字节
    jwt_secret: str = "dev-only-secret-please-change-in-production"
    # JWT 过期时间，小时
    jwt_ttl_hours: int = 24

    # 文生图/图生图 provider: mock | dashscope
    image_provider: str = "mock"
    # 阿里云百炼 DashScope API Key
    dashscope_api_key: str = ""
    # 可改为业务空间专属域名 https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com
    dashscope_base_url: str = "https://dashscope.aliyuncs.com"
    # 文生图模型名
    text_to_image_model: str = "qwen-image-3.0-pro"
    # 图生图（图像编辑）模型名
    image_edit_model: str = "qwen-image-edit-max"
    # 智能规划（文案/脚本生成）模型名
    planner_model: str = "qwen-plus"
    # 抠图 provider: auto（有 rembg 用 rembg，否则四角抠图）| rembg | corner（测试强制）
    matting_provider: str = "auto"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def frontend_dist(self) -> Path:
        return ROOT_DIR / "frontend" / "dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()
