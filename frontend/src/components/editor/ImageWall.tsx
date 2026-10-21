import { useState } from 'react'
import type { Asset, AssetKind } from '@/api/assets'
import ChatIcon from '@/components/editor/ChatIcon'

const KIND_LABELS: Record<AssetKind, string> = {
  original: '原图',
  generated: '生成',
  subject: '主体',
  background: '背景',
  mask: '遮罩',
  marketing: '营销',
  export: '导出',
}

/** 会话内全部图片，含未采用的候选。遮罩与拆层中间产物由图层面板承载，不上墙。 */
export default function ImageWall({
  assets,
  currentId,
  disabled,
  onPick,
}: {
  assets: Asset[]
  currentId: string
  disabled: boolean
  onPick: (assetId: string) => void
}) {
  return (
    <div className="image-wall border-line shrink-0 border-t">
      <div className="image-wall-heading">
        <span>创作素材</span>
        <small>原图与结果，随时切换</small>
      </div>
      <div className="scrollbar-slim flex scroll-px-4 items-center gap-2 overflow-x-auto px-4 py-3">
        {assets
          .filter((asset) => asset.kind !== 'mask')
          .filter(
            (asset) =>
              asset.id === currentId || (asset.kind !== 'subject' && asset.kind !== 'background'),
          )
          .map((asset) => {
            const active = asset.id === currentId
            return (
              <button
                key={asset.id}
                type="button"
                disabled={disabled || active}
                onClick={() => onPick(asset.id)}
                title={
                  active
                    ? `当前画布 · ${KIND_LABELS[asset.kind]}`
                    : `采用这张 · ${KIND_LABELS[asset.kind]} ${asset.width}×${asset.height}`
                }
                aria-pressed={active}
                className={`image-wall-card ${active ? 'active' : ''}`}
              >
                <AssetThumbnail asset={asset} />
                <span>
                  <strong>
                    {KIND_LABELS[asset.kind]}
                    {active ? ' · 当前' : ''}
                  </strong>
                  <small>
                    {asset.width} × {asset.height}
                  </small>
                </span>
              </button>
            )
          })}
      </div>
    </div>
  )
}

function AssetThumbnail({ asset }: { asset: Asset }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  if (failedUrl === asset.url) {
    return (
      <span className="image-wall-thumb-error" role="img" aria-label="图片加载失败">
        <ChatIcon name="alert" />
      </span>
    )
  }
  return <img src={asset.url} alt="" loading="lazy" onError={() => setFailedUrl(asset.url)} />
}
