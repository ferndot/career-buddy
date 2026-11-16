import type { GraphLink, GraphNode } from './graphLayout'

/** Fixed positions for the career graph: one column per kind, so the picture reads left to right. */
export type Point = { x: number; y: number }

const COLUMN: Record<string, number> = { Person: 0, Position: 1, Organization: 2, Education: 3, Skill: 3 }
const COLUMN_GAP = 220
const ROW_GAP = 44

/** Each node sits in its kind's column. Rows are ordered so that linked nodes sit near each other. Pure. */
export function columnPositions(nodes: GraphNode[], links: GraphLink[]): Map<string, Point> {
  const ofKind = (kind: string) => nodes.filter((n) => n.kind === kind)
  const positions = ofKind('Position')
  const positionRow = new Map(positions.map((n, i) => [n.id, i]))
  const byTitle = (a: GraphNode, b: GraphNode) => a.title.localeCompare(b.title)

  // Mean row of the positions a node is linked to; nodes linked to none go last, by title.
  const meanRow = (ids: string[]) => {
    const rows = ids.map((id) => positionRow.get(id)).filter((r): r is number => r !== undefined)
    return rows.length ? rows.reduce((sum, r) => sum + r, 0) / rows.length : Number.POSITIVE_INFINITY
  }
  const by = (score: (n: GraphNode) => number) => (a: GraphNode, b: GraphNode) => {
    const [sa, sb] = [score(a), score(b)]
    return sa === sb ? byTitle(a, b) : sa < sb ? -1 : 1
  }

  const orgScore = (org: GraphNode) => meanRow(links.filter((l) => l.kind === 'AT' && l.target === org.id).map((l) => l.source))
  const organizations = ofKind('Organization').sort(by(orgScore))
  const orgRow = new Map(organizations.map((n, i) => [n.id, i]))

  const schoolRow = (edu: GraphNode) => {
    const school = links.find((l) => l.kind === 'ATTENDED' && l.source === edu.id)
    return school ? (orgRow.get(school.target) ?? Number.POSITIVE_INFINITY) : Number.POSITIVE_INFINITY
  }
  const education = ofKind('Education').sort(by(schoolRow))

  const skillScore = (skill: GraphNode) => meanRow(links.filter((l) => l.kind === 'USES_SKILL' && l.target === skill.id).map((l) => l.source))
  const skills = ofKind('Skill').sort(by(skillScore))

  const columns: GraphNode[][] = []
  for (const kind of ['Person', 'Position']) columns[COLUMN[kind]] = ofKind(kind)
  columns[COLUMN.Organization] = organizations
  columns[COLUMN.Education] = [...education, ...skills]

  const out = new Map<string, Point>()
  const span = Math.max(...Object.values(COLUMN))
  columns.forEach((column, index) => {
    column?.forEach((node, row) => {
      out.set(node.id, {
        x: index * COLUMN_GAP - (span * COLUMN_GAP) / 2,
        y: (row - (column.length - 1) / 2) * ROW_GAP,
      })
    })
  })
  return out
}
