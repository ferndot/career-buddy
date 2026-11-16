import { dates, formatDate } from './dates'

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
  expect(dates({ period: 'Spring 2019' })).toBe('Spring 2019')
  expect(dates({})).toBe('')
})
