import type { Guide } from '@/stores/editorUi'
import type { Layer, LayerDocument } from '@/api/sessions'

export type Bounds = { left: number; top: number; right: number; bottom: number }
export type SnapLine = { axis: 'x' | 'y'; position: number }
export type SnapCandidate = SnapLine & { priority: number }
export type SnapResult = { deltaX: number; deltaY: number; lines: SnapLine[] }

export const SNAP_THRESHOLD_PX = 6

export function layerBounds(layer: Layer, x = layer.transform.x, y = layer.transform.y): Bounds {
  const width = Math.abs(layer.width * layer.transform.scale_x)
  const height = Math.abs(layer.height * layer.transform.scale_y)
  const angle = (layer.transform.rotation * Math.PI) / 180
  const cos = Math.abs(Math.cos(angle))
  const sin = Math.abs(Math.sin(angle))
  const boundsWidth = width * cos + height * sin
  const boundsHeight = width * sin + height * cos
  const centerX = x + layer.width / 2
  const centerY = y + layer.height / 2
  return {
    left: centerX - boundsWidth / 2,
    top: centerY - boundsHeight / 2,
    right: centerX + boundsWidth / 2,
    bottom: centerY + boundsHeight / 2,
  }
}

export function snapCandidates(
  document: LayerDocument,
  movingId: string,
  guides: Guide[],
): SnapCandidate[] {
  const candidates: SnapCandidate[] = []
  for (const guide of guides) {
    candidates.push({ axis: guide.axis, position: guide.position, priority: 0 })
  }
  candidates.push(
    { axis: 'x', position: document.width / 2, priority: 0 },
    { axis: 'y', position: document.height / 2, priority: 0 },
    { axis: 'x', position: 0, priority: 1 },
    { axis: 'x', position: document.width, priority: 1 },
    { axis: 'y', position: 0, priority: 1 },
    { axis: 'y', position: document.height, priority: 1 },
  )
  for (const layer of document.layers) {
    if (layer.id === movingId || !layer.visible) continue
    const box = layerBounds(layer)
    candidates.push(
      { axis: 'x', position: box.left, priority: 2 },
      { axis: 'x', position: (box.left + box.right) / 2, priority: 2 },
      { axis: 'x', position: box.right, priority: 2 },
      { axis: 'y', position: box.top, priority: 2 },
      { axis: 'y', position: (box.top + box.bottom) / 2, priority: 2 },
      { axis: 'y', position: box.bottom, priority: 2 },
    )
  }
  return candidates
}

function bestSnap(
  axis: 'x' | 'y',
  edges: number[],
  candidates: SnapCandidate[],
  thresholdCanvas: number,
): { delta: number; line: SnapLine | null } {
  let best: { delta: number; distance: number; priority: number; line: SnapLine } | null = null
  for (const candidate of candidates) {
    if (candidate.axis !== axis) continue
    for (const edge of edges) {
      const delta = candidate.position - edge
      const distance = Math.abs(delta)
      if (distance > thresholdCanvas) continue
      if (
        !best ||
        distance < best.distance - 0.0001 ||
        (Math.abs(distance - best.distance) < 0.0001 && candidate.priority < best.priority)
      ) {
        best = {
          delta,
          distance,
          priority: candidate.priority,
          line: { axis, position: candidate.position },
        }
      }
    }
  }
  return best ? { delta: best.delta, line: best.line } : { delta: 0, line: null }
}

/** Snap in canvas coordinates; the caller converts screen threshold by scale. */
export function snapBounds(
  bounds: Bounds,
  candidates: SnapCandidate[],
  thresholdCanvas: number,
): SnapResult {
  const xEdges = [bounds.left, (bounds.left + bounds.right) / 2, bounds.right]
  const yEdges = [bounds.top, (bounds.top + bounds.bottom) / 2, bounds.bottom]
  const x = bestSnap('x', xEdges, candidates, thresholdCanvas)
  const y = bestSnap('y', yEdges, candidates, thresholdCanvas)
  const lines = [x.line, y.line].filter((line): line is SnapLine => Boolean(line))
  return { deltaX: x.delta, deltaY: y.delta, lines }
}
