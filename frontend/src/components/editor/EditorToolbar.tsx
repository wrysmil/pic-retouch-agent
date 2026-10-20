import { useState } from 'react'
import { Link } from 'react-router-dom'

import type { SessionDetail } from '@/api/sessions'
import SessionSwitcher from '@/components/editor/SessionSidebar'
import Button from '@/components/ui/Button'
import Icon from '@/components/ui/Icon'
import { buttonClass } from '@/components/ui/buttonStyles'
import type { SessionSelection } from '@/hooks/useSelection'
import type { SessionTools } from '@/hooks/useSessions'
import { useEditorUi } from '@/stores/editorUi'

/** 编辑室顶栏：只放项目、版本、撤销重做、对比和交付，工具留在左侧轨道。 */
export default function EditorToolbar({
  session,
  tools,
  picking,
  onRename,
}: {
  session: SessionDetail
  tools: SessionTools
  picking: SessionSelection
  onRename: (title: string) => void
}) {
  const ui = useEditorUi()
  const canUndo = picking.canUndo || session.can_undo
  const canRedo = picking.canRedo || session.can_redo

  return (
    <header className="border-shell-line bg-shell on-dark flex shrink-0 flex-col gap-2 border-b px-3 py-2 lg:h-14 lg:flex-row lg:items-center lg:gap-2 lg:py-0">
      <div className="flex min-w-0 items-center gap-1.5">
        <Link
          to="/create"
          aria-label="返回项目台"
          className={`${buttonClass({ variant: 'icon', tone: 'dark', size: 'sm' })} lg:hidden`}
        >
          <Icon name="arrow-left" size={17} />
        </Link>
        <TitleField value={session.title} onCommit={onRename} />
        <span className="num hidden shrink-0 text-[10px] text-shell-muted sm:block">
          {session.document.width} × {session.document.height}
          <span className="mx-1.5 text-shell-line">/</span>
          修订 {session.revision}
        </span>
      </div>

      <div className="flex min-w-0 flex-wrap items-center gap-1.5 lg:ml-auto lg:flex-nowrap">
        <Button
          variant="icon"
          size="sm"
          tone="dark"
          disabled={tools.busy || picking.busy || !canUndo}
          title={picking.canUndo ? '撤销选区 ⌘Z' : canUndo ? '撤销上一步 ⌘Z' : '没有可撤销的操作'}
          onClick={() => (picking.canUndo ? picking.undo() : tools.undo())}
        >
          <Icon name="undo" size={16} />
        </Button>
        <Button
          variant="icon"
          size="sm"
          tone="dark"
          disabled={tools.busy || picking.busy || !canRedo}
          title={picking.canRedo ? '重做选区 ⌘⇧Z' : canRedo ? '重做 ⌘⇧Z' : '没有可重做的操作'}
          onClick={() => (picking.canRedo ? picking.redo() : tools.redo())}
        >
          <Icon name="redo" size={16} />
        </Button>
        <span className="bg-shell-line mx-0.5 h-5 w-px" aria-hidden />
        <Button
          size="sm"
          tone="dark"
          active={ui.compareOpen}
          disabled={!session.previous_document}
          title={session.previous_document ? '与上一版对比' : '还没有上一版'}
          onClick={() => ui.setCompareOpen(!ui.compareOpen)}
          className="gap-1.5"
        >
          <Icon name="compare" size={14} />
          <span className="hidden sm:inline">对比</span>
        </Button>
        <SessionSwitcher activeId={session.id} />
        <Button
          variant="icon"
          size="sm"
          tone="dark"
          title="打开右侧面板"
          onClick={() => {
            ui.setPanel(ui.panel ?? 'director')
            ui.setInspectorOpen(true)
          }}
          className="lg:hidden"
        >
          <Icon name="panel" size={16} />
        </Button>

        <Link
          to={`/marketing/${session.id}`}
          title="检查渠道尺寸并导出"
          className={`${buttonClass({ variant: 'signal', size: 'md', tone: 'dark' })} ml-auto inline-flex shrink-0 items-center gap-1.5 lg:ml-1`}
        >
          <Icon name="delivery" size={14} />
          <span className="hidden sm:inline">准备交付</span>
          <span className="sm:hidden">交付</span>
        </Link>
      </div>
    </header>
  )
}

function TitleField({ value, onCommit }: { value: string; onCommit: (title: string) => void }) {
  const [draft, setDraft] = useState<string | null>(null)

  const commit = () => {
    const next = draft?.trim()
    setDraft(null)
    if (next && next !== value) onCommit(next)
  }

  return (
    <input
      value={draft ?? value}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === 'Enter') event.currentTarget.blur()
        if (event.key === 'Escape') setDraft(null)
      }}
      aria-label="会话标题"
      className="text-shell-ink hover:bg-shell-3 focus:bg-shell-3 rounded-control min-w-0 max-w-48 flex-1 px-2 py-1.5 text-[13px] font-medium transition-colors outline-none sm:max-w-56 lg:w-48 lg:flex-none"
    />
  )
}
