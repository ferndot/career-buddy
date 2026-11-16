import { Box, Button, Grid, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { MONTH_NAMES, dateParts, monthCells, partialDate } from './dates'

type View = 'day' | 'month' | 'year'
const PAGE = 12 // years per page in the year view

const cell = { size: 'xs', variant: 'ghost', color: 'app.text', _hover: { bg: 'app.hover' } } as const
const chosen = { bg: 'app.primary', color: 'app.onPrimary', _hover: { bg: 'app.primary' } }

/**
 * A calendar that picks at the precision of the view it is in: a day in the day view, a month in the month view, a
 * year in the year view. The heading steps up from day to month to year, so a month or a year is one click away.
 */
export function Calendar({ value, onPick }: { value: string; onPick: (partial: string) => void }) {
  const now = new Date()
  const start = dateParts(value) ?? { year: now.getFullYear(), month: now.getMonth() + 1 }
  const [view, setView] = useState<View>('day')
  const [year, setYear] = useState(start.year)
  const [month, setMonth] = useState(start.month ?? 1)
  const selected = value.trim()

  const step = (by: number) => {
    if (view === 'year') return setYear(year + by * PAGE)
    if (view === 'month') return setYear(year + by)
    const m = month - 1 + by
    setYear(year + Math.floor(m / 12))
    setMonth(((m % 12) + 12) % 12 + 1)
  }
  const page = year - (year % PAGE)
  const heading = view === 'day' ? `${MONTH_NAMES[month - 1]} ${year}` : view === 'month' ? String(year) : `${page} – ${page + PAGE - 1}`
  const up = () => setView(view === 'day' ? 'month' : 'year')

  return (
    <Box w="full" maxW="18rem" p="1">
      <Box display="flex" alignItems="center" justifyContent="space-between" mb="2" gap="1">
        <Button {...cell} type="button" aria-label={`Previous ${view}`} onClick={() => step(-1)}>‹</Button>
        <Button {...cell} type="button" fontWeight="semibold" disabled={view === 'year'} aria-label={`${heading}, choose ${view === 'day' ? 'month' : 'year'}`} onClick={up}>
          {heading}
        </Button>
        <Button {...cell} type="button" aria-label={`Next ${view}`} onClick={() => step(1)}>›</Button>
      </Box>
      {view === 'day' && (
        <Grid templateColumns="repeat(7, 1fr)" gap="0.5">
          {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((d) => <Text key={d} fontSize="xs" color="app.text3" textAlign="center">{d}</Text>)}
          {monthCells(year, month).map((d, i) => {
            if (!d) return <span key={`pad${i}`} />
            const iso = partialDate(year, month, d)
            return (
              <Button key={iso} {...cell} type="button" px="0" aria-label={`${d} ${MONTH_NAMES[month - 1]} ${year}`}
                aria-pressed={iso === selected} {...(iso === selected ? chosen : {})} onClick={() => onPick(iso)}>{d}</Button>
            )
          })}
        </Grid>
      )}
      {view === 'month' && (
        <Grid templateColumns="repeat(3, 1fr)" gap="1">
          {MONTH_NAMES.map((name, i) => {
            const iso = partialDate(year, i + 1)
            return (
              <Button key={name} {...cell} type="button" aria-label={`${name} ${year}`} aria-pressed={iso === selected}
                {...(iso === selected ? chosen : {})} onClick={() => onPick(iso)}>{name.slice(0, 3)}</Button>
            )
          })}
        </Grid>
      )}
      {view === 'year' && (
        <Grid templateColumns="repeat(3, 1fr)" gap="1">
          {Array.from({ length: PAGE }, (_, i) => page + i).map((y) => {
            const iso = partialDate(y)
            return (
              <Button key={y} {...cell} type="button" aria-label={`Year ${y}`} aria-pressed={iso === selected}
                {...(iso === selected ? chosen : {})} onClick={() => onPick(iso)}>{y}</Button>
            )
          })}
        </Grid>
      )}
    </Box>
  )
}
