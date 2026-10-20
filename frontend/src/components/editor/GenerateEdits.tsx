import { useState } from 'react'

import type { Ratio } from '@/api/runs'
import Button from '@/components/ui/Button'
import Icon from '@/components/ui/Icon'

const RATIOS: { value: Ratio; label: string }[] = [
  { value: '1:1', label: '1:1' },
  { value: '4:5', label: '4:5' },
  { value: '3:4', label: '3:4' },
  { value: '9:16', label: '9:16' },
  { value: '16:9', label: '16:9' },
]

const FIELD =
  'border-shell-line bg-shell-3 text-shell-ink placeholder:text-shell-muted focus:border-ai/60 w-full resize-none rounded-control border px-3 py-2 text-[11px] leading-relaxed outline-none transition-colors duration-150'

export function BackgroundForm({
  disabled,
  wallOnly,
  onApply,
}: {
  disabled: boolean
  wallOnly: boolean
  onApply: (params: { prompt: string; count: number }) => void
}) {
  const [prompt, setPrompt] = useState('')
  const [count, setCount] = useState(1)
  const ready = prompt.trim().length > 0

  return (
    <section className="border-shell-line border-b px-4 py-4">
      <PaneTitle icon="image" title="换背景" />
      <p className="mb-2.5 text-[10px] leading-relaxed text-shell-muted">
        {wallOnly
          ? '写出新背景。已拆层，结果拍平成整图只进图片墙，点选采用；画布与图层保持不变。'
          : '写出新背景。一张直接上画布；多张进图片墙，点选采用。'}
      </p>
      <textarea
        rows={3}
        value={prompt}
        disabled={disabled}
        onChange={(event) => setPrompt(event.target.value)}
        placeholder="例如：浅木色桌面，晨光从左侧照入"
        className={FIELD}
      />
      <div className="mt-2 flex gap-1">
        {[1, 2, 4].map((value) => (
          <Button
            key={value}
            variant="outline"
            size="sm"
            tone="dark"
            block
            active={count === value}
            disabled={disabled}
            onClick={() => setCount(value)}
          >
            {value} 张
          </Button>
        ))}
      </div>
      <Button
        variant="signal"
        size="md"
        tone="dark"
        block
        className="mt-3"
        disabled={disabled || !ready}
        onClick={() => {
          onApply({ prompt: prompt.trim(), count })
          setPrompt('')
        }}
      >
        生成
      </Button>
    </section>
  )
}

export function ExpandForm({
  disabled,
  wallOnly,
  onApply,
}: {
  disabled: boolean
  wallOnly: boolean
  onApply: (params: { ratio: Ratio }) => void
}) {
  const [ratio, setRatio] = useState<Ratio>('16:9')

  return (
    <section className="border-shell-line border-b px-4 py-4">
      <PaneTitle icon="ratio" title="扩图" />
      <p className="mb-2.5 text-[10px] leading-relaxed text-shell-muted">
        {wallOnly
          ? '扩展到目标比例，主体保留在画面中。已拆层，结果只进图片墙，点选采用；画布与图层保持不变。'
          : '扩展到目标比例，主体保留在画面中，完成后写回画布。'}
      </p>
      <div className="grid grid-cols-5 gap-1">
        {RATIOS.map((item) => (
          <Button
            key={item.value}
            variant="outline"
            size="sm"
            tone="dark"
            block
            active={ratio === item.value}
            disabled={disabled}
            onClick={() => setRatio(item.value)}
          >
            {item.label}
          </Button>
        ))}
      </div>
      <Button
        variant="signal"
        size="md"
        tone="dark"
        block
        className="mt-3"
        disabled={disabled}
        onClick={() => onApply({ ratio })}
      >
        扩展画布
      </Button>
    </section>
  )
}

export function ReplaceForm({
  disabled,
  onApply,
}: {
  disabled: boolean
  onApply: (params: { prompt: string }) => void
}) {
  const [prompt, setPrompt] = useState('')
  const ready = prompt.trim().length > 0

  return (
    <section className="border-shell-line border-b px-4 py-4">
      <PaneTitle icon="box-select" title="局部替换" />
      <p className="mb-2.5 text-[10px] leading-relaxed text-shell-muted">
        只改当前选区。选区外的画面会保持不动。
      </p>
      <textarea
        rows={3}
        value={prompt}
        disabled={disabled}
        onChange={(event) => setPrompt(event.target.value)}
        placeholder="例如：把杯子换成陶瓷马克杯"
        className={FIELD}
      />
      <Button
        variant="signal"
        size="md"
        tone="dark"
        block
        className="mt-3"
        disabled={disabled || !ready}
        onClick={() => {
          onApply({ prompt: prompt.trim() })
          setPrompt('')
        }}
      >
        替换选区
      </Button>
    </section>
  )
}

function PaneTitle({ icon, title }: { icon: 'image' | 'ratio' | 'box-select'; title: string }) {
  return (
    <h2 className="mb-2 flex items-center gap-1.5 text-[11px] font-medium text-shell-ink">
      <Icon name={icon} size={13} className="text-ai" />
      {title}
    </h2>
  )
}
