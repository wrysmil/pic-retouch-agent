import type { Asset } from '@/api/assets'
import { formatBytes, formatDateTime } from '@/lib/format'

export default function AssetCard({ asset, onSelect }: { asset: Asset; onSelect?: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      title="点击打开编辑"
      className="group border-line bg-panel hover:border-ai-strong/70 overflow-hidden rounded-card border text-left transition-colors"
    >
      <div className="bg-panel-2 relative aspect-square">
        <img
          src={asset.url}
          alt=""
          loading="lazy"
          className="size-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
        />
        {asset.has_alpha && (
          <span className="bg-shell/75 absolute top-2 left-2 rounded-full px-1.5 py-0.5 text-[10px] text-white">
            透明底
          </span>
        )}
      </div>

      <dl className="px-3 py-2.5 text-[11px]">
        <div className="text-ink num font-medium">
          {asset.width} × {asset.height}
        </div>
        <div className="text-muted num mt-0.5">
          {asset.image_format.toUpperCase()} · {formatBytes(asset.size_bytes)}
        </div>
        <div className="text-faint num mt-0.5">{formatDateTime(asset.created_at)}</div>
      </dl>
    </button>
  )
}
