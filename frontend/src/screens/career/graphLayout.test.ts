import { describe, expect, it } from 'vitest'
import type { Edge, Fact } from './api'
import { layoutGraph, NODE_H } from './graphLayout'

const fact = (id: string, kind: string, title: string, attributes: Record<string, string> = {}): Fact => ({
  id, kind, title, attributes, source: 'resume.txt',
})
const link = (source: string, target: string, kind: string): Edge => ({ source, target, kind })

const facts = [
  fact('p', 'Person', 'Ada'),
  fact('a', 'Position', 'Analyst'),
  fact('b', 'Position', 'Engineer'),
  fact('o', 'Organization', 'Acme'),
  fact('e', 'Education', 'BSc'),
  fact('s', 'Organization', 'Uni'),
  fact('k', 'Skill', 'Python'),
  fact('ach', 'Achievement', 'Shipped it'),
  fact('ach2', 'Achievement', 'Hidden thing', { hidden: 'true' }),
  fact('hid', 'Position', 'Old job', { hidden: 'true' }),
]
const edges = [
  link('p', 'a', 'HAS_POSITION'), link('p', 'b', 'HAS_POSITION'), link('a', 'o', 'AT'), link('b', 'o', 'AT'),
  link('p', 'e', 'HAS_EDUCATION'), link('e', 's', 'ATTENDED'), link('p', 'k', 'HAS_SKILL'), link('a', 'k', 'USES_SKILL'),
  link('a', 'ach', 'ACHIEVED'), link('a', 'ach2', 'ACHIEVED'), link('hid', 'o', 'AT'), link('p', 'hid', 'HAS_POSITION'),
]

describe('layoutGraph', () => {
  const layout = layoutGraph(facts, edges)
  const ids = new Set(layout.nodes.map((n) => n.id))

  it('draws one node per visible fact except achievements, and never a hidden one', () => {
    expect([...ids].sort()).toEqual(['a', 'b', 'e', 'k', 'o', 'p', 's'])
    expect(ids.has('hid')).toBe(false)
    expect(ids.has('ach')).toBe(false)
  })

  it('draws every link between drawn nodes, and no link to a hidden or achievement node', () => {
    const drawn = layout.edges.map((e) => `${e.source}>${e.target}:${e.kind}`).sort()
    expect(drawn).toEqual(
      ['a>k:USES_SKILL', 'a>o:AT', 'b>o:AT', 'e>s:ATTENDED', 'p>a:HAS_POSITION', 'p>b:HAS_POSITION', 'p>e:HAS_EDUCATION', 'p>k:HAS_SKILL'].sort(),
    )
  })

  it('gives a shared organization one node with a line from each position', () => {
    expect(layout.nodes.filter((n) => n.id === 'o')).toHaveLength(1)
    expect(layout.edges.filter((e) => e.target === 'o')).toHaveLength(2)
  })

  it('counts visible achievements on their position as a badge', () => {
    expect(layout.badges).toEqual({ a: 1 })
  })

  it('keeps nodes in a column from overlapping', () => {
    for (const x of new Set(layout.nodes.map((n) => n.x))) {
      const ys = layout.nodes.filter((n) => n.x === x).map((n) => n.y).sort((p, q) => p - q)
      for (let i = 1; i < ys.length; i++) expect(ys[i] - ys[i - 1]).toBeGreaterThanOrEqual(NODE_H)
    }
  })

  it('fits every node inside the drawing', () => {
    for (const n of layout.nodes) {
      expect(n.y).toBeGreaterThanOrEqual(0)
      expect(n.y).toBeLessThanOrEqual(layout.height)
      expect(n.x).toBeLessThanOrEqual(layout.width)
    }
  })
})
