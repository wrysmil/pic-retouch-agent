import { useEffect, useMemo, useRef, useState } from 'react'

import type { Layer } from '@/api/sessions'
import { preloadCanvasImage } from '@/hooks/useCanvasImage'

const SIZE = 56
const CACHE_LIMIT = 200
const cache = new Map<string, string>()
const failed = new Set<string>()
let frame = 0

function remember(key: string, value: string) {
  cache.delete(key)
  cache.set(key, value)
  while (cache.size > CACHE_LIMIT) {
    const oldest = cache.keys().next().value
    if (!oldest || oldest === key) break
    cache.delete(oldest)
  }
}

export function thumbKey(layer: Layer) {
  const content = JSON.stringify({
    kind: layer.kind,
    asset: layer.asset_id,
    text: layer.text,
    font: layer.font_size,
    fill: layer.fill,
    shape: layer.shape_type,
    stroke: layer.stroke,
    strokeWidth: layer.stroke_width,
    width: layer.width,
    height: layer.height,
    sx: layer.transform.scale_x,
    sy: layer.transform.scale_y,
    rotation: layer.transform.rotation,
    opacity: layer.opacity,
    visible: layer.visible,
  })
  return `thumb:${layer.id}:${layer.kind}:${content}`
}

function checkerboard(ctx: CanvasRenderingContext2D) {
  ctx.fillStyle = '#f3f3ef'
  ctx.fillRect(0, 0, SIZE, SIZE)
  ctx.fillStyle = '#e9e9e4'
  for (let y = 0; y < SIZE; y += 8) {
    for (let x = 0; x < SIZE; x += 8) {
      if ((x / 8 + y / 8) % 2 === 0) ctx.fillRect(x, y, 8, 8)
    }
  }
}

async function renderLayer(layer: Layer, url: string | undefined): Promise<string | null> {
  if (layer.kind === 'image') {
    if (!url) return null
    const image = await preloadCanvasImage(url)
    if (!image) return null
    // A cross-origin image without CORS cannot be exported from canvas. The
    // panel falls back to drawing the original URL directly instead of white.
    if (!image.safe) return image.url
    const canvas = document.createElement('canvas')
    canvas.width = SIZE
    canvas.height = SIZE
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    checkerboard(ctx)
    const fit = Math.min((SIZE - 8) / Math.max(1, layer.width), (SIZE - 8) / Math.max(1, layer.height))
    const relative = Math.min(1.25, Math.max(0.35, Math.sqrt(Math.abs(layer.transform.scale_x))))
    const width = Math.max(1, layer.width * fit * relative)
    const height = Math.max(1, layer.height * fit * relative)
    ctx.save()
    ctx.translate(SIZE / 2, SIZE / 2)
    ctx.rotate((layer.transform.rotation * Math.PI) / 180)
    ctx.globalAlpha = Math.max(0, Math.min(1, layer.opacity))
    ctx.drawImage(image.element, -width / 2, -height / 2, width, height)
    ctx.restore()
    try {
      return canvas.toDataURL('image/png')
    } catch {
      return image.url
    }
  }

  const canvas = document.createElement('canvas')
  canvas.width = SIZE
  canvas.height = SIZE
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  checkerboard(ctx)
  ctx.save()
  ctx.translate(SIZE / 2, SIZE / 2)
  ctx.rotate((layer.transform.rotation * Math.PI) / 180)
  ctx.globalAlpha = Math.max(0, Math.min(1, layer.opacity))

  if (layer.kind === 'text') {
    const text = (layer.text || '').trim()
    ctx.fillStyle = layer.fill || '#141414'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.font = '600 13px ui-sans-serif, system-ui, sans-serif'
    ctx.fillText(text ? text.slice(0, 8) : '空', 0, 0, SIZE - 8)
  } else {
    const width = Math.min(36, SIZE - 10)
    const height = Math.min(30, SIZE - 12)
    ctx.fillStyle = layer.fill || '#f2c94c'
    ctx.strokeStyle = layer.stroke || '#141414'
    ctx.lineWidth = Math.max(1, Math.min(3, layer.stroke_width ?? 2))
    if (layer.shape_type === 'ellipse') {
      ctx.beginPath()
      ctx.ellipse(0, 0, width / 2, height / 2, 0, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
    } else if (layer.shape_type === 'line') {
      ctx.beginPath()
      ctx.moveTo(-width / 2, height / 2)
      ctx.lineTo(width / 2, -height / 2)
      ctx.stroke()
    } else {
      ctx.fillRect(-width / 2, -height / 2, width, height)
      ctx.strokeRect(-width / 2, -height / 2, width, height)
    }
  }
  ctx.restore()
  return canvas.toDataURL('image/png')
}

/** Debounced, bounded thumbnail worker for every visible or hidden layer. */
export function useLayerThumbnails(layers: Layer[], urls: Map<string, string>) {
  const [thumbs, setThumbs] = useState<Record<string, string>>({})
  const timer = useRef<number | undefined>(undefined)
  const stamp = useMemo(
    () => layers.map((layer) => `${layer.id}:${thumbKey(layer)}:${layer.asset_id ?? ''}`).join('|'),
    [layers],
  )

  useEffect(() => {
    const currentIds = new Set(layers.map((layer) => layer.id))
    setThumbs((current) => {
      const next: Record<string, string> = {}
      for (const [id, value] of Object.entries(current)) {
        if (currentIds.has(id)) next[id] = value
      }
      return next
    })

    const pending = layers.filter((layer) => {
      const key = thumbKey(layer)
      const hit = cache.get(key)
      if (hit) {
        setThumbs((current) => (current[layer.id] === hit ? current : { ...current, [layer.id]: hit }))
        return false
      }
      // 素材地址还没到就先等着，别把「暂时没有 URL」记成永久失败。
      if (layer.kind === 'image' && layer.asset_id && !urls.get(layer.asset_id)) return false
      return !failed.has(key)
    })
    if (pending.length === 0) return

    timer.current = window.setTimeout(() => {
      frame = requestAnimationFrame(() => {
        void Promise.all(
          pending.map(async (layer) => {
            const key = thumbKey(layer)
            try {
              const result = await renderLayer(layer, layer.asset_id ? urls.get(layer.asset_id) : undefined)
              if (!result) {
                failed.add(key)
                return null
              }
              remember(key, result)
              return [layer.id, result] as const
            } catch (error) {
              failed.add(key)
              if (import.meta.env.DEV) console.warn('layer thumbnail failed', layer.id, error)
              return null
            }
          }),
        ).then((results) => {
          const found = results.filter((item): item is readonly [string, string] => Boolean(item))
          if (found.length) setThumbs((current) => ({ ...current, ...Object.fromEntries(found) }))
        })
      })
    }, 120)

    return () => {
      if (timer.current !== undefined) window.clearTimeout(timer.current)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [stamp, layers, urls])

  return thumbs
}
