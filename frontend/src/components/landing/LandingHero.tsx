import { useRef, useState } from 'react'

import PromptComposer from './PromptComposer'

const SCENARIOS = [
  {
    label: '商品主图',
    prompt: '把这件商品放在纯白背景上，居中构图，柔和顶光，边缘干净，输出 1:1 主图。',
  },
  {
    label: '场景氛围图',
    prompt: '把商品放到温暖的木质桌面场景，侧逆光、浅景深，保留商品原有材质与颜色。',
  },
  {
    label: '模特上身',
    prompt: '生成模特手持该商品的半身展示图，简洁室内背景、自然光，商品细节清晰可辨。',
  },
  {
    label: '促销海报',
    prompt: '做一张大促海报：主标题「新品首发」，副标题「限时 8 折」，突出商品，右侧留出文字区。',
  },
  {
    label: '多尺寸物料',
    prompt: '基于这张商品图输出一套投放物料，包含 1:1、4:5、9:16 三个尺寸，主体不被裁切。',
  },
]

const FACTS = ['无需设计经验', '支持 JPG / PNG / WebP', '1:1 / 4:5 / 9:16 一次导出']

export default function LandingHero({
  initialPrompt,
  submitLabel,
  onStart,
}: {
  initialPrompt: string
  submitLabel: string
  onStart: (prompt: string) => void
}) {
  const [prompt, setPrompt] = useState(initialPrompt)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const pick = (text: string) => {
    setPrompt(text)
    inputRef.current?.focus()
  }

  return (
    <section className="relative isolate overflow-hidden">
      <div className="bg-glow absolute inset-x-0 -top-24 h-[560px]" aria-hidden />
      <div className="bg-grid absolute inset-x-0 -top-24 h-[560px]" aria-hidden />

      {/* 容器给到 4xl，让 14 字标题在桌面端稳定单行；正文与输入框各自再收窄 */}
      <div className="relative mx-auto max-w-4xl px-6 pt-14 pb-8 text-center sm:pt-20">
        <p
          className="border-line bg-paper/80 text-muted animate-rise inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs backdrop-blur"
          style={{ animationDelay: '40ms' }}
        >
          <span className="bg-accent size-1.5 rounded-full" aria-hidden />
          面向电商运营与内容创作者
        </p>

        <h1
          className="text-ink animate-rise mt-6 text-[2rem] leading-[1.3] font-semibold tracking-tight text-balance sm:text-[2.7rem] lg:text-[3.1rem]"
          style={{ animationDelay: '120ms' }}
        >
          一句话，交付
          <span className="relative mx-1 whitespace-nowrap">
            {/* 高亮衬底置于字身下半部，保留标题清晰度。 */}
            <span
              className="bg-accent/65 absolute inset-x-[-5px] top-[56%] bottom-[3%] -skew-x-6 rounded-[4px]"
              aria-hidden
            />
            <span className="relative">可上架</span>
          </span>
          的商品物料
        </h1>

        <p
          className="text-muted animate-rise mx-auto mt-5 max-w-xl leading-relaxed"
          style={{ animationDelay: '200ms' }}
        >
          描述需求即可从零生成，也可上传商品图继续编辑。抠图、换背景、局部精修、扩图、图层拆分与多尺寸导出，全部由智能体自动编排。
        </p>

        <div className="animate-rise mx-auto mt-9 max-w-3xl" style={{ animationDelay: '280ms' }}>
          <PromptComposer
            value={prompt}
            onChange={setPrompt}
            onSubmit={() => onStart(prompt)}
            onAttach={() => onStart(prompt)}
            submitLabel={submitLabel}
            placeholder="描述你想要的商品图，例：把这双跑鞋放到清晨的城市街道，侧逆光，输出 1:1 主图与 9:16 竖版…"
            inputRef={inputRef}
          />
        </div>

        <div
          className="animate-rise mt-5 flex flex-wrap justify-center gap-2"
          style={{ animationDelay: '360ms' }}
        >
          {SCENARIOS.map((scenario) => (
            <button
              key={scenario.label}
              type="button"
              onClick={() => pick(scenario.prompt)}
              className="border-line bg-paper/80 text-muted hover:border-brand hover:bg-brand-soft hover:text-brand-strong rounded-full border px-3.5 py-2 text-xs transition-colors"
            >
              {scenario.label}
            </button>
          ))}
        </div>

        <ul
          className="text-faint animate-rise mt-7 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs"
          style={{ animationDelay: '440ms' }}
        >
          {FACTS.map((fact) => (
            <li key={fact} className="flex items-center gap-1.5">
              <span className="bg-line-strong size-1 rounded-full" aria-hidden />
              {fact}
            </li>
          ))}
        </ul>
        <div className="studio-story border-line relative mx-auto mt-10 flex min-h-48 max-w-3xl items-center overflow-hidden rounded-panel border text-left sm:mt-12 sm:min-h-56">
          <div className="relative z-1 max-w-[58%] py-6 pl-5 sm:pl-8">
            <p className="text-brand-strong text-[10px] font-semibold tracking-[0.18em]">A LITTLE MAGIC, A LOT OF POSSIBILITY</p>
            <h2 className="text-ink mt-3 text-lg font-semibold tracking-tight sm:text-xl">让灵感，轻松成像。</h2>
            <p className="text-muted mt-2 max-w-64 text-xs leading-relaxed sm:text-sm">从一个想法，到一整套商品物料。<br className="hidden sm:block" />把繁琐留给 AI，把创意留给你。</p>
            <span className="text-brand-strong mt-4 inline-flex items-center gap-1.5 text-[10px] font-medium">
              <span className="bg-brand size-1 rounded-full" aria-hidden /> 你的 AI 创作搭档
            </span>
          </div>
          <img
            src="/illustrations/studio-companion.webp"
            alt=""
            width="640"
            height="640"
            fetchPriority="high"
            className="studio-illustration pointer-events-none absolute right-0 h-52 w-[46%] object-contain mix-blend-multiply sm:-right-2 sm:h-80 sm:w-80"
          />
        </div>
      </div>
    </section>
  )
}