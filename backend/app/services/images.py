"""
图片处理服务层。

提供图片校验和元信息提取功能。
使用 PIL 库解码图片，验证格式、大小和完整性。
"""

import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

# 文件大小限制：20MB
MAX_FILE_BYTES = 20 * 1024 * 1024
# 像素总量限制：5000万像素
MAX_PIXELS = 50_000_000
# 最小边长：32像素
MIN_SIDE = 32

# 支持的图片格式及其 MIME 类型
ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
# 格式对应的文件扩展名
EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


class ImageRejected(Exception):
    """图片校验失败，携带具体原因"""

    pass


@dataclass(frozen=True)
class ImageMeta:
    """
    图片元信息（不可变数据类）。

    - **image_format**: 图片格式（JPEG/PNG/WEBP）
    - **content_type**: MIME 类型
    - **extension**: 文件扩展名
    - **width**: 宽度（像素）
    - **height**: 高度（像素）
    - **size_bytes**: 文件大小（字节）
    - **has_alpha**: 是否含透明通道
    """

    image_format: str
    content_type: str
    extension: str
    width: int
    height: int
    size_bytes: int
    has_alpha: bool


def probe(data: bytes) -> ImageMeta:
    """
    校验图片并提取元信息。

    校验规则：
    - 文件不为空
    - 文件大小不超过 20MB
    - 格式为 JPG/PNG/WebP
    - 最短边不小于 32 像素
    - 像素总量不超过 5000 万
    - 完整解码以暴露截断或损坏的数据

    - **data**: 图片二进制数据
    - **返回**: 图片元信息
    - **抛出**: ImageRejected 校验失败
    """
    if not data:
        raise ImageRejected("文件为空")
    if len(data) > MAX_FILE_BYTES:
        raise ImageRejected(f"文件超过 {MAX_FILE_BYTES // 1024 // 1024} MB 上限")

    try:
        with Image.open(io.BytesIO(data)) as image:
            image_format = image.format or ""
            width, height = image.size
            has_alpha = image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info
            # 触发完整解码以暴露截断或损坏的数据
            image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageRejected("文件已损坏或不是受支持的图片") from exc

    if image_format not in ALLOWED_FORMATS:
        raise ImageRejected("仅支持 JPG、PNG 与 WebP")
    if min(width, height) < MIN_SIDE:
        raise ImageRejected(f"图片过小，最短边需不小于 {MIN_SIDE} 像素")
    if width * height > MAX_PIXELS:
        raise ImageRejected("图片像素总量过大")

    return ImageMeta(
        image_format=image_format,
        content_type=ALLOWED_FORMATS[image_format],
        extension=EXTENSIONS[image_format],
        width=width,
        height=height,
        size_bytes=len(data),
        has_alpha=has_alpha,
    )