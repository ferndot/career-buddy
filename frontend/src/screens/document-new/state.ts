import type { Profile, SaveBody, TailorBody, Template } from '../documents/api'

export type Wizard = {
  step: 1 | 2 | 3 | 4
  jobText: string
  jobUrl: string
  kind: Template['kind']
  templateId: string
  inputs: Record<string, string>
  headline: string
  skillIds: string[] // selected skill ids
  format: string // chosen output format; '' means the template default
  bullets: string[] // selected bullet fact ids
  education: string[] // selected education fact ids
  prefilled: boolean // the AI suggestion has been applied once
  noJob: boolean // the user chose to write without a job posting
}

export const initialWizard: Wizard = {
  step: 1,
  jobText: '',
  jobUrl: '',
  noJob: false,
  kind: 'resume',
  templateId: '',
  inputs: {},
  headline: '',
  skillIds: [],
  format: '',
  bullets: [],
  education: [],
  prefilled: false,
}

const DRAFT_KEY = 'careerbuddy.documentDraft.v2'

export function loadDraft(): Wizard {
  try {
    const raw = JSON.parse(localStorage.getItem(DRAFT_KEY) ?? 'null') as Partial<Wizard> | null
    return raw ? { ...initialWizard, ...raw } : initialWizard
  } catch {
    return initialWizard
  }
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
export function prefill(profile: Profile, positions: string[] | null): Partial<Wizard> {
  const wantedPositions = positions && new Set(positions)
  return {
    headline: profile.attributes.headline ?? '',
    skillIds: profile.skill_ids,
    bullets: profile.positions
      .filter((p) => !wantedPositions || wantedPositions.has(p.title))
      .flatMap((p) => p.achievement_ids),
    education: profile.education.map((e) => e.id),
    prefilled: true,
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

export function buildBody(w: Wizard): TailorBody {
  // headline rides along in inputs; the backend ignores unknown inputs today.
  const inputs = { ...w.inputs, ...(w.headline ? { headline: w.headline } : {}) }
  return {
    template: w.templateId,
    job_text: w.jobText,
    inputs,
    ...(w.prefilled ? { selection: w.bullets, skill_ids: w.skillIds, education_ids: w.education } : {}),
  }
}

/** The chosen format, or the template's default (docx when offered). */
export const pickFormat = (w: Wizard, t: Template) =>
  t.formats.includes(w.format) ? w.format : t.formats.includes('docx') ? 'docx' : t.formats[0]

export function buildSave(w: Wizard, t: Template): SaveBody {
  const { role, company } = w.inputs
  const b = buildBody(w)
  return {
    ...b,
    selection: b.selection ?? null,
    skill_ids: b.skill_ids ?? null,
    education_ids: b.education_ids ?? null,
    overrides: {},
    format: pickFormat(w, t),
    font: 'sans',
    paper: 'letter',
    label: [role, company].filter(Boolean).join(' · ') || t.label,
  }
}
