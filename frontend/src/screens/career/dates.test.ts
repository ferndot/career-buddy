import { dateParts, dates, formatDate, monthCells, partialDate } from './dates'

it('builds a partial date whose length is the precision, and reads one back', () => {
  expect([partialDate(2021), partialDate(2021, 3), partialDate(2021, 3, 4)]).toEqual(['2021', '2021-03', '2021-03-04'])
  expect(dateParts('2021-03-14')).toEqual({ year: 2021, month: 3 })
  expect(dateParts('2021')).toEqual({ year: 2021, month: undefined })
  expect(dateParts('present')).toBeUndefined()
})

it('lays a month out Sunday first with blanks before the 1st', () => {
  const feb = monthCells(2021, 2) // 1 Feb 2021 was a Monday
  expect(feb.slice(0, 2)).toEqual([null, 1])
  expect(feb.filter(Boolean)).toHaveLength(28)
  expect(monthCells(2024, 2).filter(Boolean)).toHaveLength(29)
})

it('shows a date at the precision it was given', () => {
  expect(['2019', '2019-03', '2019-03-04', 'present'].map(formatDate)).toEqual(['2019', 'Mar 2019', '4 Mar 2019', 'Present'])
  expect(formatDate('2019-13')).toBe('2019-13') // not a date: shown as written
})

it('shows a range with an en dash, one year once, and an open end as Present', () => {
  expect(dates({ started: '2019', finished: '2021' })).toBe('2019 – 2021')
  expect(dates({ started: '2019-03', finished: 'present' })).toBe('Mar 2019 – Present')
  expect(dates({ started: '2019-03' })).toBe('Mar 2019 – Present')
  expect(dates({ started: '2019', finished: '2019' })).toBe('2019')
  expect(dates({ finished: '2019-03-14' })).toBe('14 Mar 2019')
  expect(dates({})).toBe('')
})
