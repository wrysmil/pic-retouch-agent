import { Link } from 'react-router-dom'

import { useAdminUsers } from '@/api/adminUsers'
import { useConnections, useModels, useRuntime, useRuntimeVersions } from '@/api/adminConfig'
import { useCurrentUser } from '@/hooks/useAuth'
import {
  Alert,
  Button,
  DataTable,
  EmptyState,
  KeyValue,
  Loading,
  Panel,
  StatCard,
  Tag,
  cellCls,
  rowCls,
} from '@/components/admin/ui'

/** 后台控制台首页：关键指标条 + 运行版本概览 + 快捷操作 + 最近发布。 */
export default function AdminOverviewPage() {
  const { user } = useCurrentUser()
  const allUsers = useAdminUsers({ limit: 1 })
  const admins = useAdminUsers({ role: 'admin', limit: 1 })
  const activeUsers = useAdminUsers({ is_active: true, limit: 1 })
  const connections = useConnections()
  const models = useModels()
  const runtime = useRuntime()
  const versions = useRuntimeVersions()

  const recent = (versions.data ?? []).slice(0, 6)
  const activeModels = (models.data ?? []).filter((m) => m.status === 'active')
  const nameOf = (id: string) =>
    id && id !== '00000000-0000-0000-0000-000000000000'
      ? (models.data ?? []).find((m) => m.id === id)?.display_name ?? '（未知模型）'
      : '—'

  return (
    <div className="space-y-3">
      <Alert tone="info">
        你好，<strong>{user?.username ?? '管理员'}</strong>。这里用于管理平台用户与模型运行时配置，所有发布操作即时对工作台生效。
      </Alert>

      {/* 关键指标 */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
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
          sub="拥有后台全部权限"
          tone="success"
          icon="M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6l8-4z"
        />
        <StatCard
          label="当前生效版本"
          value={runtime.data?.current_version_seq != null ? `v${runtime.data.current_version_seq}` : '未发布'}
          sub={
            runtime.data?.published_at
              ? `发布于 ${new Date(runtime.data.published_at).toLocaleString('zh-CN')}`
              : '尚未发布运行配置'
          }
          tone="warn"
          icon="M12 2l8 4.5v9L12 20l-8-4.5v-9L12 2z"
        />
        <StatCard
          label="厂商连接"
          value={connections.data?.length ?? '—'}
          sub={`模型 ${activeModels.length} 个可用 / 共 ${models.data?.length ?? 0} 个`}
          tone="neutral"
          icon="M4 12h4m8 0h4M9 8h6v8H9z"
        />
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        {/* 运行版本概览 */}
        <Panel
          className="xl:col-span-2"
          title="当前运行配置"
          desc="任务提交时锁定该版本，热更新不影响进行中的任务"
          action={
            <Link to="/models">
              <Button variant="primary" size="sm">
                管理模型配置
              </Button>
            </Link>
          }
          bodyClass="p-0"
        >
          {runtime.isLoading ? (
            <Loading />
          ) : (
            <KeyValue
              columns={3}
              items={[
                { label: '生效版本', value: runtime.data?.current_version_seq != null ? `v${runtime.data.current_version_seq}` : '未发布' },
                { label: '发布时间', value: runtime.data?.published_at ? new Date(runtime.data.published_at).toLocaleString('zh-CN') : '—' },
                { label: '乐观锁版本', value: runtime.data?.revision != null ? `revision ${runtime.data.revision}` : '—' },
                { label: '文本模型', value: nameOf(runtime.data?.text_model_id ?? '') },
                { label: '生图模型', value: nameOf(runtime.data?.image_model_id ?? '') },
                { label: '变更说明', value: runtime.data?.note || '（无）' },
              ]}
            />
          )}
        </Panel>

        {/* 快捷操作 */}
        <Panel title="快捷操作" desc="常用管理入口">
          <div className="space-y-1.5">
            <QuickLink to="/users" label="用户管理" desc="创建账号、调整角色、启停与重置密码" />
            <QuickLink to="/models" label="模型配置" desc="维护厂商连接、模型与运行版本发布" />
          </div>
        </Panel>
      </div>

      {/* 最近发布 */}
      <Panel
        title="最近发布"
        desc="运行配置版本历史"
        bodyClass="p-3"
        action={
          <Link to="/models">
            <Button variant="default" size="sm">
              查看全部
            </Button>
          </Link>
        }
      >
        {versions.isLoading ? (
          <Loading />
        ) : recent.length === 0 ? (
          <EmptyState text="尚无发布记录" hint="在「模型配置 → 运行版本」中发布第一个运行配置" />
        ) : (
          <DataTable
            head={['版本', '变更说明', '发布时间', '来源', '状态']}
            align={['left', 'left', 'left', 'left', 'left']}
            minWidth={560}
            footer={<span>显示最近 {recent.length} 条</span>}
          >
            {recent.map((v) => (
              <tr key={v.id} className={rowCls}>
                <td className={cellCls}>
                  <Tag tone="brand" mono>
                    v{v.version_seq}
                  </Tag>
                </td>
                <td className={`${cellCls} text-ad-ink`}>{v.note || '（无备注）'}</td>
                <td className={`${cellCls} text-ad-muted font-ad-mono text-xs tabular-nums`}>
                  {new Date(v.published_at).toLocaleString('zh-CN')}
                </td>
                <td className={`${cellCls} text-ad-muted text-xs`}>
                  {v.rolled_back_from != null ? `回滚自 v${v.rolled_back_from}` : '正常发布'}
                </td>
                <td className={cellCls}>
                  {runtime.data?.current_version_seq === v.version_seq ? (
                    <Tag tone="success">当前生效</Tag>
                  ) : (
                    <Tag tone="neutral">历史</Tag>
                  )}
                </td>
              </tr>
            ))}
          </DataTable>
        )}
      </Panel>
    </div>
  )
}

function QuickLink({ to, label, desc }: { to: string; label: string; desc: string }) {
  return (
    <Link
      to={to}
      className="border-ad-border hover:border-ad-primary hover:bg-ad-surface-2 flex cursor-pointer items-center justify-between gap-3 border px-3 py-2 transition-colors"
    >
      <span className="min-w-0">
        <span className="text-ad-ink block text-[13px] font-medium">{label}</span>
        <span className="text-ad-faint block truncate text-[11px]">{desc}</span>
      </span>
      <svg viewBox="0 0 24 24" fill="none" className="text-ad-faint size-3.5 shrink-0" aria-hidden>
        <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </Link>
  )
}
