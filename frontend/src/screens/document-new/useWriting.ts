import { useMutation } from '@tanstack/react-query'
import { ApiError } from '../../api'
import type { Log } from '../../components'
import { generateText } from '../documents/api'
import { buildBody, kindLabel, type DocDraft, type DocKind, type Wizard } from './state'
import { whyFailed } from './whyFailed'

type Reject = { reasons: string[] }

/** How many slots the writer's text was rejected for, and the distinct reasons (the first few). */
function logRejected(log: Log, rejected: Reject[]) {
  if (rejected.length === 0) return
  const why = [...new Set(rejected.flatMap((r) => r.reasons))].slice(0, 3).join('; ')
  log('warn', `${rejected.length} rejected${why ? `: ${why}` : ''}`)
}

/**
 * Writes the text of every document in the wizard, one after the other. Each document's draft replaces its generated text,
 * except under the user's own wording. A failure stops the run; the document keeps its `genError` until a write works.
 * Each document's write is its own activity in the log.
 */
export function useWriting(w: Wizard, setDoc: (kind: DocKind) => (patch: Partial<DocDraft>) => void, newLog: (title: string) => Log, onDone: () => void) {
  const write = async (kind: DocKind) => {
    const d = w.docs[kind]
    const log = newLog(`Document: ${kindLabel(kind)}`)
    const pinned = Object.keys(d.overrides).length
    log('info', `Sent request for the ${kindLabel(kind).toLowerCase()}${pinned ? `, ${pinned} slot${pinned === 1 ? '' : 's'} kept as written` : ''}`, 'working')
    try {
      const draft = await generateText({ ...buildBody(w, kind), instructions: d.instructions, pinned: Object.keys(d.overrides), resume_pages: d.resumePages })
      setDoc(kind)({ generated: { ...Object.fromEntries(Object.entries(d.generated).filter(([slot]) => slot in d.overrides)), ...draft.slots }, flags: draft.flags, genError: undefined })
      const n = Object.keys(draft.slots).length
      log('info', `Received ${n} slot${n === 1 ? '' : 's'}`, 'done')
      logRejected(log, Object.values(draft.flags))
      if (draft.notice) log('info', draft.notice)
    } catch (e) {
      // an unsupported draft comes back as an error that lists what was rejected
      const rejected = (e instanceof ApiError ? (e.body as { rejected?: Reject[] } | undefined)?.rejected : undefined) ?? []
      setDoc(kind)({ genError: whyFailed(e) })
      log('error', `Failed: ${whyFailed(e)}`, 'failed')
      logRejected(log, rejected)
      throw e
    }
  }
  const m = useMutation({
    mutationFn: async () => {
      for (const kind of w.kinds) await write(kind)
    },
    onSuccess: onDone,
  })
  return {
    start: () => m.mutate(),
    active: m.isPending || m.isError,
    failed: m.isError,
    reason: m.error ? whyFailed(m.error) : '',
  }
}
