import type { ReactNode } from 'react'

import { CandidatesPreview, ExportsPreview, LayersPreview, SelectionPreview } from './previews'

const CAPABILITIES: { title: string; desc: string; preview: ReactNode }[] = [
  {
    title: '一句话生成',
    desc: '无需上传图片，描述需求即可拿到 4 个候选方向，挑中的那张直接进入编辑。',
    preview: <CandidatesPreview />,
  },
  {
    title: '主体级编辑',
    desc: '点选画面里的任意物体后再下指令，改动被约束在选区内，不会外溢到其他区域。',
    preview: <SelectionPreview />,
  },
  {
    title: '语义图层',
    desc: '主体、背景、文字自动分层，任意物体也可按需独立成层，随时回到上一版重做。',
    preview: <LayersPreview />,
  },
  {
    title: '物料包交付',
    desc: '卖点标注与 1:1、4:5、9:16 尺寸一次导出，主体不裁切，直接上架投放。',
    preview: <ExportsPreview />,
  },
]

export default function CapabilityShowcase() {
  return (
    <section className="mx-auto max-w-5xl px-6 pt-12 pb-16">
      <header className="max-w-xl">
        <p className="text-brand-strong text-xs font-semibold tracking-[0.16em]">能力</p>
        <h2 className="text-ink mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
          不只是生成一张好看的图
        </h2>
        <p className="text-muted mt-3 leading-relaxed">
          从候选方向到局部精修，再到分层与多尺寸交付，整条链路都在同一个工作台里完成。
        </p>
      </header>

      <div className="mt-10 grid gap-5 sm:grid-cols-2">
        {CAPABILITIES.map((item, index) => (
          <article
            key={item.title}
            className="studio-feature border-line bg-paper rounded-card shadow-card hover:shadow-lift border p-5 transition-shadow duration-300 sm:p-6"
          >
            <div className="studio-feature-preview border-line/70 mb-6 flex h-48 items-center justify-center overflow-hidden rounded-[14px] border px-5 py-6 transition-colors">
              {item.preview}
            </div>
            <div className="flex items-center gap-3"><span className="text-brand-strong/70 font-mono text-[11px]">0{index + 1}</span><h3 className="text-ink font-semibold">{item.title}</h3></div>
            <p className="text-muted mt-2 text-sm leading-relaxed">{item.desc}</p>
          </article>
        ))}
      </div>
    </section>
  )
}