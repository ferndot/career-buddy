import { describe, expect, it } from 'vitest'
import type { Edge, Fact } from './api'
import { graphView } from './graphLayout'
import { columnPositions } from './graphPositions'

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

describe('graphView', () => {
  const view = graphView(facts, edges)
  const ids = view.nodes.map((n) => n.id).sort()

  it('has one node per visible fact except achievements, and never a hidden one', () => {
    expect(ids).toEqual(['a', 'b', 'e', 'k', 'o', 'p', 's'])
  })

  it('draws every link between drawn nodes, and no link to a hidden or achievement node', () => {
    expect(view.links.map((l) => `${l.source}>${l.target}:${l.kind}`).sort()).toEqual(
      ['a>k:USES_SKILL', 'a>o:AT', 'b>o:AT', 'e>s:ATTENDED', 'p>a:HAS_POSITION', 'p>b:HAS_POSITION', 'p>e:HAS_EDUCATION', 'p>k:HAS_SKILL'].sort(),
    )
  })

  it('gives a shared organization one node with a link from each position', () => {
    expect(view.nodes.filter((n) => n.id === 'o')).toHaveLength(1)
    expect(view.links.filter((l) => l.target === 'o')).toHaveLength(2)
  })

  it('counts visible achievements on their position', () => {
    expect(view.nodes.find((n) => n.id === 'a')?.achievements).toBe(1)
    expect(view.nodes.find((n) => n.id === 'b')?.achievements).toBe(0)
  })
})

describe('columnPositions', () => {
  const view = graphView(facts, edges)
  const at = columnPositions(view.nodes, view.links)
  const point = (id: string) => at.get(id)!

  it('puts each kind in its own column, left to right', () => {
    const x = (id: string) => point(id).x
    expect(x('p')).toBeLessThan(x('a'))
    expect(x('a')).toBeLessThan(x('o'))
    expect(x('o')).toBeLessThan(x('e'))
    expect(x('e')).toBe(x('k'))
  })

  it('places every node at its own spot', () => {
    const spots = new Set([...at.values()].map((p) => `${p.x},${p.y}`))
    expect(spots.size).toBe(view.nodes.length)
  })

  it('keeps linked organizations level with their positions', () => {
    const [low, high] = [point('a').y, point('b').y].sort((x, y) => x - y)
    expect(point('o').y).toBeGreaterThanOrEqual(low)
    expect(point('o').y).toBeLessThanOrEqual(high)
  })
})
