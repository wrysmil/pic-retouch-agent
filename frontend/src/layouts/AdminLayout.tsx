import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useCurrentUser } from '@/hooks/useAuth'
import { useSignOutAndGoHome } from '@/api/adminUsers'

const NAV = [
  {
    group: '总览',
    items: [
      {
        to: '/admin',
        label: '控制台',
        end: true,
        icon: 'M4 13h6V4H4v9zm10 7h6v-9h-6v9zM4 20h6v-4H4v4zm10-11h6V4h-6v5z',
      },
    ],
  },
  {
    group: '管理',
    items: [
      {
        to: '/admin/users',
        label: '用户管理',
        icon: 'M16 19v-1a4 4 0 00-8 0v1M12 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7z',
      },
      {
        to: '/admin/models',
        label: '模型配置',
        icon: 'M12 2l8 4.5v9L12 20l-8-4.5v-9L12 2zm0 4.5L8 9l4 2.3L16 9l-4-2.5z',
      },
    ],
  },
]

const TITLES: Record<string, { title: string; crumb: string }> = {
  '/admin': { title: '控制台', crumb: '总览 / 控制台' },
  '/admin/users': { title: '用户管理', crumb: '管理 / 用户管理' },
  '/admin/models': { title: '模型配置', crumb: '管理 / 模型配置' },
}

function NavIcon({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="size-[18px] shrink-0" aria-hidden>
      <path
        d={path}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/** 后台控制台外壳：深蓝侧边栏（分组导航）+ 顶部面包屑/标题栏 + 管理员菜单。 */
export default function AdminLayout() {
  const { user } = useCurrentUser()
  const signOut = useSignOutAndGoHome()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    window.addEventListener('mousedown', onClick)
    return () => window.removeEventListener('mousedown', onClick)
  }, [])

  const meta = TITLES[pathname] ?? { title: '后台管理', crumb: '后台管理' }

  return (
    <div className="bg-ad-canvas flex h-screen overflow-hidden">
      {/* 侧边栏 */}
      <aside className="bg-ad-sidebar flex w-60 shrink-0 flex-col">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <span className="bg-ad-primary text-white grid size-8 place-items-center rounded-ad-sm text-sm font-bold">
            A
          </span>
          <div className="leading-tight">
            <div className="text-white text-sm font-semibold">后台管理</div>
            <div className="text-ad-sidebar-faint text-[11px]">AI 修图智能体</div>
          </div>
        </div>

        <nav className="scrollbar-slim flex-1 overflow-y-auto px-3 py-2">
          {NAV.map((section) => (
            <div key={section.group} className="mb-5">
              <div className="text-ad-sidebar-faint px-3 pb-1.5 text-[11px] font-medium tracking-wider">
                {section.group}
              </div>
              <ul className="flex flex-col gap-0.5">
                {section.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.end}
                      className={({ isActive }) =>
                        `flex cursor-pointer items-center gap-3 rounded-ad-sm px-3 py-2 text-sm transition-colors ${
                          isActive
                            ? 'bg-ad-primary text-white font-medium'
                            : 'text-ad-sidebar-ink hover:bg-ad-sidebar-2 hover:text-white'
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

        <div className="border-white/10 border-t p-3">
          <button
            type="button"
            onClick={() => navigate('/create')}
            className="text-ad-sidebar-ink hover:bg-ad-sidebar-2 hover:text-white flex w-full cursor-pointer items-center gap-3 rounded-ad-sm px-3 py-2 text-sm transition-colors"
          >
            <NavIcon path="M15 18l-6-6 6-6" />
            返回工作台
          </button>
        </div>
      </aside>

      {/* 主区 */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="bg-ad-surface border-ad-border flex h-16 shrink-0 items-center justify-between border-b px-6">
          <div>
            <h1 className="text-ad-ink text-base font-semibold">{meta.title}</h1>
            <p className="text-ad-faint text-xs">{meta.crumb}</p>
          </div>

          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              className="hover:bg-ad-surface-2 flex cursor-pointer items-center gap-2.5 rounded-ad-sm px-2 py-1.5 transition-colors"
            >
              <span className="bg-ad-primary-soft text-ad-primary-dark grid size-8 place-items-center rounded-full text-sm font-semibold">
                {user?.username.slice(0, 1).toUpperCase() ?? '?'}
              </span>
              <span className="text-left leading-tight">
                <span className="text-ad-ink block text-sm font-medium">{user?.username}</span>
                <span className="text-ad-faint block text-[11px]">管理员</span>
              </span>
              <svg viewBox="0 0 24 24" fill="none" className="text-ad-faint size-4">
                <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </button>

            {menuOpen ? (
              <div className="bg-ad-surface border-ad-border animate-pop absolute right-0 z-40 mt-2 w-44 overflow-hidden rounded-ad-sm border shadow-ad-pop">
                <button
                  type="button"
                  onClick={() => navigate('/create')}
                  className="text-ad-muted hover:bg-ad-surface-2 hover:text-ad-ink block w-full cursor-pointer px-4 py-2.5 text-left text-sm transition-colors"
                >
                  返回工作台
                </button>
                <button
                  type="button"
                  onClick={() => signOut.mutate(undefined)}
                  className="text-ad-danger hover:bg-ad-danger-soft block w-full cursor-pointer border-t border-ad-border px-4 py-2.5 text-left text-sm transition-colors"
                >
                  退出登录
                </button>
              </div>
            ) : null}
          </div>
        </header>

        <main className="min-w-0 flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
