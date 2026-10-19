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
import {
  Alert,
  Button,
  DataTable,
  EmptyState,
  Field,
  KeyValue,
  Loading,
  Modal,
  Panel,
  Tabs,
  Tag,
  Toolbar,
  cellCls,
  inputCls,
  rowCls,
  selectCls,
} from '@/components/admin/ui'

const ADAPTERS: AdapterType[] = ['dashscope', 'openai_compat', 'openai_image', 'toookens', 'minimax', 'mock']
// 各适配器的规范 base URL：MiniMax 只填到 /v1 为止（adapter 也会兜底纠正），
// 填成文档里的 .../v1/chat/completions 会被拼成重复路径。
const BASE_URL_PLACEHOLDER: Record<AdapterType, string> = {
  dashscope: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  openai_compat: 'https://api.openai.com/v1',
  openai_image: 'https://api.openai.com/v1',
  toookens: 'https://api.toookens.com/v1',
  minimax: 'https://api.minimax.cn/v1',
  mock: 'http://localhost/mock',
}
// MiniMax M3.1-Flash 的思考深度；留空则用厂商默认（max，最慢但最充分）
const REASONING_EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max'] as const
const MODEL_TYPES: { value: ModelType; label: string }[] = [
  { value: 'text', label: '文本模型' },
  { value: 'image', label: '生图模型' },
]
const TYPE_LABEL: Record<ModelType, string> = { text: '文本', image: '生图' }
const TABS = [
  { key: 'runtime', label: '运行版本' },
  { key: 'connections', label: '厂商连接' },
  { key: 'models', label: '模型清单' },
] as const

type TabKey = (typeof TABS)[number]['key']

function msg(e: unknown) {
  return e instanceof ApiError ? e.message : errorMessage(e)
}

export default function AdminModelsPage() {
  const [tab, setTab] = useState<TabKey>('runtime')
  const [banner, setBanner] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null)

  return (
    <div className="space-y-3">
      {banner ? (
        <Alert tone={banner.tone === 'ok' ? 'ok' : 'err'} onClose={() => setBanner(null)}>
          {banner.text}
        </Alert>
      ) : null}

      <div className="flex items-center justify-between gap-3">
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
        <span className="text-ad-faint text-[11px]">配置变更对进行中的任务不生效，新任务将使用最新生效版本</span>
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
    return (id: string) =>
      id && id !== '00000000-0000-0000-0000-000000000000' ? (m.get(id) ?? '（未知模型）') : '—'
  }, [models.data])

  const r = runtime.data
  const rows = versions.data ?? []

  const onTest = () => {
    test.mutate(
      { capability: testCap, prompt: '一朵云' },
      {
        onSuccess: (res) =>
          notify({
            tone: res.ok ? 'ok' : 'err',
            text: `测试 ${res.capability}：${res.ok ? '成功' : '失败'}（${res.duration_ms}ms）${res.ok ? '' : ` — ${res.detail}`}`,
          }),
        onError: (e) => notify({ tone: 'err', text: msg(e) }),
      },
    )
  }

  return (
    <div className="space-y-3">
      <Panel
        title="当前生效配置"
        desc="任务提交时会锁定该版本，热更新对进行中任务无影响"
        bodyClass="p-0"
        action={
          <Button variant="primary" size="sm" onClick={() => setPublishing(true)}>
            发布新版本
          </Button>
        }
      >
        {runtime.isLoading ? (
          <Loading />
        ) : !r || r.current_version_seq == null ? (
          <EmptyState text="尚未发布运行配置" hint="选择文本与生图模型后发布第一个运行版本" />
        ) : (
          <>
            <KeyValue
              columns={3}
              items={[
                { label: '生效版本', value: `v${r.current_version_seq}` },
                { label: '发布时间', value: r.published_at ? new Date(r.published_at).toLocaleString('zh-CN') : '—' },
                { label: '乐观锁版本', value: `revision ${r.revision}` },
                { label: '文本模型', value: nameOf(r.text_model_id) },
                { label: '生图模型', value: nameOf(r.image_model_id) },
                { label: '变更说明', value: r.note || '（无）' },
              ]}
            />
            <div className="border-ad-border flex flex-wrap items-center gap-2 border-t px-3 py-2">
              <span className="text-ad-muted mr-1 text-[11px]">连通性测试</span>
              <select
                value={testCap}
                onChange={(e) => setTestCap(e.target.value as typeof testCap)}
                aria-label="选择测试能力"
                className={`${selectCls} h-7 w-40 py-0 text-xs`}
              >
                <option value="text">文本模型</option>
                <option value="image.generate">生图 · 生成</option>
                <option value="image.edit">生图 · 编辑</option>
              </select>
              <Button variant="default" size="sm" loading={test.isPending} onClick={onTest}>
                发起测试
              </Button>
            </div>
          </>
        )}
      </Panel>

      <Panel title="历史版本" desc="回滚会生成一个新版本，指向所选历史配置" bodyClass="p-3">
        {versions.isLoading ? (
          <Loading />
        ) : rows.length === 0 ? (
          <EmptyState text="尚无历史版本" />
        ) : (
          <DataTable
            head={['版本', '文本 / 生图模型', '发布时间', '变更说明', '操作']}
            minWidth={760}
            footer={
              <span>
                共 <span className="text-ad-ink font-ad-mono tabular-nums">{rows.length}</span> 个版本
              </span>
            }
          >
            {rows.map((v) => (
              <tr key={v.id} className={rowCls}>
                <td className={cellCls}>
                  <Tag tone={r?.current_version_seq === v.version_seq ? 'brand' : 'neutral'} mono>
                    v{v.version_seq}
                  </Tag>
                </td>
                <td className={`${cellCls} text-ad-muted text-xs`}>
                  {nameOf(v.text_model_id)} / {nameOf(v.image_model_id)}
                </td>
                <td className={`${cellCls} text-ad-muted font-ad-mono text-xs tabular-nums`}>
                  {new Date(v.published_at).toLocaleString('zh-CN')}
                </td>
                <td className={`${cellCls} text-ad-muted text-xs`}>
                  {v.note || '—'}
                  {v.rolled_back_from != null ? (
                    <span className="text-ad-faint">（回滚自 v{v.rolled_back_from}）</span>
                  ) : null}
                </td>
                <td className={`${cellCls} text-right`}>
                  {r?.current_version_seq === v.version_seq ? (
                    <span className="text-ad-faint text-[11px]">当前</span>
                  ) : (
                    <Button variant="default" size="xs" onClick={() => setRollbackTo(v.version_seq)}>
                      回滚到此版本
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </DataTable>
        )}
      </Panel>

      {publishing && r ? (
        <PublishDialog
          runtime={r}
          models={models.data ?? []}
          onClose={() => setPublishing(false)}
          onDone={(seq) => {
            setPublishing(false)
            notify({ tone: 'ok', text: `已发布 v${seq}` })
          }}
          onError={(e) => notify({ tone: 'err', text: msg(e) })}
        />
      ) : null}

      {rollbackTo != null && r ? (
        <Modal
          title="回滚运行配置"
          onClose={() => setRollbackTo(null)}
          footer={
            <>
              <Button variant="default" onClick={() => setRollbackTo(null)}>
                取消
              </Button>
              <Button
                variant="primary"
                loading={rollback.isPending}
                onClick={() =>
                  rollback.mutate(
                    { target_seq: rollbackTo, expected_revision: r.revision },
                    {
                      onSuccess: () => {
                        setRollbackTo(null)
                        notify({ tone: 'ok', text: `已回滚到 v${rollbackTo}` })
                      },
                      onError: (e) => notify({ tone: 'err', text: msg(e) }),
                    },
                  )
                }
              >
                确认回滚到 v{rollbackTo}
              </Button>
            </>
          }
        >
          <p className="text-ad-ink text-[13px]">
            回滚不会删除历史，而是生成一个指向 v{rollbackTo} 配置的新版本并立即生效。
          </p>
        </Modal>
      ) : null}
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

  const textModels = models.filter((m) => m.status === 'active' && m.model_type === 'text')
  const imageModels = models.filter((m) => m.status === 'active' && m.model_type === 'image')

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
          <Button variant="default" onClick={onClose}>
            取消
          </Button>
          <Button variant="primary" loading={publish.isPending} disabled={!text || !image} onClick={submit}>
            确认发布
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="文本模型" hint={textModels.length ? undefined : '没有已启用的文本模型'}>
          <select
            value={text}
            onChange={(e) => setText(e.target.value)}
            className={selectCls}
            disabled={textModels.length === 0}
          >
            <option value="">请选择</option>
            {textModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.display_name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="生图模型" hint={imageModels.length ? undefined : '没有已启用的生图模型'}>
          <select
            value={image}
            onChange={(e) => setImage(e.target.value)}
            className={selectCls}
            disabled={imageModels.length === 0}
          >
            <option value="">请选择</option>
            {imageModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.display_name}
              </option>
            ))}
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
  const [q, setQ] = useState('')

  const rows = (connections.data ?? []).filter(
    (c) =>
      !q.trim() ||
      c.display_name.toLowerCase().includes(q.trim().toLowerCase()) ||
      c.slug.toLowerCase().includes(q.trim().toLowerCase()),
  )

  return (
    <Panel
      title="厂商连接"
      desc="维护各模型厂商的接入地址与密钥；密钥仅存密文，展示为掩码"
      bodyClass="p-3"
      action={
        <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
          新建连接
        </Button>
      }
    >
      <Toolbar className="mb-3">
        <Field label="搜索" className="min-w-[200px] flex-1">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="按名称或标识过滤"
            className={inputCls}
          />
        </Field>
        <Button variant="default" size="md" disabled={!q} onClick={() => setQ('')}>
          重置
        </Button>
      </Toolbar>

      {connections.isLoading ? (
        <Loading />
      ) : (connections.data?.length ?? 0) === 0 ? (
        <EmptyState text="尚未维护任何连接" hint="点击右上角「新建连接」接入模型厂商" />
      ) : rows.length === 0 ? (
        <EmptyState text="没有匹配的连接" hint="换个关键词，或点击「重置」" />
      ) : (
        <DataTable
          head={['名称 / 标识', '适配器', '当前版本', 'Base URL', '密钥', '状态', '操作']}
          minWidth={960}
          footer={
            <span>
              共 <span className="text-ad-ink font-ad-mono tabular-nums">{rows.length}</span> 个连接
            </span>
          }
        >
          {rows.map((c) => (
            <tr key={c.id} className={rowCls}>
              <td className={cellCls}>
                <div className="text-ad-ink font-medium">{c.display_name}</div>
                <div className="text-ad-faint font-ad-mono text-[11px]">
                  {c.slug} · {c.vendor}
                </div>
              </td>
              <td className={cellCls}>
                <Tag tone="neutral" mono>
                  {c.adapter_type}
                </Tag>
              </td>
              <td className={`${cellCls} text-ad-muted font-ad-mono text-xs tabular-nums`}>
                {c.current_version_seq != null ? `v${c.current_version_seq}` : '—'}
              </td>
              <td className={`${cellCls} text-ad-muted max-w-[220px] truncate font-ad-mono text-xs`} title={c.base_url}>
                {c.base_url || '—'}
              </td>
              <td className={`${cellCls} text-ad-muted font-ad-mono text-xs`}>{c.key_mask || '—'}</td>
              <td className={cellCls}>
                <Tag tone={c.status === 'active' ? 'success' : 'neutral'}>{c.status}</Tag>
              </td>
              <td className={`${cellCls} text-right`}>
                <Button variant="default" size="xs" onClick={() => setVersionFor(c)}>
                  更新密钥/地址
                </Button>
              </td>
            </tr>
          ))}
        </DataTable>
      )}

      {creating ? (
        <ConnectionDialog
          onClose={() => setCreating(false)}
          onDone={(s) => {
            setCreating(false)
            notify({ tone: 'ok', text: `已创建连接 ${s}` })
          }}
          onError={(e) => notify({ tone: 'err', text: msg(e) })}
        />
      ) : null}
      {versionFor ? (
        <VersionDialog
          conn={versionFor}
          onClose={() => setVersionFor(null)}
          onDone={() => {
            setVersionFor(null)
            notify({ tone: 'ok', text: '已新增连接版本' })
          }}
          onError={(e) => notify({ tone: 'err', text: msg(e) })}
        />
      ) : null}
    </Panel>
  )
}

function ConnectionDialog({
  onClose,
  onDone,
  onError,
}: {
  onClose: () => void
  onDone: (slug: string) => void
  onError: (e: unknown) => void
}) {
  const create = useCreateConnection()
  const [form, setForm] = useState({
    slug: '',
    vendor: '',
    adapter_type: 'dashscope' as AdapterType,
    display_name: '',
    base_url: '',
    api_key: '',
  })
  const set = (k: keyof typeof form, v: string) => setForm({ ...form, [k]: v })
  const submit = () => create.mutate(form, { onSuccess: () => onDone(form.slug), onError })

  return (
    <Modal
      title="新建厂商连接"
      onClose={onClose}
      width="max-w-lg"
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            取消
          </Button>
          <Button
            variant="primary"
            loading={create.isPending}
            disabled={!form.slug || !form.base_url || !form.api_key}
            onClick={submit}
          >
            创建
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="标识 slug" hint="小写字母/数字/-/_">
            <input value={form.slug} onChange={(e) => set('slug', e.target.value)} className={inputCls} placeholder="dashscope-main" autoFocus />
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
            {ADAPTERS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Base URL" hint="生产需 HTTPS；minimax 填到 /v1 即可">
          <input
            value={form.base_url}
            onChange={(e) => set('base_url', e.target.value)}
            className={inputCls}
            placeholder={BASE_URL_PLACEHOLDER[form.adapter_type]}
          />
        </Field>
        <Field label="API Key">
          <input type="password" value={form.api_key} onChange={(e) => set('api_key', e.target.value)} className={inputCls} placeholder="密钥将以密文保存" />
        </Field>
      </div>
    </Modal>
  )
}

function VersionDialog({
  conn,
  onClose,
  onDone,
  onError,
}: {
  conn: Connection
  onClose: () => void
  onDone: () => void
  onError: (e: unknown) => void
}) {
  const addVersion = useAddConnectionVersion()
  const [baseUrl, setBaseUrl] = useState(conn.base_url || '')
  const [apiKey, setApiKey] = useState('')

  const submit = () =>
    addVersion.mutate(
      { id: conn.id, base_url: baseUrl || null, api_key: apiKey || null },
      { onSuccess: onDone, onError },
    )

  return (
    <Modal
      title="更新连接密钥 / 地址"
      desc={`为 ${conn.display_name} 追加一个不可变版本`}
      onClose={onClose}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            取消
          </Button>
          <Button variant="primary" loading={addVersion.isPending} disabled={!baseUrl && !apiKey} onClick={submit}>
            保存新版本
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Base URL" hint="留空则沿用当前">
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} className={inputCls} />
        </Field>
        <Field label="新 API Key" hint="留空则沿用当前">
          <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} className={inputCls} placeholder="当前掩码：****" />
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
  const [type, setType] = useState<'' | ModelType>('')
  const [q, setQ] = useState('')

  const connName = useMemo(() => {
    const m = new Map<string, string>()
    for (const c of connections.data ?? []) m.set(c.id, c.display_name)
    return (id: string) => m.get(id) ?? '—'
  }, [connections.data])

  const all = models.data ?? []
  const rows = all.filter((m) => {
    if (type && m.model_type !== type) return false
    if (!q.trim()) return true
    const k = q.trim().toLowerCase()
    return m.display_name.toLowerCase().includes(k) || m.slug.toLowerCase().includes(k)
  })

  return (
    <Panel
      title="模型清单"
      desc="每类模型可登记多个，但同时只能启用一个；启用新的会自动停用同类旧的"
      bodyClass="p-3"
      action={
        <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
          登记模型
        </Button>
      }
    >
      <Toolbar className="mb-3">
        <Field label="搜索" className="min-w-[200px] flex-1">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="按名称或标识过滤" className={inputCls} />
        </Field>
        <Field label="类型" className="w-40">
          <select value={type} onChange={(e) => setType(e.target.value as '' | ModelType)} className={selectCls}>
            <option value="">全部</option>
            <option value="text">文本模型</option>
            <option value="image">生图模型</option>
          </select>
        </Field>
        <Button
          variant="default"
          size="md"
          disabled={!q && !type}
          onClick={() => {
            setQ('')
            setType('')
          }}
        >
          重置
        </Button>
      </Toolbar>

      {models.isLoading ? (
        <Loading />
      ) : all.length === 0 ? (
        <EmptyState text="尚未登记任何模型" hint="点击右上角「登记模型」添加" />
      ) : rows.length === 0 ? (
        <EmptyState text="没有匹配的模型" hint="换个关键词或类型，或点击「重置」" />
      ) : (
        <DataTable
          head={['名称 / slug', '所属连接', '厂商模型 ID', '类型', '状态', '操作']}
          minWidth={880}
          footer={
            <span>
              共 <span className="text-ad-ink font-ad-mono tabular-nums">{rows.length}</span> 个模型
              <span className="text-ad-faint"> · 已启用 {all.filter((m) => m.status === 'active').length} 个</span>
            </span>
          }
        >
          {rows.map((m) => (
            <tr key={m.id} className={rowCls}>
              <td className={cellCls}>
                <div className="text-ad-ink font-medium">{m.display_name}</div>
                <div className="text-ad-faint font-ad-mono text-[11px]">{m.slug}</div>
              </td>
              <td className={`${cellCls} text-ad-muted text-xs`}>{connName(m.connection_id)}</td>
              <td className={`${cellCls} text-ad-muted font-ad-mono text-xs`}>
                {m.vendor_model_id}
                {m.edit_vendor_model_id ? (
                  <div className="text-ad-faint">编辑：{m.edit_vendor_model_id}</div>
                ) : null}
              </td>
              <td className={cellCls}>
                <Tag tone="brand">{TYPE_LABEL[m.model_type]}</Tag>
              </td>
              <td className={cellCls}>
                <Tag tone={m.status === 'active' ? 'success' : 'neutral'}>
                  {m.status === 'active' ? '已启用' : '已停用'}
                </Tag>
              </td>
              <td className={`${cellCls} text-right`}>
                {m.status === 'active' ? (
                  <Button
                    variant="danger"
                    size="xs"
                    loading={disable.isPending}
                    onClick={() =>
                      disable.mutate(m.id, {
                        onSuccess: () => notify({ tone: 'ok', text: `已停用模型 ${m.display_name}` }),
                        onError: (e) => notify({ tone: 'err', text: msg(e) }),
                      })
                    }
                  >
                    停用
                  </Button>
                ) : (
                  <Button
                    variant="default"
                    size="xs"
                    loading={activate.isPending}
                    onClick={() =>
                      activate.mutate(m.id, {
                        onSuccess: () => notify({ tone: 'ok', text: `已启用模型 ${m.display_name}` }),
                        onError: (e) => notify({ tone: 'err', text: msg(e) }),
                      })
                    }
                  >
                    启用
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </DataTable>
      )}

      {creating ? (
        <ModelDialog
          connections={connections.data ?? []}
          onClose={() => setCreating(false)}
          onDone={(s) => {
            setCreating(false)
            notify({ tone: 'ok', text: `已登记模型 ${s}` })
          }}
          onError={(e) => notify({ tone: 'err', text: msg(e) })}
        />
      ) : null}
    </Panel>
  )
}

function ModelDialog({
  connections,
  onClose,
  onDone,
  onError,
}: {
  connections: Connection[]
  onClose: () => void
  onDone: (slug: string) => void
  onError: (e: unknown) => void
}) {
  const create = useCreateModel()
  const [form, setForm] = useState({
    slug: '',
    connection_id: connections[0]?.id ?? '',
    vendor_model_id: '',
    display_name: '',
  })
  const [modelType, setModelType] = useState<ModelType>('text')
  const [editVendorId, setEditVendorId] = useState('')
  const [effort, setEffort] = useState('')
  const set = (k: keyof typeof form, v: string) => setForm({ ...form, [k]: v })

  const selectedConn = connections.find((c) => c.id === form.connection_id)
  const isMinimax = selectedConn?.adapter_type === 'minimax'
  const minimaxText = isMinimax && modelType === 'text'

  const submit = () =>
    create.mutate(
      {
        ...form,
        model_type: modelType,
        edit_vendor_model_id: modelType === 'image' && editVendorId.trim() ? editVendorId.trim() : null,
        // MiniMax 的思考深度是模型级参数，运行时由 model_runtime 读 param_schema 下发
        param_schema: minimaxText && effort ? { reasoning_effort: effort } : {},
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
          <Button variant="default" onClick={onClose}>
            取消
          </Button>
          <Button
            variant="primary"
            loading={create.isPending}
            disabled={!form.slug || !form.connection_id || !form.vendor_model_id || !form.display_name}
            onClick={submit}
          >
            登记
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="模型类型">
          <div className="flex">
            {MODEL_TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setModelType(t.value)}
                className={`h-8 flex-1 cursor-pointer border text-[13px] transition-colors first:border-r-0 last:border-l-0 ${
                  modelType === t.value
                    ? 'border-ad-primary bg-ad-primary-soft text-ad-primary-dark font-medium'
                    : 'border-ad-border-strong text-ad-muted hover:bg-ad-surface-2'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="标识 slug">
            <input value={form.slug} onChange={(e) => set('slug', e.target.value)} className={inputCls} placeholder="wanx-t2i" autoFocus />
          </Field>
          <Field label="所属连接">
            <select value={form.connection_id} onChange={(e) => set('connection_id', e.target.value)} className={selectCls}>
              {connections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.display_name}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
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
