import { useRef, useState } from 'react'

import { ACCEPTED_TYPES } from '@/api/assets'
import { checkFile } from '@/hooks/useAssets'

type Props = {
  onFile: (file: File) => void
  disabled?: boolean
  hint?: string
  multiple?: boolean
}

export default function ImageDropzone({ onFile, disabled, hint, multiple }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const accept = (file: File | undefined) => {
    if (!file) return
    const problem = checkFile(file)
    setError(problem)
    if (!problem) onFile(file)
  }

  return (
    <div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          const files = Array.from(event.dataTransfer.files)
          if (multiple) files.forEach((file) => accept(file))
          else accept(files[0])
        }}
        className={`flex w-full flex-col items-center gap-1.5 rounded-[18px] border border-dashed px-6 py-10 transition-colors disabled:opacity-50 ${
          dragging ? 'border-brand bg-brand-soft' : 'border-line-strong bg-paper/80 hover:border-brand hover:bg-brand-soft/40'
        }`}
      >
        <span className="border-line bg-soft text-brand-strong mb-2 grid size-11 place-items-center rounded-2xl border" aria-hidden>
          <svg viewBox="0 0 24 24" fill="none" className="size-5">
            <rect x="3" y="4" width="18" height="16" rx="3" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="8" cy="9" r="1.5" fill="currentColor" />
            <path d="m4 17 5-5 4 4 3-3 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <span className="text-ink text-sm font-medium">
          {disabled ? '上传中…' : multiple ? '拖入多张图片，或点击选择' : '拖入图片，或点击选择'}
        </span>
        <span className="text-faint text-xs">
          {hint ?? 'JPG / PNG / WebP，单张不超过 20 MB，大图会自动压缩'}
        </span>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES.join(',')}
        multiple={multiple}
        hidden
        onChange={(event) => {
          const files = Array.from(event.target.files ?? [])
          if (multiple) files.forEach((file) => accept(file))
          else accept(files[0])
          event.target.value = ''
        }}
      />

      {error && <p className="text-danger mt-2 text-sm">{error}</p>}
    </div>
  )
}