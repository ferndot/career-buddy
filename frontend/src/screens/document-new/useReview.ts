import { useMutation } from '@tanstack/react-query'
import { ApiError } from '../../api'
import type { Log } from '../../components'
import { getFit } from '../documents/api'
import type { Review, Wizard } from './state'
import { whyFailed } from './whyFailed'

/**
 * Leaving step 1: the model reads the posting, once per posting text, and the result goes in the wizard before step 2.
 * Any failure, including no model (503), keeps the loading page up (`active`) with the reason, a retry and a way on.
 * Going on without requirements is `skip`, which leads to step 2 with step 3 saying no model answered. Each stage is recorded in `log`.
 */
export function useReview(w: Wizard, set: (patch: Partial<Wizard>) => void, newLog: (title: string) => Log) {
  const m = useMutation({ mutationFn: (text: string) => getFit(text) })
  const done = (result: Review['result']) => {
    m.reset()
    set({ review: { text: w.jobText, result }, step: 2 })
  }
  const start = () => {
    if (!w.jobText.trim() || w.review?.text === w.jobText) return set({ step: 2 }) // nothing to read, or already read
    const log = newLog('Job posting review')
    log('info', 'Reading the posting', 'working')
    m.mutate(w.jobText, {
      onSuccess: (result) => {
        log('info', `Found ${result.must_have.length} must-have requirement${result.must_have.length === 1 ? '' : 's'}`, 'done')
        done(result)
      },
      onError: (e) => {
        if (e instanceof ApiError && e.status === 503) {
          log('warn', `No answer from the model: ${whyFailed(e)}`, 'unavailable') // the page stays up: Try again, or go on without requirements
        } else log('error', `Failed: ${whyFailed(e)}`, 'failed')
      },
    })
  }
  const skip = () => {
    newLog('Job posting review')('info', 'Continued without requirements', 'idle')
    done('unavailable')
  }
  return { start, skip, active: m.isPending || m.isError, failed: m.isError, reason: m.error ? whyFailed(m.error) : '' }
}
