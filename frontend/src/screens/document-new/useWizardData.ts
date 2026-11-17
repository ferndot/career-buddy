import { useQuery } from '@tanstack/react-query'
import { useEffect, type Dispatch, type SetStateAction } from 'react'
import { getTemplates } from '../documents/api'
import type { Wizard } from './state'

/** The wizard's template query, the stored review as step 3 reads it, and the effect that gives each chosen document its first template. */
export function useWizardData(w: Wizard, setW: Dispatch<SetStateAction<Wizard>>) {
  const hasJob = w.jobText.trim().length > 0
  const templates = useQuery({ queryKey: ['templates'], queryFn: getTemplates, enabled: w.step >= 2 })
  // The model read the posting when the user left step 1 (useReview); there is no keyword fallback, so no review shows nothing to ask.
  const result = w.review?.result
  const found = result && result !== 'unavailable' ? result : undefined
  const review = {
    missing: found?.missing_must_have ?? [],
    nice: found?.missing_nice_to_have ?? [],
    unavailable: hasJob && result === 'unavailable',
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

  return { templates, review, hasJob }
}
