import { Link } from 'react-router-dom'

import { useAdminUsers } from '@/api/adminUsers'
import { useConnections, useModels, useRuntime, useRuntimeVersions } from '@/api/adminConfig'
import { useCurrentUser } from '@/hooks/useAuth'
import { Badge, Button, Card, Loading, StatCard } from '@/components/admin/ui'

/** 后台控制台首页：关键指标卡片 + 快捷入口 + 最近发布。 */
export default function AdminOverviewPage() {
  const { user } = useCurrentUser()
  const allUsers = useAdminUsers({ limit: 1 })
  const admins = useAdminUsers({ role: 'admin', limit: 1 })
  const activeUsers = useAdminUsers({ is_active: true, limit: 1 })
  const connections = useConnections()
  const models = useModels()
  const runtime = useRuntime()
  const versions = useRuntimeVersions()

  const recent = (versions.data ?? []).slice(0, 5)

  return (
    <div className="space-y-6">
      <div className="bg-ad-surface border-ad-border flex items-center justify-between rounded-ad border px-6 py-5 shadow-ad-card">
        <div>
          <h2 className="text-ad-ink text-lg font-semibold">你好，{user?.username ?? '管理员'}</h2>
          <p className="text-ad-muted mt-1 text-sm">这里是 AI 修图智能体的运营后台，可管理用户与模型运行配置。</p>
        </div>
        <Link to="/admin/models">
          <Button variant="primary">管理模型配置</Button>
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="注册用户"
          value={allUsers.data?.total ?? '—'}
          sub={`启用 ${activeUsers.data?.total ?? '—'} 人`}
          tone="brand"
          icon="M16 19v-1a4 4 0 00-8 0v1M12 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7z"
        />
        <StatCard
          label="管理员"
          value={admins.data?.total ?? '—'}
          sub="拥有后台权限"
          tone="success"
          icon="M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6l8-4z"
        />
        <StatCard
          label="当前生效版本"
          value={runtime.data?.current_version_seq != null ? `v${runtime.data.current_version_seq}` : '未发布'}
          sub={
            runtime.data?.published_at
              ? new Date(runtime.data.published_at).toLocaleString('zh-CN')
              : '尚未发布运行配置'
          }
          tone="warn"
          icon="M12 2l8 4.5v9L12 20l-8-4.5v-9L12 2z"
        />
        <StatCard
          label="厂商连接"
          value={connections.data?.length ?? '—'}
          sub={`模型 ${(models.data ?? []).filter((m) => m.status === 'active').length} 个可用`}
          tone="neutral"
          icon="M4 12h4m8 0h4M9 8h6v8H9z"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="快捷入口" className="lg:col-span-1">
          <div className="grid gap-3">
            <QuickLink to="/admin/users" label="用户管理" desc="创建账号、调整角色、启停与重置密码" icon="M16 19v-1a4 4 0 00-8 0v1M12 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7z" />
            <QuickLink to="/admin/models" label="模型配置" desc="维护厂商连接、模型与运行版本发布" icon="M12 2l8 4.5v9L12 20l-8-4.5v-9L12 2z" />
          </div>
        </Card>

        <Card
          title="最近发布"
          desc="运行配置版本历史"
          className="lg:col-span-2"
          action={
            <Link to="/admin/models">
              <Button variant="ghost" size="sm">
                查看全部
              </Button>
            </Link>
          }
        >
          {versions.isLoading ? (
            <Loading />
          ) : recent.length === 0 ? (
            <p className="text-ad-faint py-6 text-center text-sm">尚无发布记录</p>
          ) : (
            <ul className="divide-ad-border divide-y">
              {recent.map((v) => (
                <li key={v.id} className="flex items-center justify-between gap-4 py-3">
                  <div className="flex items-center gap-3">
                    <Badge tone={runtime.data?.current_version_seq === v.version_seq ? 'brand' : 'neutral'}>
                      v{v.version_seq}
                    </Badge>
                    <div>
                      <div className="text-ad-ink text-sm">{v.note || '（无备注）'}</div>
                      <div className="text-ad-faint font-ad-mono text-xs">
                        {new Date(v.published_at).toLocaleString('zh-CN')}
                        {v.rolled_back_from != null ? ` · 回滚自 v${v.rolled_back_from}` : ''}
                      </div>
                    </div>
                  </div>
                  {runtime.data?.current_version_seq === v.version_seq ? (
                    <span className="text-ad-primary text-xs font-medium">当前生效</span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}

function QuickLink({ to, label, desc, icon }: { to: string; label: string; desc: string; icon: string }) {
  return (
    <Link
      to={to}
      className="border-ad-border hover:border-ad-primary hover:bg-ad-surface-2 flex cursor-pointer items-center gap-3 rounded-ad-sm border p-3 transition-colors"
    >
      <span className="bg-ad-primary-soft text-ad-primary grid size-9 shrink-0 place-items-center rounded-ad-sm">
        <svg viewBox="0 0 24 24" fill="none" className="size-[18px]">
          <path d={icon} stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span className="min-w-0">
        <span className="text-ad-ink block text-sm font-medium">{label}</span>
        <span className="text-ad-faint block truncate text-xs">{desc}</span>
      </span>
    </Link>
  )
}
