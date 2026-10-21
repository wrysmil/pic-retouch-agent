import { useState } from 'react'

import {
  useAdjustQuota,
  usePolicies,
  usePublishPolicy,
  useReleaseReservation,
  useUserQuota,
} from '@/api/adminQuota'
import { useAdminUsers } from '@/api/adminUsers'
import { errorMessage } from '@/hooks/useAuth'
import {
  Alert,
  Button,
  DataTable,
  EmptyState,
  Field,
  Loading,
  Panel,
  Tag,
  cellCls,
  inputCls,
  rowCls,
  selectCls,
} from '@/components/admin/ui'

/** 免费权益配置：每日上限按版本发布，当天纠错走用户额度调整。 */
export default function AdminQuotaPage() {
  const policies = usePolicies()
  const publish = usePublishPolicy()
  const users = useAdminUsers({ limit: 100 })
  const [userId, setUserId] = useState('')
  const [limit, setLimit] = useState('5')
  const [effective, setEffective] = useState('')
  const [note, setNote] = useState('')
  const [units, setUnits] = useState('')
  const [reason, setReason] = useState('')
  const [releaseReason, setReleaseReason] = useState('')
  const [banner, setBanner] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null)

  const quota = useUserQuota(userId)
  const adjust = useAdjustQuota(userId)
  const release = useReleaseReservation(userId)

  const submitPolicy = () => {
    const value = Number(limit)
    if (!Number.isInteger(value) || value < 0) {
      setBanner({ tone: 'err', text: '每日上限必须是非负整数' })
      return
    }
    publish.mutate(
      {
        daily_limit: value,
        effective_from: effective || undefined,
        note: note.trim() || undefined,
      },
      {
        onSuccess: (policy) => {
          setBanner({
            tone: 'ok',
            text: `已发布 v${policy.version_seq}：每日 ${policy.daily_limit} 次，${policy.effective_from} 生效`,
          })
          setNote('')
        },
        onError: (error) => setBanner({ tone: 'err', text: errorMessage(error) }),
      },
    )
  }

  const submitAdjust = () => {
    const value = Number(units)
    if (!Number.isInteger(value) || value === 0) {
      setBanner({ tone: 'err', text: '调整数量必须是非零整数' })
      return
    }
    if (reason.trim().length < 2) {
      setBanner({ tone: 'err', text: '请填写至少 2 个字的调整原因' })
      return
    }
    adjust.mutate(
      { units: value, reason: reason.trim() },
      {
        onSuccess: () => {
          setBanner({ tone: 'ok', text: `已${value > 0 ? '增加' : '扣减'} ${Math.abs(value)} 次并记入流水` })
          setUnits('')
          setReason('')
        },
        onError: (error) => setBanner({ tone: 'err', text: errorMessage(error) }),
      },
    )
  }

  return (
    <div className="space-y-3">
      {banner ? (
        <Alert tone={banner.tone === 'ok' ? 'ok' : 'err'} onClose={() => setBanner(null)}>
          {banner.text}
        </Alert>
      ) : null}

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel
          title="免费会员每日上限"
          desc="新版本默认从明日 00:00（Asia/Shanghai）生效；当天修正请用右侧额度调整"
          bodyClass="space-y-3 p-3"
        >
          <div className="grid gap-2 sm:grid-cols-3">
            <Field label="每日次数">
              <input
                type="number"
                min={0}
                value={limit}
                onChange={(event) => setLimit(event.target.value)}
                className={inputCls}
              />
            </Field>
            <Field label="生效日期" hint="留空为明日">
              <input
                type="date"
                value={effective}
                onChange={(event) => setEffective(event.target.value)}
                className={inputCls}
              />
            </Field>
            <Field label="发布说明">
              <input
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="例如：双十一活动期"
                className={inputCls}
              />
            </Field>
          </div>
          <div className="flex items-center justify-between gap-3">
            <p className="text-ad-faint text-[11px] leading-5">
              计次口径：成功交付 1 张 AI 图片 = 1 次；本地裁剪、调色、投放尺寸不扣次数。
            </p>
            <Button variant="primary" size="sm" disabled={publish.isPending} onClick={submitPolicy}>
              {publish.isPending ? '发布中…' : '发布新版本'}
            </Button>
          </div>

          {policies.isPending ? (
            <Loading text="读取策略…" />
          ) : policies.isError ? (
            <Alert tone="err">{errorMessage(policies.error)}</Alert>
          ) : policies.data?.length ? (
            <DataTable
              head={['版本', '每日上限', '生效日期', '说明', '发布时间']}
              align={['left', 'right', 'left', 'left', 'right']}
              minWidth={560}
            >
              {policies.data.map((policy) => (
                <tr key={policy.id} className={rowCls}>
                  <td className={`${cellCls} font-ad-mono text-ad-ink text-[13px]`}>v{policy.version_seq}</td>
                  <td className={`${cellCls} text-ad-ink text-right text-[13px] tabular-nums`}>
                    {policy.daily_limit}
                  </td>
                  <td className={`${cellCls} text-ad-muted text-[12px]`}>{policy.effective_from}</td>
                  <td className={`${cellCls} text-ad-muted max-w-[220px] truncate text-[12px]`}>
                    {policy.note || '—'}
                  </td>
                  <td className={`${cellCls} text-ad-faint text-right text-[12px]`}>
                    {new Date(policy.created_at).toLocaleString('zh-CN')}
                  </td>
                </tr>
              ))}
            </DataTable>
          ) : (
            <EmptyState text="还没有策略版本" hint="发布第一版后，新日桶才会按该上限创建。" />
          )}
        </Panel>

        <Panel
          title="用户额度与纠错"
          desc="查看当天日桶与未结束预占；调整必须填写原因并记入不可变流水"
          bodyClass="space-y-3 p-3"
        >
          <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
            <Field label="选择用户">
              <select value={userId} onChange={(event) => setUserId(event.target.value)} className={selectCls}>
                <option value="">— 选择账号 —</option>
                {(users.data?.items ?? []).map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.username}（{user.role === 'admin' ? '管理员' : '普通用户'}）
                  </option>
                ))}
              </select>
            </Field>
            <Tag tone={userId ? 'success' : 'neutral'}>{userId ? '已选择' : '未选择'}</Tag>
          </div>

          {!userId ? (
            <p className="text-ad-faint text-[12px]">选择账号后查看当天额度。</p>
          ) : quota.isPending ? (
            <Loading text="读取额度…" />
          ) : quota.isError ? (
            <Alert tone="err">{errorMessage(quota.error)}</Alert>
          ) : quota.data ? (
            <>
              <div className="grid grid-cols-2 gap-px border-ad-border bg-ad-border sm:grid-cols-4">
                {[
                  ['上限', quota.data.limit + quota.data.adjustment],
                  ['已用', quota.data.consumed],
                  ['预占', quota.data.reserved],
                  ['可用', quota.data.available],
                ].map(([label, value]) => (
                  <div key={label} className="bg-ad-surface px-3 py-2">
                    <p className="text-ad-faint text-[10px]">{label}</p>
                    <p className="font-ad-mono text-ad-ink mt-0.5 text-lg font-semibold tabular-nums">
                      {value}
                    </p>
                  </div>
                ))}
              </div>
              <p className="text-ad-faint text-[11px]">
                规则 v{quota.data.policy_version_seq} · {quota.data.quota_date} ·{' '}
                {new Date(quota.data.reset_at).toLocaleString('zh-CN')} 重置
              </p>

              <div className="grid gap-2 sm:grid-cols-[100px_1fr_auto] sm:items-end">
                <Field label="调整次数" hint="可为负">
                  <input
                    type="number"
                    value={units}
                    onChange={(event) => setUnits(event.target.value)}
                    className={inputCls}
                  />
                </Field>
                <Field label="原因">
                  <input
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    placeholder="例如：厂商故障补偿"
                    className={inputCls}
                  />
                </Field>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={adjust.isPending}
                  onClick={submitAdjust}
                >
                  {adjust.isPending ? '提交中…' : '记入流水'}
                </Button>
              </div>

              <div>
                <div className="mb-1.5 flex items-end justify-between gap-2">
                  <p className="text-ad-muted text-[11px] font-medium">
                    未结束预占（{quota.data.open_reservations.length}）
                  </p>
                  {quota.data.open_reservations.length > 0 ? (
                    <input
                      value={releaseReason}
                      onChange={(event) => setReleaseReason(event.target.value)}
                      placeholder="释放原因（必填）"
                      className={`${inputCls} h-7 max-w-[220px]`}
                    />
                  ) : null}
                </div>
                {quota.data.open_reservations.length === 0 ? (
                  <p className="text-ad-faint text-[11px]">没有进行中的预占。</p>
                ) : (
                  <ul className="border-ad-border divide-ad-border divide-y border">
                    {quota.data.open_reservations.map((row) => (
                      <li key={row.id} className="flex items-center justify-between gap-2 px-2.5 py-1.5">
                        <span className="font-ad-mono text-ad-muted truncate text-[11px]">
                          {row.run_id ?? row.turn_id ?? row.id}
                        </span>
                        <span className="flex shrink-0 items-center gap-2 text-[11px]">
                          <Tag tone={row.status === 'unknown' ? 'warn' : 'neutral'}>{row.status}</Tag>
                          <span className="text-ad-ink tabular-nums">{row.units} 次</span>
                          <Button
                            variant="danger"
                            size="xs"
                            disabled={release.isPending}
                            onClick={() => {
                              if (releaseReason.trim().length < 2) {
                                setBanner({ tone: 'err', text: '请先填写释放原因' })
                                return
                              }
                              release.mutate(
                                { id: row.id, reason: releaseReason.trim() },
                                {
                                  onSuccess: () => {
                                    setBanner({ tone: 'ok', text: '已释放该预占并记入流水' })
                                    setReleaseReason('')
                                  },
                                  onError: (error) =>
                                    setBanner({ tone: 'err', text: errorMessage(error) }),
                                },
                              )
                            }}
                          >
                            释放
                          </Button>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          ) : null}
        </Panel>
      </div>
    </div>
  )
}
