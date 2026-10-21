import { useLayoutEffect, useRef, useState } from 'react'
import type { SessionDetail } from '@/api/sessions'
import ChatIcon from '@/components/editor/ChatIcon'
import { formatResetAt, useEntitlements } from '@/hooks/useQuota'

export default function MessageComposer({
  pending,
  error,
  session,
  value,
  onChange,
  onSuggestion,
  onSend,
}: {
  pending: boolean
  error?: string | null
  session?: SessionDetail
  value: string
  onChange: (text: string) => void
  onSuggestion: (text: string) => void
  onSend: (text: string) => Promise<unknown>
}) {
  const entitlements = useEntitlements()
  const empty = entitlements.data?.available === 0
  const current = session?.assets.find((asset) => asset.id === session.current_asset_id)
  const [failedContextUrl, setFailedContextUrl] = useState<string | null>(null)
  const contextImageFailed = Boolean(current && failedContextUrl === current.url)
  const sending = useRef(false)
  const latestValue = useRef(value)
  useLayoutEffect(() => {
    latestValue.current = value
  }, [value])
  const [submitting, setSubmitting] = useState(false)
  const canSend = value.trim().length > 0 && !pending && !submitting && Boolean(session)
  const submit = async () => {
    if (!canSend || sending.current) return
    sending.current = true
    setSubmitting(true)
    const submitted = value
    try {
      await onSend(submitted.trim())
      // 请求期间仍可编辑下一条；只清除已经提交的那份草稿。
      if (latestValue.current === submitted) onChange('')
    } catch {
      // 错误由调用方展示，原草稿留在输入框中供用户修改或重试。
    } finally {
      sending.current = false
      setSubmitting(false)
    }
  }
  return (
    <div className="chat-composer-area">
      <div className="chat-suggestions" aria-label="快捷修改建议">
        {[
          ['背景暖一点', '把背景调整为温暖的奶油色，保留商品主体。'],
          ['光影更柔和', '让光影更柔和一些，保留自然的立体感。'],
          ['试试其他场景', '保留商品主体，试试另一种背景场景。'],
        ].map(([label, prompt]) => (
          <button type="button" key={label} onClick={() => onSuggestion(prompt)}>
            {label}
          </button>
        ))}
      </div>
      <form
        className="chat-composer"
        aria-label="发送修图需求"
        onSubmit={(event) => {
          event.preventDefault()
          void submit()
        }}
      >
        <div className="chat-context">
          {current && !contextImageFailed ? (
            <img
              src={current.url}
              alt="当前编辑图片"
              onError={() => setFailedContextUrl(current.url)}
            />
          ) : (
            <span className="chat-context-fallback" aria-hidden="true">
              <ChatIcon name={current ? 'alert' : 'image'} />
            </span>
          )}
          <span>
            {contextImageFailed ? (
              <>
                当前图片加载失败，<strong>请从素材栏切换</strong>
              </>
            ) : (
              <>
                正在编辑 <strong>{session?.title || '当前图片'}</strong>
              </>
            )}
          </span>
          {current && (
            <small>
              {contextImageFailed ? '加载失败' : `${current.width} × ${current.height}`}
            </small>
          )}
        </div>
        <textarea
          aria-label="修图指令"
          aria-describedby="chat-input-hint"
          rows={2}
          maxLength={1000}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault()
              void submit()
            }
          }}
          placeholder={
            pending ? '可以先写下一步，当前任务结束后再发送…' : '想怎么改？试试「背景再暖一点」'
          }
        />
        <div className="chat-composer-actions">
          <span id="chat-input-hint">
            {pending ? '先确认、取消或等待当前任务结束' : 'Enter 发送 · Shift + Enter 换行'}
          </span>
          <button
            type="submit"
            className="chat-send"
            disabled={!canSend}
            aria-label="发送修图需求"
            title={pending ? '当前任务结束后可发送' : '发送修图需求'}
          >
            {submitting ? <span className="chat-spinner" /> : <ChatIcon name="arrow" />}
          </button>
        </div>
      </form>
      <div className="chat-quota">
        <span className={empty ? 'text-danger' : ''}>
          {empty ? (
            `${formatResetAt(entitlements.data)}后恢复`
          ) : (
            <>
              今日剩余 <strong>{entitlements.data?.available ?? '—'}</strong> 次
            </>
          )}
        </span>
        <span>成功生成后扣除</span>
      </div>
      {error && (
        <p className="chat-action-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
