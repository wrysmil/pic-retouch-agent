import { ACTION_LABELS } from '@/api/sessions'

// 与后端实际调用生成模型的工具对应，去背景、调色和投放尺寸适配不属于生成。
const AI_GENERATION_TOOLS = new Set([
  'generate_image',
  'replace_background',
  'expand_canvas',
  'upscale_image',
  'erase_region',
  'replace_region',
  'split_layers',
  'promote_object_to_layer',
  'generate_marketing',
])

export function isAiGeneration(tool: string) {
  return AI_GENERATION_TOOLS.has(tool)
}

/**
 * 结果不容易手工还原的操作。这类操作不做二次确认，改为完成后在提示里给撤销入口，
 * 手感更轻但仍然可退。图层变换、显隐这些随手可改的就不打扰。
 */
const UNDOABLE = new Set([
  'split_layers',
  'promote_object_to_layer',
  'remove_background',
  'replace_background',
  'expand_canvas',
  'upscale_image',
  'erase_region',
  'replace_region',
  'adjust_image',
  'crop_canvas',
  'flip_layer',
])

export function toolLabel(tool: string | undefined) {
  if (!tool) return ''
  return ACTION_LABELS[tool] ?? ''
}

export function offersUndo(tool: string | undefined) {
  return Boolean(tool && UNDOABLE.has(tool))
}
