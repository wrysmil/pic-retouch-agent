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
    # 浏览器打开签名 URL 的地址；空则与 s3_endpoint 相同
    s3_public_endpoint: str = ""
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

    # AI 模型（规划 / 文生图 / 图编辑）不再从环境变量读取，统一由后台「模型配置」
    # 发布运行版本后，经 services.model_runtime 按版本解析连接与密钥。

    # 抠图 provider: auto（有 rembg 用 rembg，否则四角抠图）| rembg | corner（测试强制）
    matting_provider: str = "auto"
    # 文字识别 provider: auto（有 rapidocr 则拆出文字层）| rapidocr | none（测试强制）
    ocr_provider: str = "auto"

    # 厂商 API Key 加密主密钥（Fernet url-safe base64，32 字节）。
    # 未设置时禁用密钥持久化：连接仍可登记，但保存时立即报错。
    secret_enc_key: str = ""

    # 管理员通过后台保存的厂商 base URL 白名单（逗号分隔）。
    # 列表外的地址直接拒绝，避免把内部地址 / 第三方任意域名配入。
    # 设 "allow-localhost" 单独开启开发期本地放行。
    allowed_provider_hosts: str = "api.openai.com,dashscope.aliyuncs.com"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def allow_local_provider_hosts(self) -> bool:
        return self.allowed_provider_hosts.strip().lower() == "allow-localhost"

    @property
    def provider_host_allowlist(self) -> set[str]:
        if self.allow_local_provider_hosts:
            return set()
        return {host.strip().lower() for host in self.allowed_provider_hosts.split(",") if host.strip()}

    @property
    def frontend_dist(self) -> Path:
        return ROOT_DIR / "frontend" / "dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()
