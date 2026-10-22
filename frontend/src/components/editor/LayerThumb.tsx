import type { Layer } from '@/api/sessions'

export default function LayerThumb({ layer, src }: { layer: Layer; src?: string }) {
  if (src) {
    return <img src={src} alt="" className="size-full object-cover" draggable={false} />
  }
  return (
    <span className="text-faint grid size-full place-items-center text-[10px]" aria-hidden>
      {layer.kind === 'text' ? '文' : layer.kind === 'shape' ? '形' : layer.locked ? '锁' : '图'}
    </span>
  )
}
