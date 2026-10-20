const KEY = 'retouch:prompt-draft'
const TITLE_KEY = 'retouch:project-title'

/**
 * 落地页写入并回填的需求草稿，只活在当前标签页。
 */
export function savePromptDraft(text: string): void {
  const value = text.trim()
  try {
    if (value) sessionStorage.setItem(KEY, value)
    else sessionStorage.removeItem(KEY)
  } catch {
    // 隐私模式下 sessionStorage 不可写，草稿丢失不影响主流程
  }
}

export function readPromptDraft(): string {
  try {
    return sessionStorage.getItem(KEY) ?? ''
  } catch {
    return ''
  }
}

/** 项目名先暂存在当前标签页，候选选用后写入新建会话的标题。 */
export function saveProjectTitle(title: string): void {
  const value = title.trim()
  try {
    if (value) sessionStorage.setItem(TITLE_KEY, value)
    else sessionStorage.removeItem(TITLE_KEY)
  } catch {
    // 同上，写入失败不影响生成
  }
}

export function readProjectTitle(): string {
  try {
    return sessionStorage.getItem(TITLE_KEY) ?? ''
  } catch {
    return ''
  }
}