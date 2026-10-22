import { useNavigate } from 'react-router-dom'

import AssetLibrary from '@/components/AssetLibrary'
import GenerateForm from '@/components/GenerateForm'
import ImageDropzone from '@/components/ImageDropzone'
import { errorMessage } from '@/hooks/useAuth'
import { useAssetLibrary, useUploadAsset } from '@/hooks/useAssets'
import { useGenerate } from '@/hooks/useRun'
import { useCreateSession } from '@/hooks/useSessions'
import { readPromptDraft, savePromptDraft } from '@/lib/promptDraft'
import { useRateLimit } from '@/stores/rateLimit'

export default function CreatePage() {
  const navigate = useNavigate()
  const { data: groups = [], isPending } = useAssetLibrary()
  const upload = useUploadAsset()
  const generate = useGenerate()
  const generateRateLimit = useRateLimit('generate')
  const createSession = useCreateSession()

  const openEditor = (assetId: string) =>
    createSession.mutate(
      { current_asset_id: assetId },
      { onSuccess: (session) => navigate(`/editor/${session.id}`) },
    )

  return (
    <div className="mx-auto max-w-4xl px-5 py-8 sm:px-8 sm:py-10">
      <header className="border-line mb-8 flex items-center justify-between gap-5 border-b pb-7">
        <div>
          <p className="text-brand-strong mb-3 text-[10px] font-semibold tracking-[0.2em]">CREATIVE STUDIO</p>
          <h1 className="text-ink text-3xl font-semibold tracking-tight">创作</h1>
          <p className="text-muted mt-3 text-sm leading-6">从一个想法开始，让画面慢慢成形。</p>
        </div>
        <img
          src="/illustrations/studio-companion.webp"
          alt=""
          width={128}
          height={128}
          className="studio-illustration pointer-events-none hidden h-32 w-32 shrink-0 mix-blend-multiply select-none sm:block"
        />
      </header>

      <div className="mb-3 flex items-center gap-3">
        <span className="bg-brand-soft text-brand-strong flex h-6 w-6 items-center justify-center rounded-lg text-[10px] font-semibold" aria-hidden>01</span>
        <h2 className="text-ink text-sm font-semibold">描述你的画面</h2>
        <span className="text-faint ml-auto hidden text-xs sm:block">让一句话，成为一张图</span>
      </div>
      <GenerateForm
        defaultPrompt={readPromptDraft()}
        pending={generate.isPending}
        rateLimitedSeconds={generateRateLimit}
        onSubmit={(input) =>
          generate.mutate(input, {
            onSuccess: (run) => {
              savePromptDraft('')
              navigate(`/candidates/${run.id}`)
            },
          })
        }
      />
      {generate.isError && (
        <p className="text-danger mt-2 text-sm">{errorMessage(generate.error)}</p>
      )}

      <section className="mt-9">
        <div className="mb-3 flex items-center gap-3">
          <span className="bg-brand-soft text-brand-strong flex h-6 w-6 items-center justify-center rounded-lg text-[10px] font-semibold" aria-hidden>02</span>
          <h2 className="text-ink text-sm font-semibold">上传已有图片</h2>
          <span className="text-faint ml-auto hidden text-xs sm:block">已有好素材？接着修</span>
        </div>
        <ImageDropzone
          onFile={(file) =>
            upload.mutate(file, { onSuccess: (asset) => openEditor(asset.id) })
          }
          disabled={upload.isPending || createSession.isPending}
        />
        {upload.isError && (
          <p className="text-danger mt-2 text-sm">{errorMessage(upload.error)}</p>
        )}
      </section>

      <section className="mt-9">
        <div className="mb-4 flex items-center gap-3">
          <span className="bg-soft text-muted border-line flex h-6 w-6 items-center justify-center rounded-lg border text-[10px] font-semibold" aria-hidden>03</span>
          <h2 className="text-ink text-sm font-semibold">历史素材</h2>
          <span className="text-faint ml-auto hidden text-xs sm:block">每一次创作，都留在这里</span>
        </div>

        {isPending ? (
          <p className="border-line bg-paper/60 rounded-card text-muted border px-6 py-8 text-sm" role="status">加载中…</p>
        ) : groups.length === 0 ? (
          <div className="border-line bg-paper/60 rounded-card flex items-center gap-4 border px-5 py-7 sm:px-6">
            <span className="bg-brand-soft text-brand-strong flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl" aria-hidden>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="4" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <path d="m4 17 5-5 4 4 3-3 5 5" />
              </svg>
            </span>
            <div>
              <p className="text-ink text-sm font-medium">你的作品集，从这里开始</p>
              <p className="text-muted mt-1.5 text-xs leading-6">还没有素材，先描述画面或上传一张图片。</p>
            </div>
          </div>
        ) : (
          <AssetLibrary
            groups={groups}
            onOpenSession={(sessionId) => navigate(`/editor/${sessionId}`)}
            onOpenAsset={openEditor}
          />
        )}
      </section>
    </div>
  )
}
