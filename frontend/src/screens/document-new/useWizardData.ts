import { useQuery } from '@tanstack/react-query'
import { useEffect, type Dispatch, type SetStateAction } from 'react'
import { getFit, getTemplates } from '../documents/api'
import type { Wizard } from './state'

/** The wizard's queries and the effect that gives each chosen document its first template. */
export function useWizardData(w: Wizard, setW: Dispatch<SetStateAction<Wizard>>) {
  const hasJob = w.jobText.trim().length > 0
  const templates = useQuery({ queryKey: ['templates'], queryFn: getTemplates, enabled: w.step >= 2 })
  // The model reads the posting; there is no keyword fallback, so a failed review (no model, or unreachable) shows nothing to ask.
  const fit = useQuery({ queryKey: ['fit', w.jobText], queryFn: () => getFit(w.jobText), enabled: w.step === 3 && hasJob, retry: false })
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

  return { templates, review, loading: fit.isLoading, hasJob }
}
