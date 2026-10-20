import { Link, NavLink } from 'react-router-dom'

import Icon from '@/components/ui/Icon'
import { useSessions } from '@/hooks/useSessions'
import { formatDateTime } from '@/lib/format'

/** 编辑室的历史会话入口：顶栏轻量菜单，不再常驻一整列。 */
export default function SessionSwitcher({ activeId }: { activeId: string }) {
  const { data: sessions = [], isPending } = useSessions()

  return (
    <details className="group relative">
      <summary className="border-shell-line text-shell-muted hover:bg-shell-3 hover:text-shell-ink flex min-h-9 cursor-pointer list-none items-center gap-1.5 rounded-control border px-2.5 text-[11px] transition-colors [&::-webkit-details-marker]:hidden">
        <Icon name="history" size={15} />
        <span className="hidden sm:inline">历史</span>
        <Icon name="chevron-down" size={12} className="transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-shell-line bg-shell-2 shadow-float absolute right-0 z-50 mt-2 w-64 overflow-hidden rounded-card border">
        <div className="border-shell-line flex items-center justify-between gap-2 border-b px-3 py-2">
          <span className="text-shell-ink text-[11px] font-medium">最近会话</span>
          <span className="num text-[10px] text-shell-muted">{sessions.length}</span>
        </div>
        {isPending ? (
          <p className="px-3 py-3 text-[11px] text-shell-muted">加载中…</p>
        ) : sessions.length === 0 ? (
          <p className="px-3 py-3 text-[11px] leading-relaxed text-shell-muted">
            还没有编辑会话，先在项目台创建。
          </p>
        ) : (
          <ul className="scrollbar-dark max-h-72 overflow-y-auto p-1.5">
            {sessions.slice(0, 12).map((session) => (
              <li key={session.id}>
                <NavLink
                  to={`/editor/${session.id}`}
                  className={({ isActive }) =>
                    `block rounded-control px-2.5 py-2 transition-colors duration-150 ${
                      isActive || session.id === activeId
                        ? 'bg-shell-3 text-shell-ink'
                        : 'text-shell-muted hover:bg-shell-3/70 hover:text-shell-ink'
                    }`
                  }
                >
                  <span className="block truncate text-[11px] font-medium">{session.title}</span>
                  <span className="num mt-0.5 block text-[10px] text-shell-muted">
                    {formatDateTime(session.updated_at)} · 修订 {session.revision}
                  </span>
                </NavLink>
              </li>
            ))}
          </ul>
        )}
        <Link
          to="/create"
          className="border-shell-line text-shell-ink hover:bg-shell-3 flex min-h-9 items-center gap-1.5 border-t px-3 text-[11px] transition-colors"
        >
          <Icon name="plus" size={13} />
          新建项目
        </Link>
      </div>
    </details>
  )
}
