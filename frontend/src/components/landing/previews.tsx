/** 商品摄影用于说明功能，选区、图层与尺寸标记均为装饰性预览。 */
const SCENES = ['0% 0%', '100% 0%', '0% 100%', '100% 100%']

/** 一句话生成：同一件商品的四种场景方向。 */
export function CandidatesPreview() {
  return (
    <div className="grid aspect-square h-full grid-cols-2 gap-2 p-1" aria-hidden>
      {SCENES.map((position, index) => (
        <div
          key={position}
          style={{ backgroundPosition: position }}
          className={`studio-product-photo relative rounded-[10px] ${
            index === 1 ? 'ring-brand ring-2 ring-offset-2 ring-offset-soft' : 'border-line border'
          }`}
        >
          {index === 1 && (
            <span className="bg-brand absolute top-1 right-1 grid size-3.5 place-items-center rounded-full">
              <svg viewBox="0 0 24 24" fill="none" className="size-2">
                <path d="M5 13l4.5 4.5L19 7" stroke="#fff" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

/** 主体级编辑：摄影图上保留清晰可辨的选区与指令。 */
export function SelectionPreview() {
  return (
    <div
      className="studio-product-photo border-line relative aspect-square h-full overflow-hidden rounded-[13px] border"
      style={{ backgroundPosition: '0% 0%' }}
      aria-hidden
    >
      <div className="border-brand absolute top-[29%] left-[26%] h-[46%] w-[62%] rounded-[6px] border-2 border-dashed">
        {['-top-1 -left-1', '-top-1 -right-1', '-bottom-1 -left-1', '-bottom-1 -right-1'].map((pos) => (
          <span key={pos} className={`bg-paper border-brand absolute size-2 rounded-full border-2 ${pos}`} />
        ))}
      </div>
      <p className="bg-ink/90 absolute right-2 bottom-2.5 left-2 rounded-full px-2 py-1.5 text-center text-[9px] text-white">
        把背景换成米色亚麻
      </p>
    </div>
  )
}

const LAYERS = [
  { name: '文字 · 卖点标注', tone: 'bg-accent/70', indent: 'ml-0' },
  { name: '主体 · 商品', tone: 'bg-brand/60', indent: 'ml-2' },
  { name: '背景 · 场景', tone: 'bg-line-strong', indent: 'ml-4' },
]

/** 语义图层：商品画面搭配主体、背景和文字图层示意。 */
export function LayersPreview() {
  return (
    <div className="relative h-full w-full max-w-[270px]" aria-hidden>
      <div
        className="studio-product-photo border-line shadow-control absolute top-0 left-0 size-28 rounded-xl border"
        style={{ backgroundPosition: '0% 100%' }}
      />
      <div className="absolute right-0 bottom-0 w-[185px] max-w-full space-y-1.5">
        {LAYERS.map((layer) => (
          <div
            key={layer.name}
            className={`border-line bg-paper/95 shadow-control flex items-center gap-2 rounded-[10px] border px-2.5 py-2 backdrop-blur-sm ${layer.indent}`}
          >
            <span className={`size-4 shrink-0 rounded-[4px] ${layer.tone}`} />
            <span className="text-muted flex-1 truncate text-[10px]">{layer.name}</span>
            <svg viewBox="0 0 24 24" fill="none" className="text-faint size-3.5 shrink-0">
              <path d="M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z" stroke="currentColor" strokeWidth="1.8" />
              <circle cx="12" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.8" />
            </svg>
          </div>
        ))}
      </div>
    </div>
  )
}

const RATIOS = [
  { label: '1:1', frame: 'h-[62px] w-[62px]' },
  { label: '4:5', frame: 'h-[70px] w-[56px]' },
  { label: '9:16', frame: 'h-[78px] w-[44px]' },
]

/** 物料包交付：居中保留商品，在不同尺寸画框内展示。 */
export function ExportsPreview() {
  return (
    <div className="flex items-end gap-2" aria-hidden>
      {RATIOS.map((ratio) => (
        <div key={ratio.label} className="flex flex-col items-center gap-2">
          <div className={`border-paper bg-[#b2b9a1] shadow-control shrink-0 overflow-hidden rounded-[9px] border-[3px] ${ratio.frame}`}>
            <img src="/illustrations/product-mug.webp" alt="" width="512" height="512" loading="lazy" className="h-full w-full object-contain" />
          </div>
          <span className="text-muted font-mono text-[10px]">{ratio.label}</span>
        </div>
      ))}
    </div>
  )
}
