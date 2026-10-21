/**
 * 上传前压缩：手机原片常见 5~15MB，经服务器中转在窄带机器上非常慢。
 * 长边压到 4K 内并重编码，通常能降到 1~3MB，同时保留交付所需的细节。
 */

const MAX_EDGE = 3840
const JPEG_QUALITY = 0.86
const WEBP_QUALITY = 0.9
/** 小文件已足够小，再编码只会损失画质 */
const SKIP_BYTES = 2 * 1024 * 1024

export async function prepareUpload(file: File): Promise<File> {
  if (file.size <= SKIP_BYTES) return file

  const url = URL.createObjectURL(file)
  try {
    const image = new Image()
    image.src = url
    await image.decode()

    const longest = Math.max(image.naturalWidth, image.naturalHeight)
    if (longest === 0) return file
    const scale = Math.min(1, MAX_EDGE / longest)

    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale))
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale))
    const context = canvas.getContext('2d')
    if (!context) return file

    context.imageSmoothingQuality = 'high'
    context.drawImage(image, 0, 0, canvas.width, canvas.height)

    // PNG/WebP 可能带透明通道，继续用 WebP 承载；JPEG 保持 JPEG
    const keepsAlpha = file.type === 'image/png' || file.type === 'image/webp'
    const type = keepsAlpha ? 'image/webp' : 'image/jpeg'
    const blob = await toBlob(canvas, type, keepsAlpha ? WEBP_QUALITY : JPEG_QUALITY)
    // 编码失败或压完反而更大时退回原文件，不让压缩成为上传失败的原因
    if (!blob || blob.size >= file.size) return file

    return new File([blob], withExtension(file.name, type), {
      type,
      lastModified: file.lastModified,
    })
  } catch {
    // 浏览器解不了的图交给后端给出统一错误
    return file
  } finally {
    URL.revokeObjectURL(url)
  }
}

function toBlob(canvas: HTMLCanvasElement, type: string, quality: number) {
  return new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, type, quality))
}

function withExtension(name: string, type: string) {
  const base = name.replace(/\.[^.]+$/, '')
  return `${base}.${type === 'image/webp' ? 'webp' : 'jpg'}`
}
