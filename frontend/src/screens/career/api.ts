import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, endpoints } from '../../api'

export type Fact = { id: string; kind: string; title: string; attributes: Record<string, string>; source: string }
export type Edge = { source: string; target: string; kind: string }
export type Graph = { nodes: unknown[]; edges: Edge[] }
export type Duplicate = { kind: string; a: { id: string; title: string }; b: { id: string; title: string }; score: number }

export const factsKey = ['facts'] as const
const graphKey = ['graph'] as const
const dupKey = ['duplicates'] as const

export const useFacts = () => useQuery({ queryKey: factsKey, queryFn: () => apiFetch<Fact[]>(endpoints.facts.list()) })
export const useGraph = () => useQuery({ queryKey: graphKey, queryFn: () => apiFetch<Graph>(endpoints.graph.get()) })
export const useDuplicates = () =>
  useQuery({ queryKey: dupKey, queryFn: () => apiFetch<Duplicate[]>(endpoints.duplicates.list()) })

/** Runs `fn`, then refetches everything on the screen. */
function useEdit<V, R = unknown>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSettled: () => Promise.all([factsKey, graphKey, dupKey].map((queryKey) => qc.invalidateQueries({ queryKey }))),
  })
}

const send = <R,>(url: string, method: string, body: unknown) => apiFetch<R>(url, { method, body })

export const useCreateFact = () =>
  useEdit((b: { kind: string; title: string; parent_id: string; attributes?: Record<string, string> }) =>
    send<{ id: string }>(endpoints.facts.create(), 'POST', b),
  )

export const useReviseFact = () =>
  useEdit((v: { id: string; attributes: Record<string, string> }) =>
    send(endpoints.facts.update(v.id), 'PATCH', { attributes: v.attributes }),
  )

export const useReorder = () =>
  useEdit((moves: { id: string; order: number }[]) =>
    Promise.all(moves.map((m) => send(endpoints.facts.reorder(m.id), 'PATCH', { order: m.order }))),
  )

export const useMerge = () =>
  useEdit((v: { alias_id: string; canonical_id: string }) => send(endpoints.duplicates.merge(), 'POST', v))

export const useDismiss = () =>
  useEdit((v: { a_id: string; b_id: string }) => send(endpoints.duplicates.dismiss(), 'POST', v))

/** Creates a position or education entry, then its bullets under it, in order. */
export function useAddEntry() {
  const create = useCreateFact()
  return useMutation({
    // The server reads a position's description into its achievements.
    mutationFn: async (v: { kind: 'Position' | 'Education'; title: string; parent_id: string; attributes: Record<string, string> }) => {
      await create.mutateAsync(v)
    },
  })
}
