import { explore, groupPositions, groupSkills, subtitle } from './explore'

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

it('groups positions by employer, newest role first, org-less last as Other', () => {
  const pos = [
    f('o1', 'Position', 'Intern', { period: '2012–2013' }),
    f('o2', 'Position', 'Lead', { period: 'Mar 2019 - Present' }),
    f('o3', 'Position', 'Junior', { period: '2016 to 2018' }),
    f('o4', 'Position', 'Senior', { period: 'Mar 2019 - Present' }),
    f('o5', 'Position', 'Freelancer', { period: '2020' }),
    f('o6', 'Position', 'Founder', { period: '2014 - 2017' }),
  ]
  const orgs = [f('A', 'Organization', 'Acme'), f('B', 'Organization', 'Beta'), f('C', 'Organization', 'Core')]
  const at = (p: string, o: string) => ({ source: p, target: o, kind: 'AT' })
  const grouped = groupPositions(
    pos,
    explore([...pos, ...orgs], [at('o1', 'B'), at('o3', 'B'), at('o2', 'A'), at('o4', 'A'), at('o6', 'C')]),
  )
  expect(grouped.map((g) => [g.org, g.years, g.items.map((x) => x.title)])).toEqual([
    ['Acme', '2019 – now', ['Lead', 'Senior']], // same period: title order
    ['Beta', '2012 – 2018', ['Junior', 'Intern']],
    ['Core', '2014 – 2017', ['Founder']],
    ['Other', '2020', ['Freelancer']],
  ])
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
