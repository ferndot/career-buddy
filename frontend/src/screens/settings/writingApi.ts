import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import { endpoints } from '../../api/endpoints'

export type Kind = 'resume' | 'letter'
/** `rules` is what the writer uses now: the saved override, else the default. */
export type KindRules = { rules: string[]; default: string[]; custom: boolean }
export type WritingRules = Record<Kind, KindRules>

export const MAX_RULES = 20
export const MAX_LENGTH = 300

const KEY = ['writing', 'rules'] as const

export const useWritingRules = () =>
  useQuery({ queryKey: KEY, queryFn: () => apiFetch<WritingRules>(endpoints.writing.rules()) })

function useChange<V>(fn: (v: V) => Promise<unknown>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: KEY }) })
}

export const useSaveRules = (kind: Kind) =>
  useChange((rules: string[]) => apiFetch<KindRules>(endpoints.writing.kind(kind), { method: 'PUT', body: { rules } }))
export const useResetRules = (kind: Kind) =>
  useChange(() => apiFetch(endpoints.writing.kind(kind), { method: 'DELETE' }))
