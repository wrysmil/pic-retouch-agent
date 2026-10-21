import { useQueries } from '@tanstack/react-query'
import type { Turn } from '@/api/agent'
import { runsApi } from '@/api/runs'
import ChatIcon from '@/components/editor/ChatIcon'
import { errorMessage } from '@/hooks/useAuth'
import { usePatchSession, useSession } from '@/hooks/useSessions'
import { collectTurnImages } from '@/lib/agentPresentation'
import { useEditorUi } from '@/stores/editorUi'
import { toast } from '@/stores/toasts'

export default function AgentTurnResults({
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
  const { data: session } = useSession(sessionId)
  const patch = usePatchSession(sessionId)
  const runs = useQueries({
    queries: turn.steps
      .filter((step) => step.run_id && step.status === 'succeeded')
      .map((step) => ({
        queryKey: ['run', step.run_id],
        queryFn: () => runsApi.get(step.run_id!),
        staleTime: 30_000,
      })),
  })
  const images = collectTurnImages(
    runs.flatMap((run) => (run.data ? [run.data] : [])),
    session?.assets ?? [],
  )
  const setCompareOpen = useEditorUi((state) => state.setCompareOpen)
  const view = (id: string) => {
    if (!session) return
    setCompareOpen(false)
    if (session.current_asset_id === id) onShowCanvas()
    else
      patch.mutate(
        { current_asset_id: id },
        { onSuccess: onShowCanvas, onError: (error) => toast(errorMessage(error), 'danger') },
      )
  }
  const canCompare = latest && Boolean(session?.previous_document) && turn.phase === 'completed'
  return (
    <div className="chat-turn-results">
      {images.length > 0 && (
        <>
          <p>
            {turn.phase === 'completed' ? '图片已就绪，看看这个方向。' : '已完成的图片保留在这里。'}
          </p>
          <div className="chat-result-grid">
            {images.map((asset, index) => (
              <button
                key={asset.id}
                className="chat-result-preview"
                disabled={patch.isPending}
                onClick={() => view(asset.id)}
              >
                <img src={asset.url} alt={`本轮处理结果 ${index + 1}`} loading="lazy" />
                <span>
                  <strong>{images.length > 1 ? `处理结果 ${index + 1}` : '本次处理结果'}</strong>
                  <small>
                    {asset.width} × {asset.height} · {asset.image_format.toUpperCase()}
                  </small>
                  <em>
                    在画布中查看 <ChatIcon name="chevron" />
                  </em>
                </span>
              </button>
            ))}
          </div>
        </>
      )}
      {latest && turn.phase === 'completed' && (
        <div className="chat-result-actions">
          <button
            onClick={() => {
              setCompareOpen(false)
              onShowCanvas()
            }}
          >
            <ChatIcon name="image" />
            查看当前画布
          </button>
          {canCompare && (
            <button
              onClick={() => {
                setCompareOpen(true)
                onShowCanvas()
              }}
            >
              <ChatIcon name="compare" />
              与上一版对比
            </button>
          )}
          <button onClick={() => onSuggestion('在当前效果上继续调整：')}>
            <ChatIcon name="spark" />
            继续微调
          </button>
        </div>
      )}
    </div>
  )
}
