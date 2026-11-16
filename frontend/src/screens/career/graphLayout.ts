import type { Edge, Fact } from './api'
import { isHidden } from './model'

/** What the career picture draws: the visible facts and the links between them. Positions are the force layout's job. */
export type GraphNode = { id: string; kind: string; title: string; achievements: number }
export type GraphLink = { source: string; target: string; kind: string }
export type GraphView = { nodes: GraphNode[]; links: GraphLink[] }

const SHOWN = new Set(['Person', 'Position', 'Education', 'Organization', 'Skill'])
/** Links drawn as lines. ACHIEVED is counted on its position instead of drawn. */
const DRAWN = new Set(['HAS_POSITION', 'HAS_EDUCATION', 'HAS_SKILL', 'AT', 'ATTENDED', 'USES_SKILL'])

export function graphView(facts: Fact[], edges: Edge[]): GraphView {
  const shown = facts.filter((f) => !isHidden(f) && SHOWN.has(f.kind))
  const shownIds = new Set(shown.map((f) => f.id))
  const achievements = new Set(facts.filter((f) => f.kind === 'Achievement' && !isHidden(f)).map((f) => f.id))

  const counts = new Map<string, number>()
  for (const e of edges) {
    if (e.kind === 'ACHIEVED' && shownIds.has(e.source) && achievements.has(e.target)) {
      counts.set(e.source, (counts.get(e.source) ?? 0) + 1)
    }
  }
  return {
    nodes: shown.map((f) => ({ id: f.id, kind: f.kind, title: f.title, achievements: counts.get(f.id) ?? 0 })),
    links: edges
      .filter((e) => DRAWN.has(e.kind) && shownIds.has(e.source) && shownIds.has(e.target))
      .map((e) => ({ source: e.source, target: e.target, kind: e.kind })),
  }
}
