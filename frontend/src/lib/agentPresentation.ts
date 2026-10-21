import type { Asset } from '../api/assets'
import type { PlanStep, Turn } from '../api/agent'
import type { Run } from '../api/runs'

export function hasPendingPlanSteps(steps: readonly Pick<PlanStep, 'status'>[]): boolean {
  return steps.some((step) => step.status === 'pending' || step.status === 'waiting')
}

export function shouldShowTurnTaskCard(
  turn: Pick<Turn, 'phase' | 'steps' | 'plan_draft'>,
): boolean {
  return (
    turn.steps.length > 0 ||
    turn.plan_draft.length > 0 ||
    ['awaiting_confirmation', 'executing', 'failed'].includes(turn.phase)
  )
}

export function hasOpenTurn(turns: readonly Pick<Turn, 'phase'>[]): boolean {
  return turns.some((turn) =>
    ['planning', 'awaiting_confirmation', 'executing'].includes(turn.phase),
  )
}

export function collectTurnImages(
  runs: readonly Pick<Run, 'status' | 'result' | 'candidates'>[],
  assets: readonly Asset[],
): Asset[] {
  const fresh = new Map(assets.map((asset) => [asset.id, asset]))
  const output = new Map<string, Asset>()
  for (const run of runs) {
    if (run.status !== 'succeeded') continue
    // 多层编辑返回的是局部图层；只有后端明确允许采用时才可切换整张画布。
    if (run.result.document && typeof run.result.adopt_asset_id !== 'string') continue
    const known = new Map(run.candidates.map((asset) => [asset.id, fresh.get(asset.id) ?? asset]))
    const ids = Array.isArray(run.result.asset_ids) ? run.result.asset_ids : []
    for (const id of [...ids, run.result.adopt_asset_id]) {
      if (typeof id !== 'string') continue
      const asset = fresh.get(id)
      if (asset) known.set(id, asset)
    }
    for (const id of [...ids, run.result.adopt_asset_id, ...known.keys()]) {
      if (typeof id !== 'string') continue
      const asset = known.get(id)
      if (asset && !['mask', 'subject', 'background'].includes(asset.kind)) output.set(id, asset)
    }
  }
  return [...output.values()]
}
