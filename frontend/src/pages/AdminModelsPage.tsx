import { useMemo, useState } from 'react'

import {
  type AdapterType,
  type Connection,
  type ModelType,
  type Runtime,
  useActivateModel,
  useAddConnectionVersion,
  useConnections,
  useCreateConnection,
  useCreateModel,
  useDisableModel,
  useModels,
  usePublishRuntime,
  useRollbackRuntime,
  useRuntime,
  useRuntimeVersions,
  useTestCapability,
} from '@/api/adminConfig'
import { ApiError } from '@/api/client'
import { errorMessage } from '@/hooks/useAuth'
import { Badge, Button, Card, EmptyState, Field, Loading, Modal, TableShell, inputCls, selectCls } from '@/components/admin/ui'

const ADAPTERS: AdapterType[] = ['dashscope', 'openai_compat', 'openai_image', 'mock']
const MODEL_TYPES: { value: ModelType; label: string }[] = [
  { value: 'text', label: '文本模型' },
  { value: 'image', label: '生图模型' },
]
const TYPE_LABEL: Record<ModelType, string> = { text: '文本', image: '生图' }

function msg(e: unknown) {
  return e instanceof ApiError ? e.message : errorMessage(e)
}

export default function AdminModelsPage() {
  const [tab, setTab] = useState<'runtime' | 'connections' | 'models'>('runtime')
  const [banner, setBanner] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null)

  const tabs = [
    { key: 'runtime', label: '运行版本' },
    { key: 'connections', label: '厂商连接' },
    { key: 'models', label: '模型清单' },
  ] as const

  return (
    <div className="space-y-5">
      {banner ? (
        <div
          className={`flex items-center justify-between rounded-ad-sm px-4 py-2.5 text-sm ${
            banner.tone === 'ok' ? 'bg-ad-primary-soft text-ad-primary-dark' : 'bg-ad-danger-soft text-ad-danger'
          }`}
        >
          <span>{banner.text}</span>
          <button type="button" onClick={() => setBanner(null)} className="cursor-pointer rounded p-0.5 hover:opacity-70" aria-label="关闭提示">
            <svg viewBox="0 0 24 24" fill="none" className="size-4">
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      ) : null}

      <div className="border-ad-border bg-ad-surface inline-flex rounded-ad-sm border p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`cursor-pointer rounded-ad-xs px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === t.key ? 'bg-ad-primary text-white' : 'text-ad-muted hover:text-ad-ink'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'runtime' ? <RuntimeTab notify={setBanner} /> : null}
      {tab === 'connections' ? <ConnectionsTab notify={setBanner} /> : null}
      {tab === 'models' ? <ModelsTab notify={setBanner} /> : null}
    </div>
  )
}

type Notify = (b: { tone: 'ok' | 'err'; text: string }) => void

/* ---------------- 运行版本 ---------------- */

function RuntimeTab({ notify }: { notify: Notify }) {
  const runtime = useRuntime()
  const versions = useRuntimeVersions()
  const models = useModels()
  const rollback = useRollbackRuntime()
  const test = useTestCapability()

  const [publishing, setPublishing] = useState(false)
  const [rollbackTo, setRollbackTo] = useState<number | null>(null)
  const [testCap, setTestCap] = useState<'text' | 'image.generate' | 'image.edit'>('image.generate')

  const nameOf = useMemo(() => {
    const m = new Map<string, string>()
    for (const model of models.data ?? []) m.set(model.id, model.display_name)
    return (id: string) => (id && id !== '00000000-0000-0000-0000-000000000000' ? (m.get(id) ?? '（未知模型）') : '—')
  }, [models.data])

  const r = runtime.data

  const onTest = () => {
    test.mutate(
      { capability: testCap, prompt: '一朵云' },
      {
        onSuccess: (res) =>
          notify({ tone: res.ok ? 'ok' : 'err', text: `测试 ${res.capability}：${res.ok ? '成功' : '失败'}（${res.duration_ms}ms）${res.ok ? '' : ` — ${res.detail}`}` }),
        onError: (e) => notify({ tone: 'err', text: msg(e) }),
      },
    )
  }

  return (
    <div className="space-y-5">
      <Card title="当前生效配置" desc="任务提交时会锁定该版本，热更新对进行中任务无影响">
        {runtime.isLoading ? (
          <Loading />
        ) : !r || r.current_version_seq == null ? (
          <EmptyState text="尚未发布运行配置" />
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-3">
              <Badge tone="brand">v{r.current_version_seq}</Badge>
              <span className="text-ad-muted font-ad-mono text-xs tabular-nums">
                发布于 {r.published_at ? new Date(r.published_at).toLocaleString('zh-CN') : '—'}
              </span>
              <span className="text-ad-faint font-ad-mono text-xs">· revision {r.revision}</span>
            </div>
            <dl className="grid gap-4 sm:grid-cols-2">
              <Binding label="文本模型" value={nameOf(r.text_model_id)} />
              <Binding label="生图模型" value={nameOf(r.image_model_id)} />
            </dl>
            {r.note ? (
              <p className="text-ad-muted border-ad-border border-t pt-3 text-xs">备注：{r.note}</p>
            ) : null}
            <div className="flex flex-wrap items-center gap-2 border-ad-border border-t pt-4">
              <span className="text-ad-muted mr-1 text-xs">连通性测试</span>
              <select value={testCap} onChange={(e) => setTestCap(e.target.value as typeof testCap)} className={`${inputCls} w-auto cursor-pointer py-1 text-xs`}>
                <option value="text">文本模型</option>
                <option value="image.generate">生图 · 生成</option>
                <option value="image.edit">生图 · 编辑</option>
              </select>
              <Button variant="outline" size="sm" loading={test.isPending} onClick={onTest}>
                发起测试
              </Button>
              <Button variant="primary" size="sm" onClick={() => setPublishing(true)}>发布新版本</Button>
            </div>
          </div>
        )}
      </Card>

      <Card title="历史版本" desc="回滚会生成一个新版本，指向所选历史配置">
        {versions.isLoading ? (
          <Loading />
        ) : (versions.data?.length ?? 0) === 0 ? (
          <EmptyState text="尚无历史版本" />
        ) : (
          <TableShell head={['版本', '文本 / 生图', '发布时间', '备注', '操作']}>
            {versions.data?.map((v) => (
              <tr key={v.id} className="border-ad-border hover:bg-ad-surface-2 border-b transition-colors last:border-0">
                <td className="px-3 py-2.5">
                  <Badge tone={r?.current_version_seq === v.version_seq ? 'brand' : 'neutral'}>v{v.version_seq}</Badge>
                </td>
                <td className="text-ad-muted px-3 py-2.5 text-xs">
                  {nameOf(v.text_model_id)} / {nameOf(v.image_model_id)}
                </td>
                <td className="text-ad-muted font-ad-mono px-3 py-2.5 text-xs tabular-nums">{new Date(v.published_at).toLocaleString('zh-CN')}</td>
                <td className="text-ad-muted px-3 py-2.5 text-xs">
                  {v.note || '—'}
                  {v.rolled_back_from != null ? <span className="text-ad-faint">（回滚自 v{v.rolled_back_from}）</span> : null}
                </td>
                <td className="px-3 py-2.5 text-right">
                  {r?.current_version_seq === v.version_seq ? (
                    <span className="text-ad-faint text-xs">当前</span>
                  ) : (
                    <Button variant="ghost" size="sm" onClick={() => setRollbackTo(v.version_seq)}>回滚到此版本</Button>
                  )}
                </td>
              </tr>
            ))}
          </TableShell>
        )}
      </Card>

      {publishing && r ? (
        <PublishDialog
          runtime={r}
          models={models.data ?? []}
          onClose={() => setPublishing(false)}
          onDone={(seq) => { setPublishing(false); notify({ tone: 'ok', text: `已发布 v${seq}` }) }}
          onError={(e) => notify({ tone: 'err', text: msg(e) })}
        />
      ) : null}

      {rollbackTo != null && r ? (
        <Modal
          title="回滚运行配置"
          onClose={() => setRollbackTo(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setRollbackTo(null)}>取消</Button>
              <Button
                variant="primary"
                loading={rollback.isPending}
                onClick={() =>
                  rollback.mutate(
                    { target_seq: rollbackTo, expected_revision: r.revision },
                    { onSuccess: () => { setRollbackTo(null); notify({ tone: 'ok', text: `已回滚到 v${rollbackTo}` }) }, onError: (e) => notify({ tone: 'err', text: msg(e) }) },
                  )
                }
              >
                确认回滚到 v{rollbackTo}
              </Button>
            </>
          }
        >
          <p className="text-ad-ink text-sm">
            回滚不会删除历史，而是生成一个指向 v{rollbackTo} 配置的新版本并立即生效。
          </p>
        </Modal>
      ) : null}
    </div>
  )
}

function Binding({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-ad-surface-2 rounded-ad-sm p-3.5">
      <dt className="text-ad-muted text-xs">{label}</dt>
      <dd className="text-ad-ink mt-1 truncate text-sm font-medium" title={value}>{value}</dd>
    </div>
  )
}

function PublishDialog({
  runtime,
  models,
  onClose,
  onDone,
  onError,
}: {
  runtime: Runtime
  models: { id: string; display_name: string; model_type: ModelType; status: string }[]
  onClose: () => void
  onDone: (seq: number) => void
  onError: (e: unknown) => void
}) {
  const publish = usePublishRuntime()
  const [text, setText] = useState(
    runtime.text_model_id !== '00000000-0000-0000-0000-000000000000' ? runtime.text_model_id : '',
  )
  const [image, setImage] = useState(
    runtime.image_model_id !== '00000000-0000-0000-0000-000000000000' ? runtime.image_model_id : '',
  )
  const [note, setNote] = useState('')

  const pick = (type: ModelType) => models.filter((m) => m.status === 'active' && m.model_type === type)
  const textModels = pick('text')
  const imageModels = pick('image')

  const submit = () => {
    publish.mutate(
      { text_model_id: text, image_model_id: image, note, expected_revision: runtime.revision },
      { onSuccess: (res) => onDone(res.current_version_seq ?? 0), onError },
    )
  }

  return (
    <Modal
      title="发布新的运行配置"
      desc="各选一个已启用的文本与生图模型并填写变更说明"
      onClose={onClose}
      width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button variant="primary" loading={publish.isPending} disabled={!text || !image} onClick={submit}>确认发布</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="文本模型" hint={textModels.length ? undefined : '没有已启用的文本模型'}>
          <select value={text} onChange={(e) => setText(e.target.value)} className={selectCls} disabled={textModels.length === 0}>
            <option value="">请选择</option>
            {textModels.map((m) => <option key={m.id} value={m.id}>{m.display_name}</option>)}
          </select>
        </Field>
        <Field label="生图模型" hint={imageModels.length ? undefined : '没有已启用的生图模型'}>
          <select value={image} onChange={(e) => setImage(e.target.value)} className={selectCls} disabled={imageModels.length === 0}>
            <option value="">请选择</option>
            {imageModels.map((m) => <option key={m.id} value={m.id}>{m.display_name}</option>)}
          </select>
        </Field>
        <Field label="变更说明">
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} className={inputCls} placeholder="本次发布的说明" />
        </Field>
      </div>
    </Modal>
  )
}

/* ---------------- 厂商连接 ---------------- */

function ConnectionsTab({ notify }: { notify: Notify }) {
  const connections = useConnections()
  const [creating, setCreating] = useState(false)
  const [versionFor, setVersionFor] = useState<Connection | null>(null)

  return (
    <Card
      title="厂商连接"
      desc="维护各模型厂商的接入地址与密钥；密钥仅存密文，展示为掩码"
      action={<Button variant="primary" onClick={() => setCreating(true)}>新建连接</Button>}
    >
      {connections.isLoading ? (
        <Loading />
      ) : (connections.data?.length ?? 0) === 0 ? (
        <EmptyState text="尚未维护任何连接" />
      ) : (
        <TableShell head={['名称 / 标识', '适配器', '当前版本', 'Base URL', '密钥', '状态', '操作']}>
          {connections.data?.map((c) => (
            <tr key={c.id} className="border-ad-border hover:bg-ad-surface-2 border-b transition-colors last:border-0">
              <td className="px-3 py-2.5">
                <div className="text-ad-ink font-medium">{c.display_name}</div>
                <div className="text-ad-faint font-ad-mono text-xs">{c.slug} · {c.vendor}</div>
              </td>
              <td className="px-3 py-2.5"><Badge tone="neutral">{c.adapter_type}</Badge></td>
              <td className="text-ad-muted font-ad-mono px-3 py-2.5 text-xs tabular-nums">{c.current_version_seq != null ? `v${c.current_version_seq}` : '—'}</td>
              <td className="text-ad-muted font-ad-mono px-3 py-2.5 text-xs max-w-[220px] truncate" title={c.base_url}>{c.base_url || '—'}</td>
              <td className="text-ad-muted px-3 py-2.5 font-ad-mono text-xs">{c.key_mask || '—'}</td>
              <td className="px-3 py-2.5"><Badge tone={c.status === 'active' ? 'success' : 'neutral'}>{c.status}</Badge></td>
              <td className="px-3 py-2.5 text-right">
                <Button variant="ghost" size="sm" onClick={() => setVersionFor(c)}>更新密钥/地址</Button>
              </td>
            </tr>
          ))}
        </TableShell>
      )}

      {creating ? (
        <ConnectionDialog onClose={() => setCreating(false)} onDone={(s) => { setCreating(false); notify({ tone: 'ok', text: `已创建连接 ${s}` }) }} onError={(e) => notify({ tone: 'err', text: msg(e) })} />
      ) : null}
      {versionFor ? (
        <VersionDialog conn={versionFor} onClose={() => setVersionFor(null)} onDone={() => { setVersionFor(null); notify({ tone: 'ok', text: '已新增连接版本' }) }} onError={(e) => notify({ tone: 'err', text: msg(e) })} />
      ) : null}
    </Card>
  )
}

function ConnectionDialog({ onClose, onDone, onError }: { onClose: () => void; onDone: (slug: string) => void; onError: (e: unknown) => void }) {
  const create = useCreateConnection()
  const [form, setForm] = useState({ slug: '', vendor: '', adapter_type: 'dashscope' as AdapterType, display_name: '', base_url: '', api_key: '' })
  const set = (k: keyof typeof form, v: string) => setForm({ ...form, [k]: v })

  const submit = () => create.mutate(form, { onSuccess: () => onDone(form.slug), onError })

  return (
    <Modal
      title="新建厂商连接"
      onClose={onClose}
      width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button variant="primary" loading={create.isPending} disabled={!form.slug || !form.base_url || !form.api_key} onClick={submit}>创建</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Field label="标识 slug" hint="小写字母/数字/-/_">
            <input value={form.slug} onChange={(e) => set('slug', e.target.value)} className={inputCls} placeholder="dashscope-main" />
          </Field>
          <Field label="厂商 vendor">
            <input value={form.vendor} onChange={(e) => set('vendor', e.target.value)} className={inputCls} placeholder="dashscope" />
          </Field>
        </div>
        <Field label="显示名称">
          <input value={form.display_name} onChange={(e) => set('display_name', e.target.value)} className={inputCls} placeholder="百炼主账号" />
        </Field>
        <Field label="适配器类型">
          <select value={form.adapter_type} onChange={(e) => set('adapter_type', e.target.value)} className={selectCls}>
            {ADAPTERS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </Field>
        <Field label="Base URL" hint="生产需 HTTPS">
          <input value={form.base_url} onChange={(e) => set('base_url', e.target.value)} className={inputCls} placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
        </Field>
        <Field label="API Key">
          <input type="password" value={form.api_key} onChange={(e) => set('api_key', e.target.value)} className={inputCls} placeholder="密钥将以密文保存" />
        </Field>
      </div>
    </Modal>
  )
}

function VersionDialog({ conn, onClose, onDone, onError }: { conn: Connection; onClose: () => void; onDone: () => void; onError: (e: unknown) => void }) {
  const addVersion = useAddConnectionVersion()
  const [base_url, setBaseUrl] = useState(conn.base_url || '')
  const [api_key, setApiKey] = useState('')

  const submit = () =>
    addVersion.mutate(
      { id: conn.id, base_url: base_url || null, api_key: api_key || null },
      { onSuccess: onDone, onError },
    )

  return (
    <Modal
      title="更新连接密钥 / 地址"
      desc={`为 ${conn.display_name} 追加一个不可变版本`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button variant="primary" loading={addVersion.isPending} disabled={!base_url && !api_key} onClick={submit}>保存新版本</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Base URL" hint="留空则沿用当前">
          <input value={base_url} onChange={(e) => setBaseUrl(e.target.value)} className={inputCls} />
        </Field>
        <Field label="新 API Key" hint="留空则沿用当前">
          <input type="password" value={api_key} onChange={(e) => setApiKey(e.target.value)} className={inputCls} placeholder="当前掩码：****" />
        </Field>
      </div>
    </Modal>
  )
}

/* ---------------- 模型清单 ---------------- */

function ModelsTab({ notify }: { notify: Notify }) {
  const models = useModels()
  const connections = useConnections()
  const activate = useActivateModel()
  const disable = useDisableModel()
  const [creating, setCreating] = useState(false)

  const connName = useMemo(() => {
    const m = new Map<string, string>()
    for (const c of connections.data ?? []) m.set(c.id, c.display_name)
    return (id: string) => m.get(id) ?? '—'
  }, [connections.data])

  return (
    <Card
      title="模型清单"
      desc="每类模型可登记多个，但同时只能启用一个；启用新的会自动停用同类旧的"
      action={<Button variant="primary" onClick={() => setCreating(true)}>登记模型</Button>}
    >
      {models.isLoading ? (
        <Loading />
      ) : (models.data?.length ?? 0) === 0 ? (
        <EmptyState text="尚未登记任何模型" />
      ) : (
        <TableShell head={['名称 / slug', '所属连接', '厂商标识', '类型', '状态', '操作']}>
          {models.data?.map((m) => (
            <tr key={m.id} className="border-ad-border hover:bg-ad-surface-2 border-b transition-colors last:border-0">
              <td className="px-3 py-2.5">
                <div className="text-ad-ink font-medium">{m.display_name}</div>
                <div className="text-ad-faint font-ad-mono text-xs">{m.slug}</div>
              </td>
              <td className="text-ad-muted px-3 py-2.5 text-xs">{connName(m.connection_id)}</td>
              <td className="text-ad-muted px-3 py-2.5 font-ad-mono text-xs">
                {m.vendor_model_id}
                {m.edit_vendor_model_id ? <div className="text-ad-faint">编辑：{m.edit_vendor_model_id}</div> : null}
              </td>
              <td className="px-3 py-2.5"><Badge tone="brand">{TYPE_LABEL[m.model_type]}</Badge></td>
              <td className="px-3 py-2.5"><Badge tone={m.status === 'active' ? 'success' : 'neutral'}>{m.status === 'active' ? '已启用' : '已停用'}</Badge></td>
              <td className="px-3 py-2.5 text-right">
                {m.status === 'active' ? (
                  <Button variant="ghost" size="sm" className="text-ad-danger hover:bg-ad-danger-soft" loading={disable.isPending} onClick={() => disable.mutate(m.id, { onSuccess: () => notify({ tone: 'ok', text: `已停用模型 ${m.display_name}` }), onError: (e) => notify({ tone: 'err', text: msg(e) }) })}>
                    停用
                  </Button>
                ) : (
                  <Button variant="ghost" size="sm" loading={activate.isPending} onClick={() => activate.mutate(m.id, { onSuccess: () => notify({ tone: 'ok', text: `已启用模型 ${m.display_name}` }), onError: (e) => notify({ tone: 'err', text: msg(e) }) })}>
                    启用
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </TableShell>
      )}

      {creating ? (
        <ModelDialog connections={connections.data ?? []} onClose={() => setCreating(false)} onDone={(s) => { setCreating(false); notify({ tone: 'ok', text: `已登记模型 ${s}` }) }} onError={(e) => notify({ tone: 'err', text: msg(e) })} />
      ) : null}
    </Card>
  )
}

function ModelDialog({ connections, onClose, onDone, onError }: { connections: Connection[]; onClose: () => void; onDone: (slug: string) => void; onError: (e: unknown) => void }) {
  const create = useCreateModel()
  const [form, setForm] = useState({ slug: '', connection_id: connections[0]?.id ?? '', vendor_model_id: '', display_name: '' })
  const [modelType, setModelType] = useState<ModelType>('text')
  const [editVendorId, setEditVendorId] = useState('')
  const set = (k: keyof typeof form, v: string) => setForm({ ...form, [k]: v })

  const submit = () =>
    create.mutate(
      {
        ...form,
        model_type: modelType,
        edit_vendor_model_id: modelType === 'image' && editVendorId.trim() ? editVendorId.trim() : null,
      },
      { onSuccess: () => onDone(form.slug), onError },
    )

  return (
    <Modal
      title="登记模型"
      onClose={onClose}
      width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button variant="primary" loading={create.isPending} disabled={!form.slug || !form.connection_id || !form.vendor_model_id || !form.display_name} onClick={submit}>登记</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="模型类型">
          <div className="flex gap-2">
            {MODEL_TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setModelType(t.value)}
                className={`cursor-pointer rounded-ad-sm border px-4 py-1.5 text-sm transition-colors ${
                  modelType === t.value ? 'border-ad-primary bg-ad-primary-soft text-ad-primary-dark' : 'border-ad-border-strong text-ad-muted hover:bg-ad-surface-2'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="标识 slug">
            <input value={form.slug} onChange={(e) => set('slug', e.target.value)} className={inputCls} placeholder="wanx-t2i" />
          </Field>
          <Field label="所属连接">
            <select value={form.connection_id} onChange={(e) => set('connection_id', e.target.value)} className={selectCls}>
              {connections.map((c) => <option key={c.id} value={c.id}>{c.display_name}</option>)}
            </select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="厂商模型 ID">
            <input value={form.vendor_model_id} onChange={(e) => set('vendor_model_id', e.target.value)} className={inputCls} placeholder="wanx2.1-t2i-turbo" />
          </Field>
          <Field label="显示名称">
            <input value={form.display_name} onChange={(e) => set('display_name', e.target.value)} className={inputCls} placeholder="通义万相文生图" />
          </Field>
        </div>
        {modelType === 'image' ? (
          <Field label="编辑模型 ID" hint="选填；留空则编辑复用上面的生成模型">
            <input value={editVendorId} onChange={(e) => setEditVendorId(e.target.value)} className={inputCls} placeholder="qwen-image-edit-max" />
          </Field>
        ) : null}
      </div>
    </Modal>
  )
}
