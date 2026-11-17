import { useMutation } from '@tanstack/react-query'
import { ApiError } from '../../api'
import type { Log } from '../../components'
import { getFit } from '../documents/api'
import type { Review, Wizard } from './state'
import { whyFailed } from './whyFailed'

// No model (503) is not an error for the user: step 3 says so. Any other failure is thrown.
const read = (text: string): Promise<Review['result']> =>
  getFit(text).catch((e) => {
    if (e instanceof ApiError && e.status === 503) return 'unavailable'
    throw e
  })

/**
 * Leaving step 1: the model reads the posting, once per posting text, and the result goes in the wizard before step 2.
 * A failure keeps the loading page up (`active`) with a retry and a way on. Each stage is recorded in `log`.
 */
export function useReview(w: Wizard, set: (patch: Partial<Wizard>) => void, log: Log) {
  const m = useMutation({ mutationFn: read })
  const done = (result: Review['result']) => {
    m.reset()
    set({ review: { text: w.jobText, result }, step: 2 })
  }
  const start = () => {
    if (!w.jobText.trim() || w.review?.text === w.jobText) return set({ step: 2 }) // nothing to read, or already read
    log('info', 'Reading the posting', 'working')
    m.mutate(w.jobText, {
      onSuccess: (result) => {
        if (result === 'unavailable') log('warn', 'No model connected', 'unavailable')
        else log('info', `Found ${result.must_have.length} must-have requirement${result.must_have.length === 1 ? '' : 's'}`, 'done')
        done(result)
      },
      onError: (e) => log('error', `Failed: ${whyFailed(e)}`, 'failed'),
    })
  }
  const skip = () => {
    log('info', 'Continued without requirements', 'idle')
    done('unavailable')
  }
  return { start, skip, active: m.isPending || m.isError, failed: m.isError }
}
