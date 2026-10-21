import { useState } from 'react'

import Button from '@/components/ui/Button'
import { formatResetAt, useEntitlements } from '@/hooks/useQuota'

export default function MessageComposer({
  pending,
  error,
  placeholder = '说明要怎么改，例如：去背景、水平翻转。回车发送',
  onSend,
}: {
  pending: boolean
  error?: string | null
  placeholder?: string
  onSend: (text: string) => void
}) {
  const [text, setText] = useState('')
  const entitlements = useEntitlements()
  const empty = entitlements.data?.available === 0
  const canSend = text.trim().length > 0 && !pending

  const submit = () => {
    if (!canSend) return
    onSend(text.trim())
    setText('')
  }

  return (
    <div className="border-line shrink-0 border-t p-3">
      <textarea
        rows={2}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            submit()
          }
        }}
        placeholder={placeholder}
        aria-label="修图指令"
        className="border-line text-ink placeholder:text-faint rounded-control focus:border-line-strong w-full resize-none border px-3 py-2 text-xs leading-relaxed outline-none transition-colors"
      />
      <div className="mt-1.5 flex items-center justify-between gap-2 text-[10px]">
        <span className="text-faint">每成功生成 1 张消耗 1 次</span>
        <span className={empty ? 'text-danger' : 'text-muted'}>
          {empty
            ? `${formatResetAt(entitlements.data)}后恢复`
            : `今日剩余 ${entitlements.data?.available ?? '—'} 次`}
        </span>
      </div>
      <Button variant="solid" block className="mt-2 py-2" disabled={!canSend} onClick={submit}>
        {pending ? '思考中…' : '发送'}
      </Button>
      {error && <p className="text-danger mt-2 text-[11px] leading-relaxed">{error}</p>}
    </div>
  )
}
