import type { Edge, Fact } from './api'
import { dates } from './model'

/** The kinds the explorer browses, in the order its sections show them. */
export const KINDS = ['Organization', 'Position', 'Achievement', 'Education', 'Skill'] as const
export type Kind = (typeof KINDS)[number]

export const KIND_LABEL: Record<Kind, string> = {
  Position: 'Positions',
  Organization: 'Organizations',
  Education: 'Education',
  Achievement: 'Achievements',
  Skill: 'Skills',
}

export type Explorer = {
  byId: Map<string, Fact>
  /** Facts of one kind, by title. Hidden ones stay in, so they can be shown again. */
  list: (kind: Kind) => Fact[]
  /** Facts linked to `id`, grouped by kind. Links to the person are left out. */
  neighbors: (id: string) => Partial<Record<Kind, Fact[]>>
  /** Edge kind and direction per neighbor of `id`: `isSource` is true when `id` is the edge's source. */
  edgesOf: (id: string) => { fact: Fact; kind: string; isSource: boolean }[]
}

const isKind = (kind: string): kind is Kind => (KINDS as readonly string[]).includes(kind)

/** Indexes the facts and the links between them. Pure. */
export function explore(facts: Fact[], edges: Edge[]): Explorer {
  const visible = facts.filter((f) => isKind(f.kind))
  const byId = new Map(visible.map((f) => [f.id, f]))
  const links = new Map<string, Fact[]>()
  const detail = new Map<string, ReturnType<Explorer['edgesOf']>>()
  for (const e of edges) {
    const [a, b] = [byId.get(e.source), byId.get(e.target)]
    if (!a || !b) continue
    links.set(a.id, [...(links.get(a.id) ?? []), b])
    links.set(b.id, [...(links.get(b.id) ?? []), a])
    detail.set(a.id, [...(detail.get(a.id) ?? []), { fact: b, kind: e.kind, isSource: true }])
    detail.set(b.id, [...(detail.get(b.id) ?? []), { fact: a, kind: e.kind, isSource: false }])
  }
  const byTitle = (a: Fact, b: Fact) => a.title.localeCompare(b.title)
  return {
    byId,
    list: (kind) => visible.filter((f) => f.kind === kind).sort(byTitle),
    edgesOf: (id) => detail.get(id) ?? [],
    neighbors: (id) => {
      const groups: Partial<Record<Kind, Fact[]>> = {}
      for (const f of new Set(links.get(id) ?? [])) {
        const kind = f.kind as Kind
        groups[kind] = [...(groups[kind] ?? []), f]
      }
      for (const kind of KINDS) groups[kind]?.sort(byTitle)
      return groups
    },
  }
}

/** One line under a title in the list: what the fact is attached to, or how many facts it touches. */
export function subtitle(fact: Fact, ex: Explorer): string {
  const near = ex.neighbors(fact.id)
  const parts: string[] = []
  if (fact.kind === 'Position') {
    parts.push(near.Organization?.[0]?.title ?? '', dates(fact.attributes))
  } else if (fact.kind === 'Achievement') {
    parts.push(near.Position?.[0]?.title ?? '')
  } else if (fact.kind === 'Education') {
    parts.push(near.Organization?.[0]?.title ?? fact.attributes.school ?? '', dates(fact.attributes))
  } else if (fact.kind === 'Skill' && (fact.attributes.level || fact.attributes.years)) {
    const { level = '', years = '' } = fact.attributes
    parts.push(level, years && `${years} ${years === '1' ? 'year' : 'years'}`)
  } else {
    const count = Object.values(near).reduce((n, list) => n + (list?.length ?? 0), 0)
    parts.push(count ? `${count} linked` : '')
  }
  return parts.filter(Boolean).join(' · ')
}

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

/** Sortable month number for "Mar 2019", "2019" or "Present" (latest); unreadable values sort oldest. */
function monthKey(text: string): number {
  if (/present|now|current/i.test(text)) return Infinity
  const iso = /^(\d{4})(?:-(\d{2}))?/.exec(text)
  if (iso) return Number(iso[1]) * 12 + Math.max(0, Number(iso[2] ?? 1) - 1)
  const year = /\d{4}/.exec(text)?.[0]
  if (!year) return -Infinity
  return Number(year) * 12 + Math.max(0, MONTHS.indexOf(text.trim().slice(0, 3).toLowerCase()))
}

/** Start and end sort keys: from `started`/`finished` (an open end is current), else from period text like "Mar 2019 - Present", "2016–2017" or "2012 to 2016". */
function span(fact: Fact): [number, number] {
  const { started = '', finished = '' } = fact.attributes
  if (started || finished) return [monthKey(started), started && !finished ? Infinity : monthKey(finished)]
  const [start = '', end = start] = dates(fact.attributes).split(/\s+to\s+|\s*[–—-]\s*/)
  return [monthKey(start), monthKey(end)]
}

export type PositionGroup = { org: string; years: string; items: Fact[] }

/** Positions as one headerless group, newest first: end date (present is newest), then start date, then title. The employer shows on each row's subtitle. Pure. */
export function groupPositions(positions: Fact[], ex: Explorer): PositionGroup[] {
  const byOrg = new Map<string, Fact[]>()
  for (const p of positions) {
    const org = ex.neighbors(p.id).Organization?.[0]?.title ?? ''
    byOrg.set(org, [...(byOrg.get(org) ?? []), p])
  }
  const newest = (a: Fact, b: Fact) => {
    const [[as, ae], [bs, be]] = [span(a), span(b)]
    return be - ae || bs - as || a.title.localeCompare(b.title)
  }
  const year = (key: number) => (key === Infinity ? 'now' : key === -Infinity ? '' : String(Math.floor(key / 12)))
  return [...byOrg]
    .map(([org, list]) => {
      const items = list.sort(newest)
      const spans = items.map(span)
      const [from, to] = [year(Math.min(...spans.map((s) => s[0]))), year(Math.max(...spans.map((s) => s[1])))]
      return { org: org || 'Other', years: from === to ? from : [from, to].filter(Boolean).join(' – '), items, last: spans[0] }
    })
    .sort((a, b) => Number(a.org === 'Other') - Number(b.org === 'Other') || b.last[1] - a.last[1] || b.last[0] - a.last[0])
    .map(({ org, years, items }) => ({ org, years, items }))
}

export const SKILL_CATEGORIES = [
  'Languages',
  'Frameworks & libraries',
  'Data & databases',
  'Cloud & infrastructure',
  'Tools & platforms',
  'Practices & methods',
  'Other',
] as const

/** Skills grouped by their "category" attribute in the order above, uncategorized (or unknown) last. Empty groups are left out. `years` carries the count. Pure. */
export function groupSkills(skills: Fact[]): PositionGroup[] {
  const known = (c: string | undefined) => (SKILL_CATEGORIES as readonly string[]).includes(c ?? '')
  const name = (f: Fact) => (known(f.attributes.category) ? (f.attributes.category as string) : 'Uncategorized')
  return [...SKILL_CATEGORIES, 'Uncategorized']
    .map((org) => ({ org, items: skills.filter((f) => name(f) === org) }))
    .filter((g) => g.items.length)
    .map((g) => ({ ...g, years: String(g.items.length) }))
}

export const SKILL_LEVELS = ['Beginner', 'Intermediate', 'Advanced', 'Expert'] as const
