import { explore, groupPositions, groupSkills, subtitle } from './explore'

const f = (id: string, kind: string, title: string, attributes: Record<string, string> = {}) => ({ id, kind, title, attributes, source: 's' })
const facts = [
  f('p', 'Person', 'Jane Doe'),
  f('pos', 'Position', 'Senior Engineer', { started: '2019', finished: 'present' }),
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
  expect(subtitle(ex.byId.get('pos')!, ex)).toBe('Acme · 2019 – Present')
  expect(subtitle(f('x', 'Position', 'X', { started: '2010', finished: '2012' }), ex)).toBe('2010 – 2012')
  expect(subtitle(ex.byId.get('a')!, ex)).toBe('Senior Engineer')
  expect(subtitle(ex.byId.get('org')!, ex)).toBe('1 linked')
  expect(subtitle(ex.byId.get('sk')!, ex)).toBe('')
})

it('groups positions by employer, groups and their positions newest first', () => {
  const facts = [
    f('acme', 'Organization', 'Acme'),
    f('beta', 'Organization', 'Beta'),
    f('lead', 'Position', 'Lead', { started: '2019-03', finished: 'present' }),
    f('junior', 'Position', 'Junior', { started: '2016', finished: '2018' }),
    f('founder', 'Position', 'Founder', { started: '2014', finished: '2018' }),
    f('intern', 'Position', 'Intern', { started: '2012', finished: '2013' }),
  ]
  const edges = [
    { source: 'lead', target: 'acme', kind: 'AT' },
    { source: 'junior', target: 'acme', kind: 'AT' },
    { source: 'founder', target: 'beta', kind: 'AT' },
    { source: 'intern', target: 'beta', kind: 'AT' },
  ]
  const grouped = groupPositions(facts.filter((x) => x.kind === 'Position'), explore(facts, edges))
  expect(grouped.map((g) => g.org)).toEqual(['Acme', 'Beta'])
  expect(grouped.map((g) => g.years)).toEqual(['2016 – now', '2012 – 2018'])
  expect(grouped[0].items.map((x) => x.title)).toEqual(['Lead', 'Junior'])
  expect(grouped[1].items.map((x) => x.title)).toEqual(['Founder', 'Intern'])
})

it('gives the edge kind and direction per neighbor', () => {
  expect(ex.edgesOf('pos').filter((l) => l.kind === 'AT').map((l) => [l.fact.id, l.isSource])).toEqual([['org', true]])
  expect(ex.edgesOf('org').map((l) => [l.fact.id, l.kind, l.isSource])).toEqual([['pos', 'AT', false]])
})

it('groups skills by category in the fixed order, uncategorized last, skipping empty groups', () => {
  const skills = [
    f('s1', 'Skill', 'Excel'),
    f('s2', 'Skill', 'Terraform', { category: 'Cloud & infrastructure' }),
    f('s3', 'Skill', 'Python', { category: 'Languages' }),
    f('s4', 'Skill', 'Go', { category: 'Languages' }),
    f('s5', 'Skill', 'Mystery', { category: 'Not a category' }),
  ]
  expect(groupSkills(skills).map((g) => [g.org, g.years, g.items.map((x) => x.title)])).toEqual([
    ['Languages', '2', ['Python', 'Go']],
    ['Cloud & infrastructure', '1', ['Terraform']],
    ['Uncategorized', '2', ['Excel', 'Mystery']],
  ])
  expect(groupSkills([])).toEqual([])
})

it('subtitles a skill with its level and years, omitting what is empty', () => {
  const sub = (a: Record<string, string>) => subtitle(f('x', 'Skill', 'X', a), ex)
  expect(sub({ level: 'Expert', years: '5' })).toBe('Expert · 5 years')
  expect(sub({ years: '5+' })).toBe('5+ years')
  expect(sub({ level: 'Advanced', years: '' })).toBe('Advanced')
  expect(sub({ years: '1' })).toBe('1 year')
})
