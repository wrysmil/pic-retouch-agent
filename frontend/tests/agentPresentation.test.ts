import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  collectTurnImages,
  hasOpenTurn,
  hasPendingPlanSteps,
  shouldShowTurnTaskCard,
} from '../src/lib/agentPresentation.ts'

const image = (id: string, kind = 'generated', url = `${id}.png`) =>
  ({
    id,
    kind,
    source: 'tool',
    url,
    width: 512,
    height: 512,
    image_format: 'png',
    size_bytes: 100,
    has_alpha: false,
    created_at: '2026-10-21T00:00:00Z',
  }) as Parameters<typeof collectTurnImages>[1][number]
const run = (
  status: 'succeeded' | 'failed' | 'running',
  candidates = [image('own')],
  result = {},
) => ({ status, candidates, result })

test('规划、待确认和执行均阻止另一轮并发改图', () => {
  for (const phase of ['planning', 'awaiting_confirmation', 'executing'] as const) {
    assert.equal(hasOpenTurn([{ phase }]), true, phase)
  }
  assert.equal(hasOpenTurn([{ phase: 'completed' }, { phase: 'failed' }]), false)
  assert.equal(hasOpenTurn([]), false)
})
test('普通问候不会提前显示任务计划卡', () => {
  assert.equal(
    shouldShowTurnTaskCard({ phase: 'planning', steps: [], plan_draft: [] }),
    false,
  )
  assert.equal(
    shouldShowTurnTaskCard({
      phase: 'planning',
      steps: [],
      plan_draft: [
        {
          call_index: 0,
          id: 'step-1',
          tool: 'flip_layer',
          label: '水平翻转',
          params: {},
          state: 'draft',
        },
      ],
    }),
    true,
  )
  assert.equal(
    shouldShowTurnTaskCard({
      phase: 'completed',
      steps: [],
      plan_draft: [],
    }),
    false,
  )
})
test('只有尚未开始的任务才配停止入口', () => {
  assert.equal(hasPendingPlanSteps([{ status: 'running' }]), false)
  assert.equal(hasPendingPlanSteps([{ status: 'running' }, { status: 'pending' }]), true)
  assert.equal(hasPendingPlanSteps([{ status: 'waiting' }]), true)
  assert.equal(hasPendingPlanSteps([{ status: 'succeeded' }, { status: 'failed' }]), false)
})
test('结果图片只来自此轮成功任务，不使用会话当前图兜底', () => {
  assert.deepEqual(
    collectTurnImages([run('succeeded')], [image('unrelated')]).map((a) => a.id),
    ['own'],
  )
  assert.deepEqual(
    collectTurnImages([run('succeeded', [], { document: {} })], [image('unrelated')]),
    [],
  )
})
test('失败和执行中的任务不能展示成功结果', () => {
  assert.deepEqual(collectTurnImages([run('failed'), run('running')], []), [])
})
test('可从任务明确返回的素材标识恢复结果，并保留生成顺序', () => {
  const result = { asset_ids: ['second', 'first'], adopt_asset_id: 'second' }
  assert.deepEqual(
    collectTurnImages([run('succeeded', [], result)], [image('first'), image('second')]).map(
      (a) => a.id,
    ),
    ['second', 'first'],
  )
})
test('拆层中间素材不冒充完整成片，多步骤重复图片去重', () => {
  const candidates = [
    image('own'),
    image('mask', 'mask'),
    image('subject', 'subject'),
    image('background', 'background'),
  ]
  assert.deepEqual(
    collectTurnImages([run('succeeded', candidates), run('succeeded')], []).map((a) => a.id),
    ['own'],
  )
})
test('优先使用会话刷新后的图片地址，避免过期签名 URL', () => {
  assert.equal(
    collectTurnImages([run('succeeded')], [image('own', 'generated', 'fresh.png')])[0]?.url,
    'fresh.png',
  )
})
test('多层画布的局部图层产物不能作为整图采用，避免覆盖其他图层', () => {
  const layerResult = {
    document: { layers: [{ asset_id: 'own' }, { asset_id: 'other-layer' }] },
    asset_ids: ['own'],
  }
  assert.deepEqual(collectTurnImages([run('succeeded', [image('own')], layerResult)], []), [])
  const fullImageResult = { ...layerResult, adopt_asset_id: 'own' }
  assert.deepEqual(
    collectTurnImages([run('succeeded', [image('own')], fullImageResult)], []).map((a) => a.id),
    ['own'],
  )
})
