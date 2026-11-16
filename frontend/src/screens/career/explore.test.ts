import { explore, subtitle } from './explore'

const f = (id: string, kind: string, title: string, attributes: Record<string, string> = {}) => ({ id, kind, title, attributes, source: 's' })
const facts = [
  f('p', 'Person', 'Jane Doe'),
  f('pos', 'Position', 'Senior Engineer', { period: '2019 - Present' }),
  f('org', 'Organization', 'Acme'),
  f('b', 'Achievement', 'B bullet'),
  f('a', 'Achievement', 'A bullet'),
  f('h', 'Achievement', 'Hidden bullet', { hidden: 'true' }),
  f('sk', 'Skill', 'Python'),
]
const edges = [
  { source: 'p', target: 'pos', kind: 'HAS_POSITION' },
  { source: 'pos', target: 'org', kind: 'AT' },
  { source: 'pos', target: 'b', kind: 'ACHIEVED' },
  { source: 'pos', target: 'a', kind: 'ACHIEVED' },
  { source: 'pos', target: 'h', kind: 'ACHIEVED' },
  { source: 'p', target: 'sk', kind: 'HAS_SKILL' },
]
const ex = explore(facts, edges)

it('lists facts of a kind by title, hidden ones included, but never the person', () => {
  expect(ex.list('Achievement').map((x) => x.title)).toEqual(['A bullet', 'B bullet', 'Hidden bullet'])
  expect(ex.byId.has('p')).toBe(false)
})

it('groups neighbors by kind from either edge direction, leaving out the person', () => {
  const near = ex.neighbors('pos')
  expect(near.Organization?.map((x) => x.id)).toEqual(['org'])
  expect(near.Achievement?.map((x) => x.title)).toEqual(['A bullet', 'B bullet', 'Hidden bullet'])
  expect(Object.keys(near).sort()).toEqual(['Achievement', 'Organization'])
  expect(ex.neighbors('org').Position?.[0]?.id).toBe('pos')
  expect(ex.neighbors('sk')).toEqual({})
})

it('writes a one-line subtitle per kind', () => {
  expect(subtitle(ex.byId.get('pos')!, ex)).toBe('Acme · 2019 - Present')
  expect(subtitle(ex.byId.get('a')!, ex)).toBe('Senior Engineer')
  expect(subtitle(ex.byId.get('org')!, ex)).toBe('1 linked')
  expect(subtitle(ex.byId.get('sk')!, ex)).toBe('')
})
