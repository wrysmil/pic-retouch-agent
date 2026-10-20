import type { Asset, AssetKind } from '@/api/assets'
import Icon from '@/components/ui/Icon'
import { formatDateTime } from '@/lib/format'

const KIND_LABELS: Record<AssetKind, string> = {
  original: '原图',
  generated: '生成',
  subject: '主体',
  background: '背景',
  mask: '遮罩',
  marketing: '营销',
  export: '导出',
}

/** 会话内全部图片，含未采用的候选。遮罩与拆层中间产物由图层面板承载，不上胶片带。 */
export default function ImageWall({
  assets,
  currentId,
  updatedAt,
  disabled,
  onPick,
}: {
  assets: Asset[]
  currentId: string
  updatedAt?: string
  disabled: boolean
  onPick: (assetId: string) => void
}) {
  const visible = assets
    .filter((asset) => asset.kind !== 'mask')
    .filter(
      (asset) =>
        asset.id === currentId || (asset.kind !== 'subject' && asset.kind !== 'background'),
    )

  return (
    <div className="border-shell-line bg-shell shrink-0 border-t">
      <div className="flex items-center gap-2 px-3 pt-2">
        <span className="flex items-center gap-1.5 text-[10px] text-shell-muted">
          <Icon name="history" size={12} />
          版本胶片
        </span>
        <span className="num text-[10px] text-shell-muted">{visible.length}</span>
        {updatedAt && (
          <span className="num ml-auto hidden text-[10px] text-shell-muted sm:block">
            更新于 {formatDateTime(updatedAt)}
          </span>
        )}
      </div>
      <div className="scrollbar-dark flex scroll-px-3 items-end gap-2 overflow-x-auto px-3 py-2.5">
        {visible.length === 0 ? (
          <p className="text-[10px] text-shell-muted">暂无版本</p>
        ) : (
          visible.map((asset, index) => {
            const active = asset.id === currentId
            const version = String(index + 1).padStart(2, '0')
            return (
              <button
                key={asset.id}
                type="button"
                disabled={disabled || active}
                onClick={() => onPick(asset.id)}
                aria-pressed={active}
                title={
                  active
                    ? `当前版本 V${version} · ${KIND_LABELS[asset.kind]}`
                    : `切换到 V${version} · ${KIND_LABELS[asset.kind]} ${asset.width}×${asset.height}`
                }
                className={`group relative shrink-0 text-left disabled:cursor-default ${
                  active ? '' : 'opacity-80 hover:opacity-100'
                }`}
              >
                <span
                  className={`bg-shell-2 block size-14 overflow-hidden rounded-chip border transition-colors duration-150 ${
                    active
                      ? 'border-signal ring-1 ring-signal/40'
                      : 'border-shell-line group-hover:border-ai/70'
                  }`}
                >
                  <img src={asset.url} alt="" loading="lazy" className="size-full object-cover" />
                </span>
                <span
                  className={`num mt-1 block text-center text-[9px] ${
                    active ? 'text-signal' : 'text-shell-muted'
                  }`}
                >
                  V{version}
                </span>
                <span className="mt-0.5 block max-w-14 truncate text-center text-[9px] text-shell-muted">
                  {KIND_LABELS[asset.kind]}
                </span>
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}
