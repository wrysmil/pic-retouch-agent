import { useState } from 'react'

import type { Asset, LibraryGroup } from '@/api/assets'
import Icon from '@/components/ui/Icon'
import { formatDateTime } from '@/lib/format'
import { KIND_LABELS } from '@/lib/marketing'

/** 素材库：一个会话一组的封面卡，展开看组内全部图。 */
export default function AssetLibrary({
  groups,
  onOpenSession,
  onOpenAsset,
}: {
  groups: LibraryGroup[]
  onOpenSession: (sessionId: string) => void
  onOpenAsset: (assetId: string) => void
}) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {groups.map((group) => (
        <LibraryGroupCard
          key={group.session_id ?? 'orphan'}
          group={group}
          onOpenSession={onOpenSession}
          onOpenAsset={onOpenAsset}
        />
      ))}
    </ul>
  )
}

function LibraryGroupCard({
  group,
  onOpenSession,
  onOpenAsset,
}: {
  group: LibraryGroup
  onOpenSession: (sessionId: string) => void
  onOpenAsset: (assetId: string) => void
}) {
  const [open, setOpen] = useState(false)
  const visible = group.assets.filter(
    (asset) => asset.kind !== 'mask' && asset.kind !== 'subject' && asset.kind !== 'background',
  )
  // 已归组的回到原会话继续改，没归组的用封面开一个新会话
  const openGroup = () => {
    if (group.session_id) onOpenSession(group.session_id)
    else onOpenAsset(group.cover.id)
  }

  return (
    <li className="border-line bg-panel overflow-hidden rounded-card border">
      <div className="flex items-stretch">
        <button
          type="button"
          onClick={openGroup}
          className="group flex min-w-0 flex-1 items-center gap-3 p-2.5 text-left"
        >
          <span className="bg-panel-2 border-line relative h-20 w-24 shrink-0 overflow-hidden rounded-control border">
            <img
              src={group.cover.url}
              alt=""
              loading="lazy"
              className="size-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
            />
          </span>
          <span className="min-w-0 flex-1">
            <span className="text-ink block truncate text-[13px] font-medium">{group.title}</span>
            <span className="text-muted num mt-1 block text-[10px]">
              {group.assets.length} 张 · {formatDateTime(group.updated_at)}
            </span>
            <span className="text-ai-strong mt-2 inline-flex items-center gap-1 text-[10px] font-medium">
              {group.session_id ? '继续编辑' : '打开并创建会话'}
              <Icon name="arrow-right" size={11} />
            </span>
          </span>
        </button>
        {visible.length > 1 && (
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-label={open ? '收起组内素材' : '展开组内素材'}
            className="border-line text-muted hover:bg-soft hover:text-ink w-10 shrink-0 border-l text-[10px] transition-colors"
          >
            <Icon name={open ? 'chevron-up' : 'chevron-down'} size={14} className="mx-auto" />
          </button>
        )}
      </div>
      {open && (
        <div className="border-line animate-fade-in grid grid-cols-3 gap-2 border-t p-2.5 sm:grid-cols-4">
          {visible.map((asset) => (
            <AssetTile
              key={asset.id}
              asset={asset}
              onSelect={() =>
                group.session_id ? onOpenSession(group.session_id) : onOpenAsset(asset.id)
              }
            />
          ))}
        </div>
      )}
    </li>
  )
}

function AssetTile({ asset, onSelect }: { asset: Asset; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      title="打开这张素材"
      className="group border-line bg-panel-2 hover:border-ai-strong/70 relative aspect-square overflow-hidden rounded-chip border transition-colors"
    >
      <img
        src={asset.url}
        alt=""
        loading="lazy"
        className="size-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
      />
      <span className="bg-shell/65 absolute inset-x-0 bottom-0 px-1.5 py-1 text-[9px] text-white">
        {KIND_LABELS[asset.kind]}
      </span>
    </button>
  )
}
