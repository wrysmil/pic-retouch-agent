import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import BrandMark from '@/components/BrandMark'
import ToastHost from '@/components/ToastHost'
import Icon, { type IconName } from '@/components/ui/Icon'
import { useAuthActions, useCurrentUser } from '@/hooks/useAuth'
import { useSessions } from '@/hooks/useSessions'

type NavItem = {
  to: string
  label: string
  short: string
  icon: IconName
  end?: boolean
}

const PRIMARY: NavItem[] = [
  { to: '/create', label: '项目台', short: '项目', icon: 'projects', end: true },
  { to: '/editor', label: '编辑室', short: '编辑', icon: 'editor' },
  { to: '/marketing', label: '交付中心', short: '交付', icon: 'delivery' },
  { to: '/library', label: '素材库', short: '素材', icon: 'library' },
]

const PRODUCTION: NavItem = { to: '/batch', label: '批量任务', short: '批量', icon: 'batch' }

/** 工作台外壳：深墨工作室导航；编辑会话内收成图标轨道，窄屏改为顶栏 + 底部分段导航。 */
export default function WorkbenchLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useCurrentUser()
  const { logout } = useAuthActions()
  const { data: sessions = [] } = useSessions()

  const signOut = () =>
    logout.mutate(undefined, { onSuccess: () => navigate('/', { replace: true }) })

  // 会话内的编辑室自己占满一屏，移动端不再叠加全局导航，给画布留空间
  const editing = /^\/editor\/[^/]+/.test(location.pathname)
  const rail = editing

  return (
    <div className={`flex h-dvh overflow-hidden ${editing ? 'bg-shell-2' : 'bg-work'}`}>
      <aside
        className={`bg-shell on-dark scrollbar-dark hidden shrink-0 flex-col overflow-y-auto border-r border-shell-line lg:flex ${
          rail ? 'w-[76px] px-3 py-4' : 'w-[208px] px-3 py-5 xl:w-[232px]'
        }`}
        aria-label="工作室导航"
      >
        <NavLink
          to="/create"
          className={`mb-6 flex items-center gap-2.5 rounded-control outline-none ${
            rail ? 'justify-center px-0' : 'px-2'
          }`}
          aria-label="知图工作室 · 项目台"
        >
          <BrandMark size={rail ? 'sm' : 'md'} />
          {!rail && (
            <span className="min-w-0">
              <span className="text-shell-ink block truncate text-[13px] font-semibold tracking-tight">
                知图工作室
              </span>
              <span className="num block truncate text-[9px] tracking-[0.18em] text-shell-muted">
                VISUAL ATELIER
              </span>
            </span>
          )}
        </NavLink>

        {!rail && (
          <p className="px-3 pt-2 pb-2 text-[10px] tracking-[0.16em] text-shell-muted uppercase">
            Workspace
          </p>
        )}
        <ul className="flex flex-col gap-1">
          {PRIMARY.map((item) => (
            <li key={item.to}>
              <SideNavItem item={item} rail={rail} />
            </li>
          ))}
        </ul>

        {rail ? (
          <div className="my-3 border-t border-shell-line" aria-hidden />
        ) : (
          <p className="px-3 pt-5 pb-2 text-[10px] tracking-[0.16em] text-shell-muted uppercase">
            Production
          </p>
        )}
        <ul>
          <li>
            <SideNavItem item={PRODUCTION} rail={rail} secondary />
          </li>
        </ul>

        <div className="mt-auto pt-4">
          {!rail && (
            <div className="mb-3 rounded-card border border-shell-line bg-shell-2 px-3 py-2.5">
              <p className="text-shell-ink text-[11px] font-medium">个人工作空间</p>
              <p className="num mt-0.5 text-[10px] text-shell-muted">
                {sessions.length ? `${sessions.length} 个编辑会话` : '等待第一个项目'}
              </p>
            </div>
          )}
          <div className={`flex items-center gap-2 ${rail ? 'flex-col' : ''}`}>
            <span className="bg-signal text-signal-ink grid size-8 shrink-0 place-items-center rounded-full text-[11px] font-semibold">
              {user?.username.slice(0, 1).toUpperCase() ?? '?'}
            </span>
            {!rail && (
              <span className="min-w-0 flex-1">
                <span className="text-shell-ink block truncate text-[11px] font-medium">
                  {user?.username ?? '未登录'}
                </span>
                <span className="block text-[10px] text-shell-muted">创作者</span>
              </span>
            )}
            <button
              type="button"
              onClick={signOut}
              title="退出登录"
              aria-label="退出登录"
              className="text-shell-muted hover:bg-shell-3 hover:text-shell-ink grid size-9 shrink-0 place-items-center rounded-control transition-colors"
            >
              <Icon name="log-out" size={16} />
            </button>
          </div>
        </div>
      </aside>

      {editing ? (
        <main className="min-h-0 min-w-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      ) : (
        <>
          <div className="flex min-w-0 flex-1 flex-col">
            <MobileHeader
              username={user?.username ?? null}
              signingOut={logout.isPending}
              onSignOut={signOut}
            />
            <main className="min-h-0 flex-1 overflow-auto pb-[calc(64px+env(safe-area-inset-bottom))] lg:pb-0">
              <Outlet />
            </main>
          </div>
          <MobileNav />
        </>
      )}
      <ToastHost />
    </div>
  )
}

function SideNavItem({
  item,
  rail,
  secondary = false,
}: {
  item: NavItem
  rail: boolean
  secondary?: boolean
}) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      title={rail ? item.label : undefined}
      aria-label={item.label}
      className={({ isActive }) =>
        `group relative flex min-h-11 items-center rounded-control text-[13px] transition-colors duration-150 ${
          rail ? 'justify-center px-0' : 'gap-3 px-3'
        } ${
          isActive
            ? 'bg-shell-3 font-medium text-shell-ink'
            : secondary
              ? 'text-shell-muted hover:bg-shell-2 hover:text-shell-ink'
              : 'text-shell-muted hover:bg-shell-2 hover:text-shell-ink'
        }`
      }
    >
      {({ isActive }) => (
        <>
          <Icon name={item.icon} size={secondary ? 16 : 18} className="shrink-0" />
          {!rail && <span className="truncate">{item.label}</span>}
          {isActive && (
            <span
              className={`bg-signal absolute rounded-full ${
                rail ? 'top-1.5 right-1.5 size-1.5' : 'right-2.5 size-1.5'
              }`}
              aria-hidden
            />
          )}
        </>
      )}
    </NavLink>
  )
}

function MobileHeader({
  username,
  signingOut,
  onSignOut,
}: {
  username: string | null
  signingOut: boolean
  onSignOut: () => void
}) {
  return (
    <header className="bg-work/95 sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between border-b border-line/70 px-4 backdrop-blur lg:hidden">
      <div className="flex min-w-0 items-center gap-2.5">
        <BrandMark size="sm" />
        <span className="min-w-0">
          <span className="text-ink block truncate text-[13px] font-semibold tracking-tight">
            知图工作室
          </span>
          <span className="block text-[9px] tracking-[0.16em] text-faint">VISUAL ATELIER</span>
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted hidden max-w-24 truncate text-xs sm:block">{username}</span>
        <button
          type="button"
          onClick={onSignOut}
          disabled={signingOut}
          aria-label="退出登录"
          title="退出登录"
          className="text-muted hover:bg-soft hover:text-ink grid size-9 place-items-center rounded-control transition-colors disabled:opacity-40"
        >
          <Icon name="log-out" size={17} />
        </button>
      </div>
    </header>
  )
}

function MobileNav() {
  return (
    <nav
      className="bg-shell on-dark fixed inset-x-0 bottom-0 z-30 border-t border-shell-line pb-[env(safe-area-inset-bottom)] lg:hidden"
      aria-label="工作室导航"
    >
      <ul className="grid grid-cols-4">
        {PRIMARY.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `relative flex min-h-14 flex-col items-center justify-center gap-1 text-[10px] transition-colors duration-150 ${
                  isActive ? 'text-signal' : 'text-shell-muted active:text-shell-ink'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon name={item.icon} size={19} />
                  <span>{item.short}</span>
                  {isActive && (
                    <span className="bg-signal absolute top-0 h-0.5 w-6 rounded-full" aria-hidden />
                  )}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
