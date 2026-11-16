import { useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { SAVED_KEY, saveDocument, type SaveBody, type SavedDocument, type Template } from '../documents/api'
import { buildSave, type DocKind, type Wizard } from './state'

type Pending = { sig: string; doc: Promise<SavedDocument> }

/**
 * Saves each document once. Saving again with the same content returns the same document; changed content saves a new
 * one. Two quick clicks share one request. `saved` lists the kinds whose saved copy matches what is on screen.
 */
export function useSaved(w: Wizard, templates: Template[] | undefined) {
  const qc = useQueryClient()
  const pending = useRef<Partial<Record<DocKind, Pending>>>({})
  const [done, setDone] = useState<Partial<Record<DocKind, string>>>({}) // signature of what each kind last saved

  const body = (kind: DocKind): SaveBody | null => {
    const t = templates?.find((x) => x.id === w.docs[kind].templateId)
    return t ? buildSave(w, kind, t) : null
  }
  const save = (kind: DocKind): Promise<SavedDocument> => {
    const b = body(kind)
    if (!b) return Promise.reject(new Error('Choose a template first.'))
    const sig = JSON.stringify(b)
    const known = pending.current[kind]
    if (known?.sig === sig) return known.doc
    const doc = saveDocument(b).then((d) => {
      setDone((s) => ({ ...s, [kind]: sig }))
      void qc.invalidateQueries({ queryKey: SAVED_KEY })
      return d
    })
    pending.current[kind] = { sig, doc }
    doc.catch(() => {
      if (pending.current[kind]?.doc === doc) delete pending.current[kind] // a failed save can be tried again
    })
    return doc
  }
  const saved = w.kinds.filter((k) => {
    const b = body(k)
    return b && done[k] === JSON.stringify(b)
  })
  return { save, saved }
}
