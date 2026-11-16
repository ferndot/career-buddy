const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2019", "2019-03" or "2019-03-14" as "2019", "Mar 2019" or "14 Mar 2019"; "present" as "Present". Other text as written. Mirrors domain/dates.py. */
export function formatDate(iso: string): string {
  if (iso.toLowerCase() === 'present') return 'Present'
  const m = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/.exec(iso)
  if (!m || (m[2] && !MONTHS[Number(m[2]) - 1])) return iso
  return [m[3] && String(Number(m[3])), m[2] && MONTHS[Number(m[2]) - 1], m[1]].filter(Boolean).join(' ')
}

export const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

const two = (n: number) => String(n).padStart(2, '0')

/** A picked year, month (1-12) or day as the partial ISO text stored: "2021", "2021-03" or "2021-03-14". The length is the precision. */
export const partialDate = (year: number, month?: number, day?: number): string =>
  [String(year).padStart(4, '0'), month && two(month), month && day && two(day)].filter(Boolean).join('-')

/** The year and month (1-12) a stored partial date names, for opening a calendar there; undefined when it is not one. */
export function dateParts(iso: string): { year: number; month?: number } | undefined {
  const m = /^(\d{4})(?:-(\d{2}))?/.exec(iso)
  return m && Number(m[1]) > 0 ? { year: Number(m[1]), month: m[2] ? Math.min(Math.max(Number(m[2]), 1), 12) : undefined } : undefined
}

/** One month as calendar cells, Sunday first: null pads before the 1st, then 1..last day. */
export function monthCells(year: number, month: number): (number | null)[] {
  const lead = new Date(year, month - 1, 1).getDay()
  const days = new Date(year, month, 0).getDate()
  return [...Array<null>(lead).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)]
}

/** A fact's dates for display: "2019 – 2021", "Mar 2019 – Present", "2019", or "" with no dates. An open end is Present. Mirrors format_range in domain/dates.py. */
export function dates(a: Record<string, string>): string {
  const { started = '', finished = '' } = a
  const [s, e] = [formatDate(started), formatDate(started && !finished ? 'present' : finished)]
  return s && e && s !== e ? `${s} – ${e}` : s || e
}
