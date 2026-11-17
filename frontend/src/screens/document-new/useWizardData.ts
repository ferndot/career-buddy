import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, type Dispatch, type SetStateAction } from 'react'
import { getFit, getProfile, getTemplates } from '../documents/api'
import { prefill, type Wizard } from './state'

/** The wizard's queries and the effects that feed their answers into the draft. */
export function useWizardData(w: Wizard, setW: Dispatch<SetStateAction<Wizard>>) {
  const hasJob = w.jobText.trim().length > 0
  const onFacts = w.step === 3
  const templates = useQuery({ queryKey: ['templates'], queryFn: getTemplates, enabled: w.step >= 2 })
  const profile = useQuery({ queryKey: ['profile'], queryFn: getProfile, enabled: w.step >= 3 })
  // The model reads the posting; there is no keyword fallback, so a failed review (no model, or unreachable) shows nothing to ask.
  const fit = useQuery({ queryKey: ['fit', w.jobText], queryFn: () => getFit(w.jobText), enabled: onFacts && hasJob, retry: false })
  const review = {
    missing: fit.data?.missing_must_have ?? [],
    nice: fit.data?.missing_nice_to_have ?? [],
    unavailable: hasJob && fit.isError,
  }

  // Each chosen document starts on the first template of its kind.
  useEffect(() => {
    const list = templates.data
    if (!list) return
    setW((prev) => {
      const docs = { ...prev.docs }
      let changed = false
      for (const k of prev.kinds) {
        const first = list.find((t) => t.kind === k)
        if (first && !list.some((t) => t.id === docs[k].templateId)) {
          docs[k] = { ...docs[k], templateId: first.id }
          changed = true
        }
      }
      return changed ? { ...prev, docs } : prev
    })
  }, [templates.data, w.kinds, setW])

  // The starting selection is applied once per document (again for all of them when the posting changes). It does not wait for the review.
  useEffect(() => {
    if (!onFacts || !profile.data) return
    setW((prev) => {
      const todo = prev.kinds.filter((k) => !prev.prefilled || !prev.docs[k].seeded)
      if (!todo.length) return prev
      const docs = { ...prev.docs }
      for (const k of todo) docs[k] = { ...docs[k], ...prefill(profile.data) }
      return { ...prev, docs, prefilled: true }
    })
  }, [onFacts, profile.data, w.kinds, w.prefilled, setW])

  // A skill added from a "Do you have ...?" row is selected for every document.
  const seen = useRef<Set<string> | null>(null)
  useEffect(() => {
    const ids = profile.data?.skill_ids
    if (!ids) return
    const before = seen.current
    seen.current = new Set(ids)
    const added = ids.filter((id) => before && !before.has(id))
    if (!added.length) return
    setW((prev) => ({
      ...prev,
      docs: Object.fromEntries(Object.entries(prev.docs).map(([k, d]) => [k, { ...d, skillIds: [...new Set([...d.skillIds, ...added])] }])) as Wizard['docs'],
    }))
  }, [profile.data, setW])

  return { templates, profile, review, loading: fit.isLoading || profile.isLoading, hasJob }
}
