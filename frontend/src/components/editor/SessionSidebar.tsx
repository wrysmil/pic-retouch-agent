import { useRef, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import AgentConversation from '@/components/editor/AgentConversation'
import ChatIcon from '@/components/editor/ChatIcon'
import MessageComposer from '@/components/editor/MessageComposer'
import { useSendMessage, useTurns } from '@/hooks/useAgent'
import { errorMessage } from '@/hooks/useAuth'
import { useSession, useSessions } from '@/hooks/useSessions'
import { hasOpenTurn } from '@/lib/agentPresentation'
import { formatDateTime } from '@/lib/format'
import { useRateLimit } from '@/stores/rateLimit'

export default function SessionSidebar({
  activeId,
  onShowCanvas,
}: {
  activeId: string
  onShowCanvas: () => void
}) {
  const [historyOpen, setHistoryOpen] = useState(false)
  return (
    <aside className="session-sidebar" id="editor-conversation" aria-label="AI 修图助手">
      <header className="chat-sidebar-header">
        <div className="chat-ai-avatar">
          <ChatIcon name="spark" />
        </div>
        <div>
          <h1>
            映造助手 <span>AI</span>
          </h1>
          <p>你的想法，我们一起实现。</p>
        </div>
        <Link className="chat-header-button" to="/create" aria-label="新对话" title="新对话">
          <ChatIcon name="plus" />
        </Link>
        <button
          className={`chat-header-button ${historyOpen ? 'active' : ''}`}
          aria-label="历史对话"
          aria-expanded={historyOpen}
          aria-controls="chat-history"
          title="历史对话"
          onClick={() => setHistoryOpen((open) => !open)}
        >
          <ChatIcon name="history" />
        </button>
      </header>
      {historyOpen && <SessionList activeId={activeId} onPick={() => setHistoryOpen(false)} />}
      {activeId ? (
        <Conversation key={activeId} sessionId={activeId} onShowCanvas={onShowCanvas} />
      ) : (
        <p className="chat-state-note">打开一个历史对话，或回到创作页开始新的一张。</p>
      )}
    </aside>
  )
}

function Conversation({
  sessionId,
  onShowCanvas,
}: {
  sessionId: string
  onShowCanvas: () => void
}) {
  const send = useSendMessage(sessionId)
  const turns = useTurns(sessionId)
  const rateLimitSeconds = useRateLimit('agent-plan')
  const { data: session } = useSession(sessionId)
  const [draft, setDraft] = useState('')
  const root = useRef<HTMLDivElement>(null)
  const planActive = hasOpenTurn(turns.data ?? [])
  const suggest = (text: string) => {
    setDraft((previous) =>
      previous.trim() ? `${previous.trimEnd()}\n${text}`.slice(0, 1000) : text,
    )
    requestAnimationFrame(() => root.current?.querySelector('textarea')?.focus())
  }
  return (
    <div className="chat-session" ref={root}>
      <AgentConversation
        sessionId={sessionId}
        turns={turns.data ?? []}
        loading={turns.isPending}
        error={turns.isError ? errorMessage(turns.error) : null}
        onRetry={() => {
          void turns.refetch()
        }}
        onSuggestion={suggest}
        onShowCanvas={onShowCanvas}
      />
      <MessageComposer
        session={session}
        pending={
          send.isPending || planActive || turns.isPending || turns.isError || rateLimitSeconds > 0
        }
        error={
          send.isError
            ? `${errorMessage(send.error)}${
                rateLimitSeconds > 0 ? ` · ${rateLimitSeconds} 秒后可重试` : ''
              }`
            : null
        }
        value={draft}
        onChange={setDraft}
        onSuggestion={suggest}
        onSend={(text) => send.mutateAsync(text)}
      />
    </div>
  )
}

function SessionList({ activeId, onPick }: { activeId: string; onPick: () => void }) {
  const { data: sessions = [], isPending, isError } = useSessions()
  return (
    <div className="chat-history scrollbar-slim" id="chat-history">
      <div className="chat-history-title">最近的对话</div>
      {isPending ? (
        <p>加载中…</p>
      ) : isError ? (
        <p role="alert">历史对话读取失败，请稍后重试。</p>
      ) : sessions.length === 0 ? (
        <p>还没有会话</p>
      ) : (
        <ul>
          {sessions.map((session) => (
            <li key={session.id}>
              <NavLink
                onClick={onPick}
                to={`/editor/${session.id}`}
                className={session.id === activeId ? 'active' : ''}
              >
                <strong>{session.title}</strong>
                <small>{formatDateTime(session.updated_at)}</small>
              </NavLink>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
