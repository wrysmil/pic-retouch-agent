import { Fragment, type ReactNode } from 'react'

/**
 * 极简 Markdown 渲染。
 *
 * 只覆盖模型回复里真正会出现的语法：标题、无序/有序列表、引用、
 * 粗体、斜体、行内代码与链接。全部用 React 文本节点输出，不解析 HTML，
 * 因此不存在注入风险，也不用为这个引入一个 Markdown 依赖。
 */

// 加粗允许跨行（模型常把整段诗包在一对 ** 里），但不允许嵌套的星号
const INLINE = /(\*\*[^*]{1,400}?\*\*|\*[^*\n]+\*|_[^_\n]+_|`[^`\n]+`|\[[^\]\n]+\]\((https?:\/\/[^)\s]+)\))/g

function inline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  let last = 0
  let match: RegExpExecArray | null
  let index = 0
  INLINE.lastIndex = 0

  while ((match = INLINE.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index))
    const token = match[0]
    const key = `${keyPrefix}-${index++}`
    if (token.startsWith('**')) {
      nodes.push(<strong key={key}>{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('`')) {
      nodes.push(
        <code key={key} className="bg-soft text-ink rounded-[4px] px-1 py-0.5 text-[0.92em]">
          {token.slice(1, -1)}
        </code>,
      )
    } else if (token.startsWith('[')) {
      const link = /^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/.exec(token)
      nodes.push(
        <a
          key={key}
          href={link ? link[2] : '#'}
          target="_blank"
          rel="noreferrer noopener"
          className="text-brand-strong underline underline-offset-2"
        >
          {link ? link[1] : token}
        </a>,
      )
    } else {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>)
    }
    last = match.index + token.length
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

type Block =
  | { kind: 'p'; lines: string[] }
  | { kind: 'h'; level: number; text: string }
  | { kind: 'ul'; items: string[] }
  | { kind: 'ol'; items: string[] }
  | { kind: 'quote'; lines: string[] }
  | { kind: 'code'; text: string }

function parse(source: string): Block[] {
  const lines = source.replace(/\r\n/g, '\n').split('\n')
  const blocks: Block[] = []
  let paragraph: string[] = []
  let quote: string[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  let fence: string[] | null = null

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ kind: 'p', lines: paragraph })
      paragraph = []
    }
  }
  const flushQuote = () => {
    if (quote.length) {
      blocks.push({ kind: 'quote', lines: quote })
      quote = []
    }
  }
  const flushList = () => {
    if (list) {
      blocks.push(list.ordered ? { kind: 'ol', items: list.items } : { kind: 'ul', items: list.items })
      list = null
    }
  }
  const flushAll = () => {
    flushParagraph()
    flushQuote()
    flushList()
  }

  for (const line of lines) {
    if (fence !== null) {
      if (line.trim().startsWith('```')) {
        blocks.push({ kind: 'code', text: fence.join('\n') })
        fence = null
      } else {
        fence.push(line)
      }
      continue
    }
    if (line.trim().startsWith('```')) {
      flushAll()
      fence = []
      continue
    }
    if (!line.trim()) {
      flushAll()
      continue
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) {
      flushAll()
      blocks.push({ kind: 'h', level: heading[1].length, text: heading[2] })
      continue
    }

    const quoted = /^>\s?(.*)$/.exec(line)
    if (quoted) {
      flushParagraph()
      flushList()
      quote.push(quoted[1])
      continue
    }
    flushQuote()

    const bullet = /^\s*[-*+]\s+(.*)$/.exec(line)
    const ordered = /^\s*\d+[.)]\s+(.*)$/.exec(line)
    if (bullet || ordered) {
      flushParagraph()
      const isOrdered = Boolean(ordered)
      if (!list || list.ordered !== isOrdered) {
        flushList()
        list = { ordered: isOrdered, items: [] }
      }
      list.items.push((bullet ?? ordered)![1])
      continue
    }
    flushList()
    paragraph.push(line)
  }

  if (fence !== null) {
    blocks.push({ kind: 'code', text: fence.join('\n') })
  }
  flushAll()
  return blocks
}

const HEADING_CLASS = [
  'text-ink mt-2 text-sm font-semibold',
  'text-ink text-base font-semibold',
  'text-ink text-sm font-semibold',
  'text-ink text-xs font-semibold',
  'text-ink text-xs font-medium',
  'text-muted text-[11px] font-medium',
]

export default function Markdown({ text, className = '' }: { text: string; className?: string }) {
  const blocks = parse(text || '')
  return (
    <div className={`space-y-1.5 leading-relaxed ${className}`}>
      {blocks.map((block, index) => {
        const key = `b${index}`
        if (block.kind === 'h') {
          return (
            <p key={key} className={HEADING_CLASS[block.level - 1]}>
              {inline(block.text, key)}
            </p>
          )
        }
        if (block.kind === 'ul') {
          return (
            <ul key={key} className="text-ink ml-4 list-disc space-y-1">
              {block.items.map((item, i) => (
                <li key={`${key}-${i}`}>{inline(item, `${key}-${i}`)}</li>
              ))}
            </ul>
          )
        }
        if (block.kind === 'ol') {
          return (
            <ol key={key} className="text-ink ml-4 list-decimal space-y-1">
              {block.items.map((item, i) => (
                <li key={`${key}-${i}`}>{inline(item, `${key}-${i}`)}</li>
              ))}
            </ol>
          )
        }
        if (block.kind === 'quote') {
          return (
            <blockquote key={key} className="text-muted border-line border-l-2 pl-2.5">
              {block.lines.map((line, i) => (
                <p key={`${key}-${i}`}>{inline(line, `${key}-${i}`)}</p>
              ))}
            </blockquote>
          )
        }
        if (block.kind === 'code') {
          return (
            <pre
              key={key}
              className="bg-soft text-ink overflow-x-auto rounded-[10px] px-3 py-2 text-[11px] leading-relaxed"
            >
              <code>{block.text}</code>
            </pre>
          )
        }
        return (
          <p key={key} className="whitespace-pre-wrap">
            {block.lines.map((line, i) => (
              <Fragment key={`${key}-${i}`}>
                {i > 0 && <br />}
                {inline(line, `${key}-${i}`)}
              </Fragment>
            ))}
          </p>
        )
      })}
    </div>
  )
}
