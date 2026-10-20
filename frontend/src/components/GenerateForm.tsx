import { useRef, useState } from 'react'

import type { Asset } from '@/api/assets'
import { RATIO_LABELS, type GenerateInput, type Ratio } from '@/api/runs'
import ImageDropzone from '@/components/ImageDropzone'
import Icon from '@/components/ui/Icon'
import { buttonClass } from '@/components/ui/buttonStyles'
import { errorMessage } from '@/hooks/useAuth'
import { checkFile, useUploadAsset } from '@/hooks/useAssets'
import { readProjectTitle, saveProjectTitle } from '@/lib/promptDraft'

const RATIOS = Object.keys(RATIO_LABELS) as Ratio[]
const COUNTS = [1, 2, 4, 6]
const MAX_REFS = 3

const CHANNELS: { label: string; hint: string; ratio: Ratio }[] = [
  { label: '商品详情', hint: '1:1 主图', ratio: '1:1' },
  { label: '信息流', hint: '4:5 竖版', ratio: '4:5' },
  { label: '竖版故事', hint: '9:16 长图', ratio: '9:16' },
  { label: '横版广告', hint: '16:9 横图', ratio: '16:9' },
]

const DIRECTIONS: { label: string; prompt: string }[] = [
  {
    label: '纯净棚拍',
    prompt: '纯净棚拍，柔和轮廓光，保留充足留白；商品标签、形状与主色保持准确。',
  },
  {
    label: '自然晨光',
    prompt: '自然晨光，暖石台与少量植物，侧光勾勒商品轮廓，安静高级，避免过度修饰。',
  },
  {
    label: '高级礼赠',
    prompt: '高级礼赠氛围，深色背景，局部金属质感与克制的高光，画面精致但不喧闹。',
  },
]

export default function GenerateForm({
  onSubmit,
  pending,
  defaultPrompt = '',
  onImport,
  importing = false,
}: {
  onSubmit: (input: GenerateInput) => void
  pending: boolean
  defaultPrompt?: string
  onImport?: (file: File) => void
  importing?: boolean
}) {
  const [title, setTitle] = useState(() => readProjectTitle())
  const [mode, setMode] = useState<'asset' | 'prompt'>('asset')
  const [prompt, setPrompt] = useState(defaultPrompt)
  const [ratio, setRatio] = useState<Ratio>('1:1')
  const [count, setCount] = useState(4)
  const [negative, setNegative] = useState('')
  const [advanced, setAdvanced] = useState(false)
  const [refs, setRefs] = useState<Asset[]>([])
  const [refError, setRefError] = useState<string | null>(null)
  const refInput = useRef<HTMLInputElement>(null)
  const upload = useUploadAsset()

  const canSubmit = prompt.trim().length > 0 && !pending
  const channel = CHANNELS.find((item) => item.ratio === ratio)

  const pickDirection = (text: string) => setPrompt(text)

  const addRef = (file: File | undefined) => {
    if (!file) return
    const problem = checkFile(file)
    setRefError(problem)
    if (problem) return
    upload.mutate(file, {
      onSuccess: (asset) =>
        setRefs((current) =>
          current.some((item) => item.id === asset.id) || current.length >= MAX_REFS
            ? current
            : [...current, asset],
        ),
    })
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (!canSubmit) return
        saveProjectTitle(title)
        onSubmit({
          prompt: prompt.trim(),
          ratio,
          count,
          negative_prompt: negative.trim() || undefined,
          reference_asset_ids: refs.length ? refs.map((asset) => asset.id) : undefined,
        })
      }}
      className="border-line bg-panel rounded-card border p-4 sm:p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <label htmlFor="project-title" className="text-muted block text-[10px] tracking-[0.12em]">
            项目名称
          </label>
          <input
            id="project-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="例如：澄野 · 秋季上新"
            className="text-ink placeholder:text-faint focus:border-line-strong mt-1 w-full rounded-none border-b border-transparent bg-transparent pb-1 text-[18px] font-semibold tracking-tight outline-none transition-colors sm:text-[20px]"
          />
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="border-line text-muted inline-flex min-h-8 items-center gap-1.5 rounded-full border px-2.5 text-[11px]">
            <span className="bg-ai size-1.5 rounded-full" aria-hidden />
            阶段 · 视觉方向
          </span>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <div
          className="bg-panel-2 border-line inline-flex rounded-control border p-0.5"
          role="group"
          aria-label="创作起点"
        >
          {[
            { id: 'asset' as const, label: '基于商品图' },
            { id: 'prompt' as const, label: '从描述开始' },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={mode === item.id}
              onClick={() => setMode(item.id)}
              className={`rounded-[7px] px-3 py-1.5 text-[11px] font-medium transition-colors duration-150 ${
                mode === item.id
                  ? 'bg-panel text-ink shadow-control'
                  : 'text-muted hover:text-ink'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <p className="text-faint text-[11px]">
          {mode === 'asset' ? '可上传原片直接精修，也可以只写方向生成新图' : '不需要素材，直接描述画面'}
        </p>
      </div>

      <div
        className={`mt-4 grid gap-3 ${mode === 'asset' ? 'md:grid-cols-[188px_minmax(0,1fr)]' : ''}`}
      >
        {mode === 'asset' && onImport && (
          <ImageDropzone
            compact
            label="导入原片"
            hint="上传后直接进入编辑室"
            disabled={importing}
            onFile={onImport}
          />
        )}

        <div className="border-line bg-panel-2 rounded-control border p-3">
          <label htmlFor="project-brief" className="text-muted block text-[10px] tracking-[0.12em]">
            视觉方向描述
          </label>
          <textarea
            id="project-brief"
            rows={4}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }}
            placeholder="例如：为植物精华制作一组秋季上新物料，暖石台、自然侧光，商品标签与瓶身颜色保持准确。"
            className="text-ink placeholder:text-faint mt-1 w-full resize-none bg-transparent text-[14px] leading-relaxed outline-none"
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {DIRECTIONS.map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => pickDirection(item.prompt)}
                aria-pressed={prompt === item.prompt}
                className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors duration-150 ${
                  prompt === item.prompt
                    ? 'border-ai-strong bg-ai-soft text-brand-strong'
                    : 'border-line text-muted hover:border-ai-strong hover:text-ink'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="border-line mt-4 border-t pt-4">
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted text-[11px] font-medium">投放渠道</span>
          <span className="text-faint text-[10px]">决定本次主比例，其他尺寸在交付中心补齐</span>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {CHANNELS.map((item) => {
            const active = channel?.label === item.label
            return (
              <button
                key={item.label}
                type="button"
                aria-pressed={active}
                onClick={() => setRatio(item.ratio)}
                className={`rounded-control flex min-h-11 items-center justify-between gap-2 border px-3 text-left transition-colors duration-150 ${
                  active
                    ? 'border-shell bg-shell text-shell-ink'
                    : 'border-line bg-panel text-ink hover:border-line-strong'
                }`}
              >
                <span className="text-[12px] font-medium">{item.label}</span>
                <span className={`num text-[10px] ${active ? 'text-signal' : 'text-faint'}`}>
                  {item.hint}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <span className="text-muted text-[11px] font-medium">画面比例</span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {RATIOS.map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={ratio === value}
                onClick={() => setRatio(value)}
                className={`num rounded-chip min-h-9 border px-2.5 text-[11px] transition-colors duration-150 ${
                  ratio === value
                    ? 'border-ai-strong bg-ai-soft text-brand-strong'
                    : 'border-line text-muted hover:text-ink'
                }`}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
        <div>
          <span className="text-muted text-[11px] font-medium">候选数量</span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {COUNTS.map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={count === value}
                onClick={() => setCount(value)}
                className={`num rounded-chip min-h-9 border px-3 text-[11px] transition-colors duration-150 ${
                  count === value
                    ? 'border-ai-strong bg-ai-soft text-brand-strong'
                    : 'border-line text-muted hover:text-ink'
                }`}
              >
                {value} 张
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="border-line mt-4 flex flex-wrap items-center gap-2 border-t pt-4">
        <span className="text-muted text-[11px] font-medium">风格参考</span>
        {refs.map((asset) => (
          <span key={asset.id} className="group relative">
            <img
              src={asset.url}
              alt="风格参考"
              className="border-line size-10 rounded-chip border object-cover"
            />
            <button
              type="button"
              onClick={() => setRefs((current) => current.filter((item) => item.id !== asset.id))}
              aria-label="移除参考图"
              className="bg-shell text-shell-ink absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-full opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
            >
              <Icon name="x" size={11} />
            </button>
          </span>
        ))}
        <button
          type="button"
          onClick={() => refInput.current?.click()}
          disabled={upload.isPending || refs.length >= MAX_REFS}
          className="border-line text-muted hover:border-ai-strong hover:text-ink rounded-chip flex min-h-9 items-center gap-1.5 border border-dashed px-2.5 text-[11px] transition-colors disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Icon name={upload.isPending ? 'loader' : 'plus'} size={13} className={upload.isPending ? 'animate-spin' : ''} />
          {upload.isPending ? '上传中' : '添加参考图'}
        </button>
        <span className="text-faint text-[10px]">可选，最多 {MAX_REFS} 张</span>
        <input
          ref={refInput}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          hidden
          onChange={(event) => {
            addRef(event.target.files?.[0])
            event.target.value = ''
          }}
        />
        {(refError || upload.isError) && (
          <p className="text-danger w-full text-[11px]">
            {refError ?? errorMessage(upload.error)}
          </p>
        )}
      </div>

      {advanced && (
        <div className="border-line animate-fade-in mt-3 border-t pt-3">
          <input
            value={negative}
            onChange={(event) => setNegative(event.target.value)}
            placeholder="不希望出现的内容，例如：文字、水印、多余的手"
            aria-label="排除项"
            className="border-line text-ink placeholder:text-faint rounded-control focus:border-line-strong w-full border bg-transparent px-3 py-2 text-xs outline-none"
          />
        </div>
      )}

      <div className="border-line mt-4 flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setAdvanced((open) => !open)}
            className="text-muted hover:text-ink inline-flex items-center gap-1 text-[11px] transition-colors"
          >
            <Icon name={advanced ? 'chevron-up' : 'chevron-down'} size={13} />
            {advanced ? '收起排除项' : '排除项'}
          </button>
          <span className="text-faint text-[10px]">生成后进入候选筛选 · 不会覆盖已有素材</span>
        </div>
        <button
          type="submit"
          disabled={!canSubmit}
          className={`${buttonClass({ variant: 'signal', size: 'lg' })} inline-flex items-center gap-2 px-4`}
        >
          <Icon name={pending ? 'loader' : 'sparkles'} size={16} className={pending ? 'animate-spin' : ''} />
          {pending ? '提交中…' : '生成视觉方向'}
        </button>
      </div>
    </form>
  )
}
