const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2019", "2019-03" or "2019-03-14" as "2019", "Mar 2019" or "14 Mar 2019"; "present" as "Present". Other text as written. Mirrors domain/dates.py. */
export function formatDate(iso: string): string {
  if (iso.toLowerCase() === 'present') return 'Present'
  const m = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/.exec(iso)
  if (!m || (m[2] && !MONTHS[Number(m[2]) - 1])) return iso
  return [m[3] && String(Number(m[3])), m[2] && MONTHS[Number(m[2]) - 1], m[1]].filter(Boolean).join(' ')
}

/** A fact's dates for display: "2019 – 2021", "Mar 2019 – Present", "2019", or the raw `period` text when no dates are structured. An open end is Present. */
export function dates(a: Record<string, string>): string {
  const { started = '', finished = '', period = '' } = a
  if (!started && !finished) return period
  const [s, e] = [formatDate(started), formatDate(started && !finished ? 'present' : finished)]
  return s && e && s !== e ? `${s} – ${e}` : s || e
}
