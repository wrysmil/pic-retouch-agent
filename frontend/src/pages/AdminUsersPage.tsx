import { useState } from 'react'

import {
  type AdminUser,
  type Role,
  useAdminUsers,
  useCreateAdminUser,
  useResetUserPassword,
  useRevokeUserSessions,
  useUpdateUserActive,
  useUpdateUserRole,
} from '@/api/adminUsers'
import { ApiError } from '@/api/client'
import { errorMessage } from '@/hooks/useAuth'
import { Badge, Button, Card, EmptyState, Field, Loading, Modal, TableShell, inputCls } from '@/components/admin/ui'

type FilterState = { keyword: string; role: '' | Role; is_active: '' | 'true' | 'false' }

function msg(error: unknown) {
  return error instanceof ApiError ? error.message : errorMessage(error)
}

type RowAction =
  | { kind: 'reset'; user: AdminUser }
  | { kind: 'revoke'; user: AdminUser }
  | { kind: 'toggle'; user: AdminUser }

export default function AdminUsersPage() {
  const [filter, setFilter] = useState<FilterState>({ keyword: '', role: '', is_active: '' })
  const [creating, setCreating] = useState(false)
  const [action, setAction] = useState<RowAction | null>(null)
  const [banner, setBanner] = useState('')

  const list = useAdminUsers({
    keyword: filter.keyword || undefined,
    role: filter.role || undefined,
    is_active: filter.is_active === '' ? undefined : filter.is_active === 'true',
    limit: 100,
  })

  const role = useUpdateUserRole()
  const active = useUpdateUserActive()
  const revoke = useRevokeUserSessions()

  const onToggle = () => {
    if (!action || action.kind !== 'toggle') return
    const u = action.user
    active.mutate(
      { id: u.id, is_active: !u.is_active },
      { onSuccess: () => { setAction(null); setBanner(`已${u.is_active ? '停用' : '启用'}用户 ${u.username}`) }, onError: (e) => setBanner(msg(e)) },
    )
  }

  const onRevoke = () => {
    if (!action || action.kind !== 'revoke') return
    revoke.mutate(
      action.user.id,
      { onSuccess: () => { setAction(null); setBanner(`已撤销 ${action.user.username} 的全部会话`) }, onError: (e) => setBanner(msg(e)) },
    )
  }

  return (
    <div className="space-y-5">
      {banner ? (
        <div className="bg-ad-primary-soft text-ad-primary-dark flex items-center justify-between rounded-ad-sm px-4 py-2.5 text-sm">
          <span>{banner}</span>
          <button type="button" onClick={() => setBanner('')} className="cursor-pointer rounded p-0.5 hover:opacity-70" aria-label="关闭提示">
            <svg viewBox="0 0 24 24" fill="none" className="size-4">
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      ) : null}

      <Card
        title="用户管理"
        desc="查看、创建账号，调整角色与启停状态，重置密码或撤销会话"
        action={
          <Button variant="primary" onClick={() => setCreating(true)}>
            <svg viewBox="0 0 24 24" fill="none" className="size-4">
              <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
            新建用户
          </Button>
        }
      >
        {/* 过滤工具栏 */}
        <div className="mb-4 flex flex-wrap gap-3">
          <div className="relative min-w-[200px] flex-1">
            <svg viewBox="0 0 24 24" fill="none" className="text-ad-faint pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2">
              <path d="M11 19a8 8 0 100-16 8 8 0 000 16zm10 2l-4.35-4.35" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
            <input
              placeholder="搜索用户名前缀"
              value={filter.keyword}
              onChange={(e) => setFilter({ ...filter, keyword: e.target.value })}
              className={`${inputCls} pl-9`}
            />
          </div>
          <select
            value={filter.role}
            onChange={(e) => setFilter({ ...filter, role: e.target.value as FilterState['role'] })}
            className={`${inputCls} w-auto cursor-pointer`}
          >
            <option value="">全部角色</option>
            <option value="user">普通用户</option>
            <option value="admin">管理员</option>
          </select>
          <select
            value={filter.is_active}
            onChange={(e) => setFilter({ ...filter, is_active: e.target.value as FilterState['is_active'] })}
            className={`${inputCls} w-auto cursor-pointer`}
          >
            <option value="">全部状态</option>
            <option value="true">启用</option>
            <option value="false">已停用</option>
          </select>
        </div>

        {list.isLoading ? (
          <Loading />
        ) : (list.data?.items.length ?? 0) === 0 ? (
          <EmptyState text="当前条件下暂无用户" />
        ) : (
          <TableShell head={['用户名', '角色', '状态', '最近登录', '注册时间', '操作']}>
            {list.data?.items.map((u) => (
              <tr key={u.id} className="border-ad-border hover:bg-ad-surface-2 border-b transition-colors last:border-0">
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2.5">
                    <span className="bg-ad-primary-soft text-ad-primary-dark grid size-8 shrink-0 place-items-center rounded-full text-xs font-semibold">
                      {u.username.slice(0, 1).toUpperCase()}
                    </span>
                    <span className="text-ad-ink font-medium">{u.username}</span>
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  <select
                    value={u.role}
                    onChange={(e) => role.mutate({ id: u.id, role: e.target.value as Role }, { onError: (err) => setBanner(msg(err)) })}
                    className="border-ad-border-strong focus:border-ad-primary focus:ring-ad-primary/20 text-ad-ink cursor-pointer rounded-ad-xs border bg-ad-surface px-2 py-1 text-xs focus:ring-2 focus:outline-none"
                  >
                    <option value="user">普通用户</option>
                    <option value="admin">管理员</option>
                  </select>
                </td>
                <td className="px-3 py-2.5">
                  <Badge tone={u.is_active ? 'success' : 'danger'}>{u.is_active ? '启用' : '已停用'}</Badge>
                </td>
                <td className="text-ad-muted font-ad-mono px-3 py-2.5 text-xs tabular-nums">
                  {u.last_login_at ? new Date(u.last_login_at).toLocaleString('zh-CN') : '从未登录'}
                </td>
                <td className="text-ad-muted font-ad-mono px-3 py-2.5 text-xs tabular-nums">{new Date(u.created_at).toLocaleString('zh-CN')}</td>
                <td className="px-3 py-2.5">
                  <div className="flex justify-end gap-1">
                    <Button variant="ghost" size="sm" onClick={() => setAction({ kind: 'reset', user: u })}>
                      重置密码
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setAction({ kind: 'toggle', user: u })}>
                      {u.is_active ? '停用' : '启用'}
                    </Button>
                    <Button variant="ghost" size="sm" className="text-ad-danger hover:bg-ad-danger-soft" onClick={() => setAction({ kind: 'revoke', user: u })}>
                      撤销会话
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </TableShell>
        )}
      </Card>

      {creating ? <CreateDialog onClose={() => setCreating(false)} onDone={(n) => setBanner(`已创建用户 ${n}`)} /> : null}

      {action?.kind === 'reset' ? (
        <ResetDialog user={action.user} onClose={() => setAction(null)} onDone={() => { setAction(null); setBanner(`已重置 ${action.user.username} 的密码`) }} />
      ) : null}

      {action?.kind === 'toggle' ? (
        <Modal
          title={action.user.is_active ? '停用用户' : '启用用户'}
          onClose={() => setAction(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setAction(null)}>取消</Button>
              <Button variant={action.user.is_active ? 'danger' : 'primary'} loading={active.isPending} onClick={onToggle}>
                确认{action.user.is_active ? '停用' : '启用'}
              </Button>
            </>
          }
        >
          <p className="text-ad-ink text-sm">
            确定要{action.user.is_active ? '停用' : '启用'}用户 <strong>{action.user.username}</strong> 吗？
          </p>
          {action.user.is_active ? (
            <p className="text-ad-muted mt-2 text-xs">停用后该用户将无法登录，现有会话仍有效，可另行「撤销会话」强制下线。</p>
          ) : null}
        </Modal>
      ) : null}

      {action?.kind === 'revoke' ? (
        <Modal
          title="撤销全部会话"
          onClose={() => setAction(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setAction(null)}>取消</Button>
              <Button variant="danger" loading={revoke.isPending} onClick={onRevoke}>确认撤销</Button>
            </>
          }
        >
          <p className="text-ad-ink text-sm">
            将强制下线 <strong>{action.user.username}</strong> 的所有已登录设备，需要重新登录。
          </p>
        </Modal>
      ) : null}
    </div>
  )
}

function CreateDialog({ onClose, onDone }: { onClose: () => void; onDone: (username: string) => void }) {
  const create = useCreateAdminUser()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('user')
  const [isActive, setIsActive] = useState(true)
  const [err, setErr] = useState('')

  const submit = () => {
    setErr('')
    create.mutate(
      { username, password, role, is_active: isActive },
      { onSuccess: () => { onDone(username); onClose() }, onError: (e) => setErr(msg(e)) },
    )
  }

  return (
    <Modal
      title="新建用户"
      desc="创建后可随时调整角色与启停状态"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button variant="primary" loading={create.isPending} disabled={!username || password.length < 6} onClick={submit}>
            创建用户
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="用户名">
          <input value={username} onChange={(e) => setUsername(e.target.value)} className={inputCls} placeholder="登录用户名" />
        </Field>
        <Field label="密码" hint="6-64 个字符">
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} placeholder="初始密码" />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="角色">
            <select value={role} onChange={(e) => setRole(e.target.value as Role)} className={inputCls}>
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </Field>
          <Field label="账号状态">
            <button
              type="button"
              onClick={() => setIsActive((v) => !v)}
              className={`${inputCls} flex cursor-pointer items-center justify-between`}
            >
              <span>{isActive ? '启用' : '停用'}</span>
              <span className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${isActive ? 'bg-ad-primary' : 'bg-ad-border-strong'}`}>
                <span className={`inline-block size-4 transform rounded-full bg-white transition-transform ${isActive ? 'translate-x-4' : 'translate-x-0.5'}`} />
              </span>
            </button>
          </Field>
        </div>
        {err ? <p className="text-ad-danger text-xs">{err}</p> : null}
      </div>
    </Modal>
  )
}

function ResetDialog({ user, onClose, onDone }: { user: AdminUser; onClose: () => void; onDone: () => void }) {
  const reset = useResetUserPassword()
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')

  const submit = () => {
    setErr('')
    reset.mutate(
      { id: user.id, new_password: password },
      { onSuccess: onDone, onError: (e) => setErr(msg(e)) },
    )
  }

  return (
    <Modal
      title="重置密码"
      desc={`为 ${user.username} 设置新密码，将同时撤销其全部会话`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button variant="primary" loading={reset.isPending} disabled={password.length < 6} onClick={submit}>确认重置</Button>
        </>
      }
    >
      <Field label="新密码" hint="6-64 个字符">
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} placeholder="输入新密码" autoFocus />
      </Field>
      {err ? <p className="text-ad-danger mt-2 text-xs">{err}</p> : null}
    </Modal>
  )
}
