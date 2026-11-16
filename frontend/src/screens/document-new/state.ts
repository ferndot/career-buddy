import type { Profile, SaveBody, TailorBody, Template } from '../documents/api'

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
  overrides: Record<string, string> // the user's own wording: bullet fact id, or "summary" -> text. Wins over generated text.
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
 * The request for one document. The headline goes in as an override (the backend reads "headline" there); the user's own
 * text overrides are left out of the on-screen preview, which shows generated text next to them.
 */
export function buildBody(w: Wizard, kind: DocKind, withText = true): TailorBody & { overrides: Record<string, string> } {
  const d = w.docs[kind]
  const text = withText ? Object.fromEntries(Object.entries(d.overrides).filter(([, v]) => v.trim())) : {}
  const seeded = d.seeded && w.prefilled
  return {
    template: d.templateId,
    job_text: w.jobText,
    inputs: d.inputs,
    overrides: { ...text, ...(d.headline ? { headline: d.headline } : {}) },
    ...(seeded ? { selection: d.bullets, skill_ids: d.skillIds, education_ids: d.education } : {}),
  }
}

export function buildSave(w: Wizard, kind: DocKind, t: Template): SaveBody {
  const b = buildBody(w, kind)
  const { role, company } = w.docs[kind].inputs
  return {
    ...b,
    selection: b.selection ?? null,
    skill_ids: b.skill_ids ?? null,
    education_ids: b.education_ids ?? null,
    font: 'sans',
    paper: 'letter',
    label: [role, company].filter(Boolean).join(' · ') || t.label,
  }
}
