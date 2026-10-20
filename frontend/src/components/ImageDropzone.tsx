import { useRef, useState } from 'react'

import { ACCEPTED_TYPES } from '@/api/assets'
import Icon from '@/components/ui/Icon'
import { checkFile } from '@/hooks/useAssets'

type Props = {
  onFile: (file: File) => void
  disabled?: boolean
  hint?: string
  multiple?: boolean
  compact?: boolean
  label?: string
}

export default function ImageDropzone({
  onFile,
  disabled,
  hint,
  multiple,
  compact = false,
  label,
}: Props) {
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
        className={`group flex w-full flex-col items-center justify-center gap-2 rounded-card border border-dashed text-center transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${
          compact ? 'min-h-24 px-4 py-4' : 'px-6 py-10'
        } ${
          dragging
            ? 'border-ai-strong bg-ai-soft'
            : 'border-line-strong bg-panel-2 hover:border-ai-strong hover:bg-ai-soft/50'
        }`}
      >
        <span className="text-ai-strong grid size-9 place-items-center rounded-full bg-ai-soft">
          <Icon name="image-plus" size={18} />
        </span>
        <span className="text-ink text-[13px] font-medium">
          {disabled ? '上传中…' : (label ?? (multiple ? '拖入多张图片，或点击选择' : '拖入图片，或点击选择'))}
        </span>
        <span className="text-muted text-[11px]">{hint ?? 'JPG / PNG / WebP，单张不超过 20 MB'}</span>
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

      {error && <p className="text-danger mt-2 text-xs">{error}</p>}
    </div>
  )
}
