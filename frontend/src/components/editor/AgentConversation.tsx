import { useEffect, useRef, useState } from 'react'
import type { Turn } from '@/api/agent'
import AgentTaskCard from '@/components/editor/AgentTaskCard'
import AgentTurnResults from '@/components/editor/AgentTurnResults'
import ChatIcon from '@/components/editor/ChatIcon'
import Markdown from '@/components/ui/Markdown'
import { shouldShowTurnTaskCard } from '@/lib/agentPresentation'

export default function AgentConversation({
  sessionId,
  turns,
  loading,
  error,
  onRetry,
  onSuggestion,
  onShowCanvas,
}: {
  sessionId: string
  turns: Turn[]
  loading: boolean
  error: string | null
  onRetry: () => void
  onSuggestion: (text: string) => void
  onShowCanvas: () => void
}) {
  const scroll = useRef<HTMLDivElement>(null)
  const content = useRef<HTMLDivElement>(null)
  const pinned = useRef(true)
  const [hasNew, setHasNew] = useState(false)
  const toBottom = () => {
    const node = scroll.current
    if (node) node.scrollTop = node.scrollHeight
    pinned.current = true
    setHasNew(false)
  }
  useEffect(() => {
    const node = scroll.current
    if (node && pinned.current) node.scrollTop = node.scrollHeight
    else if (node) setHasNew(true)
  }, [turns])
  useEffect(() => {
    const node = content.current
    if (!node) return
    const observer = new ResizeObserver(() => {
      if (pinned.current && scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [loading, error])
  return (
    <div className="agent-conversation-wrap">
      <div
        className="agent-conversation scrollbar-slim"
        ref={scroll}
        aria-label="修图对话记录"
        onScroll={() => {
          const node = scroll.current
          if (!node) return
          pinned.current = node.scrollHeight - node.scrollTop - node.clientHeight < 64
          if (pinned.current) setHasNew(false)
        }}
      >
        <div ref={content}>
          {loading ? (
            <div className="chat-loading" role="status">
              <span className="chat-spinner" />
              正在读取对话…
            </div>
          ) : error ? (
            <div className="chat-error" role="alert">
              <p>{error}</p>
              <button onClick={onRetry}>重新读取对话</button>
            </div>
          ) : turns.length === 0 ? (
            <Welcome onSuggestion={onSuggestion} />
          ) : (
            <>
              <p className="conversation-start">一句话，开始这次创作</p>
              {turns.map((turn, index) => (
                <TurnBlock
                  key={turn.id}
                  turn={turn}
                  sessionId={sessionId}
                  latest={index === turns.length - 1}
                  onSuggestion={onSuggestion}
                  onShowCanvas={onShowCanvas}
                />
              ))}
            </>
          )}
        </div>
      </div>
      {hasNew && (
        <button className="chat-new-message" onClick={toBottom}>
          有新的进展 <ChatIcon name="chevron" />
        </button>
      )}
    </div>
  )
}

function Welcome({ onSuggestion }: { onSuggestion: (text: string) => void }) {
  return (
    <div className="chat-welcome">
      <img src="/illustrations/studio-companion.webp" alt="" />
      <span className="chat-eyebrow">一起，把图片做好。</span>
      <h2>
        想怎么改，
        <br />
        直接告诉我。
      </h2>
      <p>
        换个背景、调整光线，或完成一组修改。
        <br />
        多步任务会先给你方案，确认后再动手。
      </p>
      <button
        onClick={() => onSuggestion('保留商品主体，换成简洁高级的鼠尾草绿背景，光线柔和自然。')}
      >
        <ChatIcon name="spark" />
        <span>给商品换一个高级感场景</span>
        <ChatIcon name="chevron" />
      </button>
      <button onClick={() => onSuggestion('把画面提亮一点，保留自然的颜色与质感。')}>
        <ChatIcon name="image" />
        <span>提亮画面，保留自然质感</span>
        <ChatIcon name="chevron" />
      </button>
    </div>
  )
}

function TurnBlock({
  turn,
  sessionId,
  latest,
  onSuggestion,
  onShowCanvas,
}: {
  turn: Turn
  sessionId: string
  latest: boolean
  onSuggestion: (text: string) => void
  onShowCanvas: () => void
}) {
  const reply = turn.phase === 'planning' ? turn.public_summary : turn.reply
  const meaningfulReply = reply && !/^正在安排[….]*$/.test(reply.trim())
  return (
    <article className="chat-turn" aria-label="一轮修图对话">
      <div className="chat-user-message">{turn.goal}</div>
      <div className="chat-assistant">
        <div className="chat-author">
          <ChatIcon name="spark" />
          <strong>映造助手</strong>
          <span>
            {turn.phase === 'planning'
              ? turn.plan_draft.length > 0
                ? '正在整理方案'
                : '正在理解'
              : turn.phase === 'executing'
                ? '正在创作'
                : '与你一起创作'}
          </span>
        </div>
        {meaningfulReply && <Markdown text={reply} className="chat-reply" />}
        {turn.phase === 'planning' && !meaningfulReply && turn.plan_draft.length === 0 && (
          <p className="chat-thinking" role="status">
            <span className="chat-spinner" />
            正在理解你的需求
          </p>
        )}
        {shouldShowTurnTaskCard(turn) && <AgentTaskCard turn={turn} sessionId={sessionId} />}
        {turn.error && (
          <div className="chat-error" role="alert">
            <ChatIcon name="alert" />
            <span>{turn.error}</span>
          </div>
        )}
        {turn.phase === 'canceled' && (
          <p className="chat-state-note">
            已停止后续处理，已完成的修改保留在画布中。你可以调整需求后继续。
          </p>
        )}
        {turn.phase === 'needs_attention' && (
          <p className="chat-state-note">需要你补充或调整需求。把想改的地方写在下方，我们继续。</p>
        )}
        {(turn.phase === 'completed' || turn.phase === 'failed') && turn.steps.length > 0 && (
          <AgentTurnResults
            turn={turn}
            sessionId={sessionId}
            latest={latest}
            onSuggestion={onSuggestion}
            onShowCanvas={onShowCanvas}
          />
        )}
      </div>
    </article>
  )
}
