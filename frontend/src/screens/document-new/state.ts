import type { Fit, Flag, GenSection, ResumePages, SaveBody, TailorBody, Template, WritingStyle } from '../documents/api'

export type DocKind = Template['kind']

export const DOC_KINDS: { id: DocKind; label: string; hint: string }[] = [
  { id: 'resume', label: 'Resume', hint: 'Experience, skills and education' },
  { id: 'letter', label: 'Cover letter', hint: 'A letter for this role' },
]
export const kindLabel = (k: DocKind) => DOC_KINDS.find((d) => d.id === k)?.label ?? k

/** What the user chose for one document. */
export type DocDraft = {
  templateId: string
  styleId: string // a letter's writing style; empty is the template's first
  inputs: Record<string, string>
  overrides: Record<string, string> // the user's own wording by slot id ("summary", "bullet:<fact id>", "para:<n>" for the nth paragraph of a letter) -> text. Wins over written text.
  instructions: string // the user's directions for the writer
  resumePages: ResumePages // how long this resume should be; a letter ignores it
  sections: GenSection[] // the writer's document: its structure and the default text of each slot, never an override
  flags: Record<string, Flag> // slots of the draft the person should look at, by slot id
  genError?: string // why the last generate failed: the document waits, unsaved, until a generate works
}

/** The model's review of the posting, with the posting text it was made from. `unavailable`: no model, or the user went on without it. */
export type Review = { text: string; result: Fit | 'unavailable' }

export type Wizard = {
  step: 1 | 2 | 3 | 4 | 5
  jobText: string
  jobUrl: string
  noJob: boolean // the user chose to write without a job posting
  kinds: DocKind[] // the documents being created, in DOC_KINDS order
  active: DocKind // the side tab showing
  docs: Record<DocKind, DocDraft>
  answers: Record<string, 'yes' | 'no'> // "Do you have <requirement>?" replies, by requirement
  review: Review | null // made when the user leaves step 1; dropped when the posting text changes
}

export const emptyDoc: DocDraft = {
  templateId: '',
  styleId: '',
  inputs: {},
  overrides: {},
  instructions: '',
  resumePages: 'default',
  sections: [],
  flags: {},
}

export const initialWizard: Wizard = {
  step: 1,
  jobText: '',
  jobUrl: '',
  noJob: false,
  kinds: [],
  active: 'resume',
  docs: { resume: emptyDoc, letter: emptyDoc },
  answers: {},
  review: null,
}

const DRAFT_KEY = 'careerbuddy.documentDraft.v3'

/** Every visit starts the wizard over: the previous run's entries are discarded, not restored. */
export function loadDraft(): Wizard {
  clearDraft()
  return initialWizard
}

export function saveDraft(w: Wizard): void {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(w))
  } catch {
    /* storage unavailable: nothing to do */
  }
}

export function clearDraft(): void {
  try {
    localStorage.removeItem(DRAFT_KEY)
  } catch {
    /* ignore */
  }
}

/** The override rule: the user's text wins over generated text; text equal to the generated one is no override. */
export function withOverride(overrides: Record<string, string>, key: string, text: string, generated: string): Record<string, string> {
  const rest = Object.fromEntries(Object.entries(overrides).filter(([k]) => k !== key))
  return text === generated ? rest : { ...rest, [key]: text }
}

export const missingInputs = (d: DocDraft, t: Template | undefined) => !t || t.required.some((f) => !d.inputs[f]?.trim())

/** The style a letter is written in: the chosen one, else the template's first. Resumes have none. */
export const styleOf = (d: DocDraft, t: Template | undefined): WritingStyle | undefined => t?.styles.find((s) => s.id === d.styleId) ?? t?.styles[0]

/** What the writer is told about the template and, for a letter, its style. */
export const writerInstructions = (d: DocDraft, t: Template | undefined) => [t?.instructions, styleOf(d, t)?.instructions].filter(Boolean).join(' ')

/** The request for one document: the template, the job and the inputs, never the user's text. The backend uses every visible fact. */
export function buildBody(w: Wizard, kind: DocKind): TailorBody {
  const d = w.docs[kind]
  const fit = kind === 'letter' && w.review && w.review.result !== 'unavailable' ? w.review.result : undefined // a letter names the posting's role and company
  const job = fit ? { ...(fit.title && { role: fit.title }), ...(fit.company && { company: fit.company }) } : {}
  return { template: d.templateId, job_text: w.jobText, inputs: { ...job, ...d.inputs } }
}

/** The save request: the writer's sections (the layout) and the user's own words, kept apart. */
export function buildSave(w: Wizard, kind: DocKind, t: Template): SaveBody {
  const b = buildBody(w, kind)
  const { role, company } = w.docs[kind].inputs
  return {
    ...b,
    overrides: Object.fromEntries(Object.entries(w.docs[kind].overrides).filter(([, v]) => v.trim())),
    sections: w.docs[kind].sections,
    instructions: w.docs[kind].instructions.trim(),
    resume_pages: w.docs[kind].resumePages,
    template_instructions: writerInstructions(w.docs[kind], t),
    font: 'sans',
    paper: 'letter',
    label: [role, company].filter(Boolean).join(' · ') || t.label,
  }
}
