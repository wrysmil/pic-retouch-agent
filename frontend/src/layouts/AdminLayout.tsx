import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useAdminAuthActions, useCurrentAdmin } from '@/hooks/useAdminAuth'
import { Button } from '@/components/admin/ui'
import { WORKBENCH_URL } from '@/admin/config'

const NAV = [
  {
    group: '总览',
    items: [
      {
        to: '/',
        label: '控制台',
        icon: 'M4 13h6V4H4v9zm10 7h6v-9h-6v9zM4 20h6v-4H4v4zm10-11h6V4h-6v5z',
      },
    ],
  },
  {
    group: '系统管理',
    items: [
      {
        to: '/users',
        label: '用户管理',
        icon: 'M16 19v-1a4 4 0 00-8 0v1M12 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7z',
      },
      {
        to: '/quota',
        label: '会员权益',
        icon: 'M12 3l7 3v5c0 4.3-2.9 7.9-7 9-4.1-1.1-7-4.7-7-9V6l7-3zm0 5v5m0 3h.01',
      },
      {
        to: '/models',
        label: '模型配置',
        icon: 'M12 2l8 4.5v9L12 20l-8-4.5v-9L12 2zm0 4.5L8 9l4 2.3L16 9l-4-2.5z',
      },
    ],
  },
] as const

/** 由路由反推面包屑与页面标题，避免每页各写一份 */
function useMeta(pathname: string) {
  const flat = NAV.flatMap((s) => s.items.map((i) => ({ ...i, group: s.group })))
  // '/' 是前缀，必须先判掉，否则会吃掉所有子路由
  const hit =
    flat.find((i) => i.to === '/') ?? [...flat].sort((a, b) => b.to.length - a.to.length).find((i) => pathname.startsWith(i.to))
  return hit
    ? { title: hit.label, crumbs: [hit.group, hit.label] as string[] }
    : { title: '后台管理', crumbs: ['后台管理'] as string[] }
}

function NavIcon({ path, className = 'size-4' }: { path: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={`shrink-0 ${className}`} aria-hidden>
      <path
        d={path}
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/** 后台控制台外壳：顶部品牌条 + 直角深色侧栏（左侧色条选中态）+ 面包屑页头。 */
export default function AdminLayout() {
  const { user } = useCurrentAdmin()
  const { logout } = useAdminAuthActions()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const meta = useMeta(pathname)

  // 工作台是另一个端口的应用，只能整页跳，不能走前端路由
  const goWorkbench = () => window.location.assign(WORKBENCH_URL)

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    window.addEventListener('mousedown', onClick)
    return () => window.removeEventListener('mousedown', onClick)
  }, [])

  const signOut = () => {
    logout.mutate(undefined, {
      onSuccess: () => navigate('/login', { replace: true }),
    })
  }

  return (
    <div className="ad-root bg-ad-canvas flex h-screen flex-col overflow-hidden">
      {/* 顶部品牌条 */}
      <header className="bg-ad-sidebar flex h-12 shrink-0 items-stretch border-b border-ad-sidebar-line">
        <div className="flex w-52 shrink-0 items-center gap-2 border-r border-ad-sidebar-line px-3">
          <span className="bg-ad-primary grid size-7 shrink-0 place-items-center text-[13px] font-bold text-white">
            AI
          </span>
          <div className="min-w-0 leading-tight">
            <div className="truncate text-[13px] font-semibold text-white">图片智能体</div>
            <div className="text-ad-sidebar-faint truncate text-[10px] tracking-wider uppercase">
              Admin Console
            </div>
          </div>
        </div>

        <div className="flex min-w-0 flex-1 items-center justify-between px-4">
          <span className="text-ad-sidebar-faint truncate text-[12px]">
            运营管理后台 · 用户与模型运行时配置
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="text-ad-sidebar-ink hover:bg-ad-sidebar-2 hover:text-white"
            onClick={goWorkbench}
          >
            <NavIcon path="M15 18l-6-6 6-6" />
            返回工作台
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* 侧边栏 */}
        <aside className="bg-ad-sidebar flex w-52 shrink-0 flex-col border-r border-ad-sidebar-line">
          <nav className="scrollbar-slim flex-1 overflow-y-auto py-2">
            {NAV.map((section) => (
              <div key={section.group} className="mb-4 last:mb-0">
                <div className="text-ad-sidebar-faint px-3 pb-1 text-[10px] font-medium tracking-[0.12em] uppercase">
                  {section.group}
                </div>
                <ul>
                  {section.items.map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        end={item.to === '/'}
                        className={({ isActive }) =>
                          `flex h-8 cursor-pointer items-center gap-2.5 border-l-2 pr-3 pl-2.5 text-[13px] transition-colors ${
                            isActive
                              ? 'border-ad-primary bg-ad-sidebar-2 font-medium text-white'
                              : 'border-transparent text-ad-sidebar-ink hover:bg-ad-sidebar-2 hover:text-white'
                          }`
                        }
                      >
                        <NavIcon path={item.icon} />
                        {item.label}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>

          <div className="border-ad-sidebar-line text-ad-sidebar-faint border-t px-3 py-2 text-[10px] leading-4">
            环境：生产
            <br />
            版本：2.0 · 企业控制台
          </div>
        </aside>

        {/* 主区 */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* 面包屑页头 */}
          <div className="bg-ad-surface border-ad-border flex h-10 shrink-0 items-center justify-between gap-4 border-b px-4">
            <div className="flex min-w-0 items-center gap-1.5 text-[13px]">
              {meta.crumbs.map((c, i) => (
                <span key={c} className="flex min-w-0 items-center gap-1.5">
                  {i > 0 ? (
                    <span className="text-ad-border-strong text-[10px]" aria-hidden>
                      /
                    </span>
                  ) : null}
                  <span className={i === meta.crumbs.length - 1 ? 'text-ad-ink font-semibold' : 'text-ad-faint'}>
                    {c}
                  </span>
                </span>
              ))}
            </div>

            <div className="relative shrink-0" ref={menuRef}>
              <button
                type="button"
                onClick={() => setMenuOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                className="border-ad-border hover:bg-ad-surface-2 flex h-8 cursor-pointer items-center gap-2 border px-2 transition-colors"
              >
                <span className="bg-ad-primary-soft text-ad-primary-dark grid size-5 shrink-0 place-items-center text-[11px] font-semibold">
                  {(user?.username ?? '?').slice(0, 1).toUpperCase()}
                </span>
                <span className="text-ad-ink text-[13px]">{user?.username}</span>
                <span className="bg-ad-success-soft text-ad-success ml-1 border border-ad-success/30 px-1 py-px text-[10px]">
                  管理员
                </span>
                <NavIcon path="M6 9l6 6 6-6" className="text-ad-faint size-3" />
              </button>

              {menuOpen ? (
                <div
                  role="menu"
                  className="bg-ad-surface border-ad-border-strong animate-pop absolute right-0 z-40 mt-1 w-44 border shadow-ad-pop"
                >
                  <button
                    type="button"
                    role="menuitem"
                    onClick={goWorkbench}
                    className="text-ad-muted hover:bg-ad-surface-2 hover:text-ad-ink block w-full cursor-pointer px-3 py-1.5 text-left text-[13px] transition-colors"
                  >
                    返回工作台
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={signOut}
                    className="text-ad-danger hover:bg-ad-danger-soft block w-full cursor-pointer border-t border-ad-border px-3 py-1.5 text-left text-[13px] transition-colors"
                  >
                    退出登录
                  </button>
                </div>
              ) : null}
            </div>
          </div>

          <main className="scrollbar-slim min-w-0 flex-1 overflow-auto p-3">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
