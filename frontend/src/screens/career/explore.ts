import type { Edge, Fact } from './api'

/** The kinds the explorer browses, in the order its sections show them. */
export const KINDS = ['Position', 'Organization', 'Education', 'Achievement', 'Skill'] as const
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
}

const isKind = (kind: string): kind is Kind => (KINDS as readonly string[]).includes(kind)

/** Indexes the facts and the links between them. Pure. */
export function explore(facts: Fact[], edges: Edge[]): Explorer {
  const visible = facts.filter((f) => isKind(f.kind))
  const byId = new Map(visible.map((f) => [f.id, f]))
  const links = new Map<string, Fact[]>()
  for (const e of edges) {
    const [a, b] = [byId.get(e.source), byId.get(e.target)]
    if (!a || !b) continue
    links.set(a.id, [...(links.get(a.id) ?? []), b])
    links.set(b.id, [...(links.get(b.id) ?? []), a])
  }
  const byTitle = (a: Fact, b: Fact) => a.title.localeCompare(b.title)
  return {
    byId,
    list: (kind) => visible.filter((f) => f.kind === kind).sort(byTitle),
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
    parts.push(near.Organization?.[0]?.title ?? '', fact.attributes.period ?? '')
  } else if (fact.kind === 'Achievement') {
    parts.push(near.Position?.[0]?.title ?? '')
  } else if (fact.kind === 'Education') {
    parts.push(near.Organization?.[0]?.title ?? fact.attributes.school ?? '', fact.attributes.period ?? '')
  } else {
    const count = Object.values(near).reduce((n, list) => n + (list?.length ?? 0), 0)
    parts.push(count ? `${count} linked` : '')
  }
  return parts.filter(Boolean).join(' · ')
}
