import dagre from '@dagrejs/dagre'
import type { Edge, Fact } from './api'
import { isHidden } from './model'

/** Pure layout for the career picture: dagre ranks the facts left to right, so a shared organization gets one node with several lines in. */
export type GraphNode = { id: string; kind: string; title: string; x: number; y: number }
export type GraphEdge = { source: string; target: string; kind: string }
export type Layout = {
  nodes: GraphNode[] // x, y are the top-left corner
  edges: GraphEdge[]
  badges: Record<string, number> // achievements per position, shown as a count rather than as nodes
  width: number
  height: number
}

export const NODE_W = 170
export const NODE_H = 48
const SHOWN = new Set(['Person', 'Position', 'Education', 'Organization', 'Skill'])
/** Links drawn as lines. ACHIEVED is shown as a badge on its position instead. */
const DRAWN = new Set(['HAS_POSITION', 'HAS_EDUCATION', 'HAS_SKILL', 'AT', 'ATTENDED', 'USES_SKILL'])

export function layoutGraph(facts: Fact[], edges: Edge[]): Layout {
  const shown = facts.filter((f) => !isHidden(f) && SHOWN.has(f.kind))
  const shownIds = new Set(shown.map((f) => f.id))
  const achievements = new Set(facts.filter((f) => f.kind === 'Achievement' && !isHidden(f)).map((f) => f.id))
  const badges: Record<string, number> = {}
  for (const e of edges) {
    if (e.kind === 'ACHIEVED' && shownIds.has(e.source) && achievements.has(e.target)) {
      badges[e.source] = (badges[e.source] ?? 0) + 1
    }
  }
  const drawn = edges
    .filter((e) => DRAWN.has(e.kind) && shownIds.has(e.source) && shownIds.has(e.target))
    .map((e) => ({ source: e.source, target: e.target, kind: e.kind }))

  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 28, ranksep: 110, marginx: 16, marginy: 16 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const f of shown) g.setNode(f.id, { width: NODE_W, height: NODE_H })
  for (const e of drawn) g.setEdge(e.source, e.target)
  dagre.layout(g)

  const nodes = shown.map((f) => {
    const p = g.node(f.id)
    return { id: f.id, kind: f.kind, title: f.title, x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 }
  })
  const { width, height } = g.graph()
  return { nodes, edges: drawn, badges, width: width ?? 0, height: height ?? 0 }
}
