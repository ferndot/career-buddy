import type { Flag, PreviewDoc, ResumePages, Profile, SaveBody, TailorBody, Template } from '../documents/api'
import { saveTexts } from './layout'

export type DocKind = Template['kind']

export const DOC_KINDS: { id: DocKind; label: string; hint: string }[] = [
  { id: 'resume', label: 'Resume', hint: 'Experience, skills and education' },
  { id: 'letter', label: 'Cover letter', hint: 'A letter for this role' },
]
export const kindLabel = (k: DocKind) => DOC_KINDS.find((d) => d.id === k)?.label ?? k

/** What the user chose for one document. */
export type DocDraft = {
  templateId: string
  inputs: Record<string, string>
  headline: string
  skillIds: string[] // selected skill ids
  bullets: string[] // selected bullet fact ids
  education: string[] // selected education fact ids
  overrides: Record<string, string> // the user's own wording by slot id ("summary", "bullet:<fact id>", "para:<n>") -> text. Wins over generated text.
  instructions: string // the user's directions for the writer
  resumePages: ResumePages // how long this resume should be; a letter ignores it
  generated: Record<string, string> // the writer's draft by slot id: the default text of a slot, never an override
  flags: Record<string, Flag> // slots of the draft the person should look at, by slot id
  seeded: boolean // the AI suggestion has been applied to this document
}

export type Wizard = {
  step: 1 | 2 | 3 | 4 | 5
  jobText: string
  jobUrl: string
  noJob: boolean // the user chose to write without a job posting
  prefilled: boolean // the AI suggestion has been applied; the job step clears it when the posting changes
  kinds: DocKind[] // the documents being created, in DOC_KINDS order
  active: DocKind // the side tab showing
  docs: Record<DocKind, DocDraft>
  answers: Record<string, 'yes' | 'no'> // "Do you have <requirement>?" replies, by requirement
}

export const emptyDoc: DocDraft = {
  templateId: '',
  inputs: {},
  headline: '',
  skillIds: [],
  bullets: [],
  education: [],
  overrides: {},
  instructions: '',
  resumePages: 1,
  generated: {},
  flags: {},
  seeded: false,
}

export const initialWizard: Wizard = {
  step: 1,
  jobText: '',
  jobUrl: '',
  noJob: false,
  prefilled: false,
  kinds: [],
  active: 'resume',
  docs: { resume: emptyDoc, letter: emptyDoc },
  answers: {},
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

/** Starting selection: every skill and education entry; bullets narrowed to the positions the AI found fitting. */
export function prefill(profile: Profile, positions: string[] | null): Partial<DocDraft> {
  const wantedPositions = positions && new Set(positions)
  return {
    headline: profile.attributes.headline ?? '',
    skillIds: profile.skill_ids,
    bullets: profile.positions
      .filter((p) => !wantedPositions || wantedPositions.has(p.title))
      .flatMap((p) => p.achievement_ids),
    education: profile.education.map((e) => e.id),
    seeded: true,
  }
}

export function toggle(list: string[], item: string, on: boolean): string[] {
  const rest = list.filter((x) => x !== item)
  return on ? [...rest, item] : rest
}

export function toggleMany(list: string[], items: string[], on: boolean): string[] {
  const rest = list.filter((x) => !items.includes(x))
  return on ? [...rest, ...items] : rest
}

/** The override rule: the user's text wins over generated text; text equal to the generated one is no override. */
export function withOverride(overrides: Record<string, string>, key: string, text: string, generated: string): Record<string, string> {
  const rest = Object.fromEntries(Object.entries(overrides).filter(([k]) => k !== key))
  return text === generated ? rest : { ...rest, [key]: text }
}

export const missingInputs = (d: DocDraft, t: Template | undefined) => !t || t.required.some((f) => !d.inputs[f]?.trim())

/**
 * The request for one document: its facts and template, never the user's text. The headline goes in as an override (the
 * backend reads "headline" there); the on-screen preview and the writer start from the facts, not from the user's edits.
 */
export function buildBody(w: Wizard, kind: DocKind): TailorBody & { overrides: Record<string, string> } {
  const d = w.docs[kind]
  const seeded = d.seeded && w.prefilled
  return {
    template: d.templateId,
    job_text: w.jobText,
    inputs: d.inputs,
    overrides: d.headline ? { headline: d.headline } : {},
    ...(seeded ? { selection: d.bullets, skill_ids: d.skillIds, education_ids: d.education } : {}),
  }
}

/** The save request. `preview` is the document's layout, which a letter needs to name its paragraphs. */
export function buildSave(w: Wizard, kind: DocKind, t: Template, preview?: PreviewDoc): SaveBody {
  const b = buildBody(w, kind)
  const { role, company } = w.docs[kind].inputs
  const { overrides, generated } = saveTexts(preview, w.docs[kind], kind)
  return {
    ...b,
    overrides: { ...overrides, ...b.overrides },
    generated,
    instructions: w.docs[kind].instructions.trim(),
    resume_pages: w.docs[kind].resumePages,
    selection: b.selection ?? null,
    skill_ids: b.skill_ids ?? null,
    education_ids: b.education_ids ?? null,
    font: 'sans',
    paper: 'letter',
    label: [role, company].filter(Boolean).join(' · ') || t.label,
  }
}
