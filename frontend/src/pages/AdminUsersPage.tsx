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
import {
  Alert,
  Button,
  DataTable,
  EmptyState,
  Field,
  Loading,
  Modal,
  Panel,
  Tag,
  Toolbar,
  cellCls,
  inputCls,
  rowCls,
  selectCls,
} from '@/components/admin/ui'

type FilterState = { keyword: string; role: '' | Role; is_active: '' | 'true' | 'false' }

const EMPTY_FILTER: FilterState = { keyword: '', role: '', is_active: '' }

function msg(error: unknown) {
  return error instanceof ApiError ? error.message : errorMessage(error)
}

type RowAction =
  | { kind: 'reset'; user: AdminUser }
  | { kind: 'revoke'; user: AdminUser }
  | { kind: 'toggle'; user: AdminUser }

export default function AdminUsersPage() {
  // 草稿筛选条件与已生效条件分离，避免每敲一个字就打一次接口
  const [draft, setDraft] = useState<FilterState>(EMPTY_FILTER)
  const [filter, setFilter] = useState<FilterState>(EMPTY_FILTER)
  const [creating, setCreating] = useState(false)
  const [action, setAction] = useState<RowAction | null>(null)
  const [banner, setBanner] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null)

  const list = useAdminUsers({
    keyword: filter.keyword || undefined,
    role: filter.role || undefined,
    is_active: filter.is_active === '' ? undefined : filter.is_active === 'true',
    limit: 100,
  })

  const role = useUpdateUserRole()
  const active = useUpdateUserActive()
  const revoke = useRevokeUserSessions()

  const dirty = draft.keyword !== filter.keyword || draft.role !== filter.role || draft.is_active !== filter.is_active

  const onToggle = () => {
    if (!action || action.kind !== 'toggle') return
    const u = action.user
    active.mutate(
      { id: u.id, is_active: !u.is_active },
      {
        onSuccess: () => {
          setAction(null)
          setBanner({ tone: 'ok', text: `已${u.is_active ? '停用' : '启用'}用户 ${u.username}` })
        },
        onError: (e) => setBanner({ tone: 'err', text: msg(e) }),
      },
    )
  }

  const onRevoke = () => {
    if (!action || action.kind !== 'revoke') return
    revoke.mutate(action.user.id, {
      onSuccess: () => {
        setAction(null)
        setBanner({ tone: 'ok', text: `已撤销 ${action.user.username} 的全部会话` })
      },
      onError: (e) => setBanner({ tone: 'err', text: msg(e) }),
    })
  }

  const items = list.data?.items ?? []

  return (
    <div className="space-y-3">
      {banner ? (
        <Alert tone={banner.tone === 'ok' ? 'ok' : 'err'} onClose={() => setBanner(null)}>
          {banner.text}
        </Alert>
      ) : null}

      <Panel
        title="用户管理"
        desc="查看与创建账号，调整角色与启停状态，重置密码或撤销会话"
        bodyClass="p-3"
        action={
          <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
            <svg viewBox="0 0 24 24" fill="none" className="size-3.5" aria-hidden>
              <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            新建用户
          </Button>
        }
      >
        {/* 筛选工具条 */}
        <Toolbar className="mb-3">
          <Field label="用户名" className="min-w-[180px] flex-1">
            <input
              placeholder="按前缀搜索用户名"
              value={draft.keyword}
              onChange={(e) => setDraft({ ...draft, keyword: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === 'Enter') setFilter(draft)
              }}
              className={inputCls}
            />
          </Field>
          <Field label="角色" className="w-36">
            <select
              value={draft.role}
              onChange={(e) => setDraft({ ...draft, role: e.target.value as FilterState['role'] })}
              className={selectCls}
            >
              <option value="">全部</option>
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </Field>
          <Field label="状态" className="w-36">
            <select
              value={draft.is_active}
              onChange={(e) => setDraft({ ...draft, is_active: e.target.value as FilterState['is_active'] })}
              className={selectCls}
            >
              <option value="">全部</option>
              <option value="true">启用</option>
              <option value="false">已停用</option>
            </select>
          </Field>
          <div className="flex items-center gap-2">
            <Button variant="primary" size="md" onClick={() => setFilter(draft)}>
              查询
            </Button>
            <Button
              variant="default"
              size="md"
              onClick={() => {
                setDraft(EMPTY_FILTER)
                setFilter(EMPTY_FILTER)
              }}
            >
              重置
            </Button>
          </div>
        </Toolbar>

        {list.isLoading ? (
          <Loading />
        ) : items.length === 0 ? (
          <EmptyState
            text="当前条件下暂无用户"
            hint={dirty || filter !== EMPTY_FILTER ? '试着放宽筛选条件，或点击「重置」' : '点击右上角「新建用户」创建第一个账号'}
          />
        ) : (
          <DataTable
            head={['用户名', '角色', '状态', '最近登录', '注册时间', '操作']}
            minWidth={840}
            footer={
              <>
                <span>
                  共 <span className="text-ad-ink font-ad-mono tabular-nums">{items.length}</span> 条记录
                  {list.data?.total != null && list.data.total > items.length ? `（匹配 ${list.data.total} 条，仅显示前 ${items.length} 条）` : ''}
                </span>
                {dirty ? <span className="text-ad-accent">筛选条件已修改，点击「查询」生效</span> : <span />}
              </>
            }
          >
            {items.map((u) => (
              <tr key={u.id} className={rowCls}>
                <td className={cellCls}>
                  <span className="text-ad-ink font-medium">{u.username}</span>
                </td>
                <td className={cellCls}>
                  <select
                    value={u.role}
                    aria-label={`${u.username} 的角色`}
                    onChange={(e) =>
                      role.mutate(
                        { id: u.id, role: e.target.value as Role },
                        {
                          onSuccess: () => setBanner({ tone: 'ok', text: `已将 ${u.username} 设为${e.target.value === 'admin' ? '管理员' : '普通用户'}` }),
                          onError: (err) => setBanner({ tone: 'err', text: msg(err) }),
                        },
                      )
                    }
                    className={`${selectCls} h-7 w-28 py-0 text-xs`}
                  >
                    <option value="user">普通用户</option>
                    <option value="admin">管理员</option>
                  </select>
                </td>
                <td className={cellCls}>
                  <Tag tone={u.is_active ? 'success' : 'danger'}>{u.is_active ? '启用' : '已停用'}</Tag>
                </td>
                <td className={`${cellCls} text-ad-muted font-ad-mono text-xs tabular-nums`}>
                  {u.last_login_at ? new Date(u.last_login_at).toLocaleString('zh-CN') : '从未登录'}
                </td>
                <td className={`${cellCls} text-ad-muted font-ad-mono text-xs tabular-nums`}>
                  {new Date(u.created_at).toLocaleString('zh-CN')}
                </td>
                <td className={cellCls}>
                  <div className="flex justify-end gap-1">
                    <Button variant="ghost" size="xs" onClick={() => setAction({ kind: 'reset', user: u })}>
                      重置密码
                    </Button>
                    <Button variant="ghost" size="xs" onClick={() => setAction({ kind: 'toggle', user: u })}>
                      {u.is_active ? '停用' : '启用'}
                    </Button>
                    <Button variant="ghost" size="xs" className="text-ad-danger hover:bg-ad-danger-soft" onClick={() => setAction({ kind: 'revoke', user: u })}>
                      撤销会话
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </DataTable>
        )}
      </Panel>

      {creating ? (
        <CreateDialog onClose={() => setCreating(false)} onDone={(n) => setBanner({ tone: 'ok', text: `已创建用户 ${n}` })} />
      ) : null}

      {action?.kind === 'reset' ? (
        <ResetDialog
          user={action.user}
          onClose={() => setAction(null)}
          onDone={() => {
            setAction(null)
            setBanner({ tone: 'ok', text: `已重置 ${action.user.username} 的密码` })
          }}
        />
      ) : null}

      {action?.kind === 'toggle' ? (
        <Modal
          title={action.user.is_active ? '停用用户' : '启用用户'}
          onClose={() => setAction(null)}
          footer={
            <>
              <Button variant="default" onClick={() => setAction(null)}>
                取消
              </Button>
              <Button
                variant={action.user.is_active ? 'dangerSolid' : 'primary'}
                loading={active.isPending}
                onClick={onToggle}
              >
                确认{action.user.is_active ? '停用' : '启用'}
              </Button>
            </>
          }
        >
          <p className="text-ad-ink text-[13px]">
            确定要{action.user.is_active ? '停用' : '启用'}用户 <strong>{action.user.username}</strong> 吗？
          </p>
          {action.user.is_active ? (
            <p className="text-ad-muted mt-2 text-[11px]">
              停用后该用户将无法登录，现有会话仍有效，可另行「撤销会话」强制下线。
            </p>
          ) : null}
        </Modal>
      ) : null}

      {action?.kind === 'revoke' ? (
        <Modal
          title="撤销全部会话"
          onClose={() => setAction(null)}
          footer={
            <>
              <Button variant="default" onClick={() => setAction(null)}>
                取消
              </Button>
              <Button variant="dangerSolid" loading={revoke.isPending} onClick={onRevoke}>
                确认撤销
              </Button>
            </>
          }
        >
          <p className="text-ad-ink text-[13px]">
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
      {
        onSuccess: () => {
          onDone(username)
          onClose()
        },
        onError: (e) => setErr(msg(e)),
      },
    )
  }

  return (
    <Modal
      title="新建用户"
      desc="创建后可随时调整角色与启停状态"
      onClose={onClose}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            取消
          </Button>
          <Button
            variant="primary"
            loading={create.isPending}
            disabled={!username || password.length < 6}
            onClick={submit}
          >
            创建用户
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="用户名">
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className={inputCls}
            placeholder="登录用户名"
            autoFocus
          />
        </Field>
        <Field label="密码" hint="6-64 个字符">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputCls}
            placeholder="初始密码"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="角色">
            <select value={role} onChange={(e) => setRole(e.target.value as Role)} className={selectCls}>
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </Field>
          <Field label="账号状态">
            <div className="flex gap-1.5">
              {(
                [
                  { value: true, label: '启用' },
                  { value: false, label: '停用' },
                ] as const
              ).map((opt) => (
                <button
                  key={String(opt.value)}
                  type="button"
                  onClick={() => setIsActive(opt.value)}
                  className={`h-8 flex-1 cursor-pointer border text-[13px] transition-colors ${
                    isActive === opt.value
                      ? 'border-ad-primary bg-ad-primary-soft text-ad-primary-dark font-medium'
                      : 'border-ad-border-strong text-ad-muted hover:bg-ad-surface-2'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </Field>
        </div>
        {err ? <Alert tone="err">{err}</Alert> : null}
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
      {
        onSuccess: onDone,
        onError: (e) => setErr(msg(e)),
      },
    )
  }

  return (
    <Modal
      title="重置密码"
      desc={`为 ${user.username} 设置新密码，将同时撤销其全部会话`}
      onClose={onClose}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            取消
          </Button>
          <Button variant="primary" loading={reset.isPending} disabled={password.length < 6} onClick={submit}>
            确认重置
          </Button>
        </>
      }
    >
      <Field label="新密码" hint="6-64 个字符">
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={inputCls}
          placeholder="输入新密码"
          autoFocus
        />
      </Field>
      {err ? <Alert tone="err">{err}</Alert> : null}
    </Modal>
  )
}
