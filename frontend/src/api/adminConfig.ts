import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'

export type AdapterType =
  | 'dashscope'
  | 'openai_compat'
  | 'minimax'
  | 'openai_image'
  | 'toookens'
  | 'mock'
export type ModelType = 'text' | 'image'

export type Connection = {
  id: string
  slug: string
  vendor: string
  adapter_type: AdapterType
  display_name: string
  status: string
  current_version_id: string | null
  current_version_seq: number | null
  base_url: string
  key_mask: string
  created_at: string
}

export type ModelDef = {
  id: string
  slug: string
  connection_id: string
  vendor_model_id: string
  edit_vendor_model_id: string | null
  display_name: string
  model_type: ModelType
  param_schema: Record<string, unknown>
  status: string
  created_at: string
}

export type Runtime = {
  current_version_seq: number | null
  revision: number
  published_at: string | null
  published_by: string | null
  note: string
  text_model_id: string
  image_model_id: string
}

export type RuntimeVersion = {
  id: string
  version_seq: number
  text_model_id: string
  image_model_id: string
  rolled_back_from: number | null
  published_by: string
  published_at: string
  note: string
}

export type TestResult = {
  capability: string
  ok: boolean
  detail: string
  duration_ms: number
}

const CONFIG = '/admin/model-config'

export function useConnections() {
  return useQuery({
    queryKey: ['admin', 'connections'],
    queryFn: () => api.get<Connection[]>(`${CONFIG}/connections`),
  })
}

export function useModels() {
  return useQuery({
    queryKey: ['admin', 'models'],
    queryFn: () => api.get<ModelDef[]>(`${CONFIG}/models`),
  })
}

export function useRuntime() {
  return useQuery({
    queryKey: ['admin', 'runtime'],
    queryFn: () => api.get<Runtime>(`${CONFIG}/current`),
  })
}

export function useRuntimeVersions() {
  return useQuery({
    queryKey: ['admin', 'runtime-versions'],
    queryFn: () => api.get<RuntimeVersion[]>(`${CONFIG}/versions`),
  })
}

function useConfigInvalidate() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['admin', 'connections'] })
    qc.invalidateQueries({ queryKey: ['admin', 'models'] })
    qc.invalidateQueries({ queryKey: ['admin', 'runtime'] })
    qc.invalidateQueries({ queryKey: ['admin', 'runtime-versions'] })
  }
}

export type ConnectionCreate = {
  slug: string
  vendor: string
  adapter_type: AdapterType
  display_name: string
  base_url: string
  api_key: string
}

export function useCreateConnection() {
  const invalidate = useConfigInvalidate()
  return useMutation({
    mutationFn: (body: ConnectionCreate) => api.post<Connection>(`${CONFIG}/connections`, body),
    onSuccess: invalidate,
  })
}

export function useAddConnectionVersion() {
  const invalidate = useConfigInvalidate()
  return useMutation({
    mutationFn: ({
      id,
      base_url,
      api_key,
    }: {
      id: string
      base_url?: string | null
      api_key?: string | null
    }) =>
      api.post<Connection>(`${CONFIG}/connections/${id}/versions`, {
        base_url: base_url ?? null,
        api_key: api_key ?? null,
      }),
    onSuccess: invalidate,
  })
}

export type ModelCreate = {
  slug: string
  connection_id: string
  vendor_model_id: string
  edit_vendor_model_id?: string | null
  display_name: string
  model_type: ModelType
}

export function useCreateModel() {
  const invalidate = useConfigInvalidate()
  return useMutation({
    mutationFn: (body: ModelCreate) => api.post<ModelDef>(`${CONFIG}/models`, body),
    onSuccess: invalidate,
  })
}

export function useActivateModel() {
  const invalidate = useConfigInvalidate()
  return useMutation({
    mutationFn: (id: string) => api.post<ModelDef>(`${CONFIG}/models/${id}/activate`),
    onSuccess: invalidate,
  })
}

export function useDisableModel() {
  const invalidate = useConfigInvalidate()
  return useMutation({
    mutationFn: (id: string) => api.post<ModelDef>(`${CONFIG}/models/${id}/disable`),
    onSuccess: invalidate,
  })
}

export function usePublishRuntime() {
  const invalidate = useConfigInvalidate()
  return useMutation({
    mutationFn: (body: {
      text_model_id: string
      image_model_id: string
      note: string
      expected_revision: number
    }) => api.post<Runtime>(`${CONFIG}/publish`, body),
    onSuccess: invalidate,
  })
}

export function useRollbackRuntime() {
  const invalidate = useConfigInvalidate()
  return useMutation({
    mutationFn: (body: { target_seq: number; expected_revision: number }) =>
      api.post<Runtime>(`${CONFIG}/rollback`, body),
    onSuccess: invalidate,
  })
}

export function useTestCapability() {
  return useMutation({
    mutationFn: (body: { capability: 'text' | 'image.generate' | 'image.edit'; prompt: string }) =>
      api.post<TestResult>(`${CONFIG}/test`, body),
  })
}
