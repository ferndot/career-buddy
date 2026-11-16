import { Box, Heading, Input, Link, Text, Textarea } from '@chakra-ui/react'
import { useEffect, useRef, useState } from 'react'
import { RobotMascot } from '../../brand'
import { fetchJobText } from '../documents/api'
import type { Wizard } from './state'

type Props = { w: Wizard; set: (patch: Partial<Wizard>) => void }
type Status = 'idle' | 'loading' | 'ok' | 'error'

const DELAY_MS = 500
const looksLikeUrl = (v: string) => /^https?:\/\/\S+$/i.test(v)
const siteName = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export function JobStep({ w, set }: Props) {
  const [status, setStatus] = useState<Status>(w.jobText.trim() ? 'ok' : 'idle')
  const [pasteOpen, setPasteOpen] = useState(false)
  const latest = useRef(w.jobUrl.trim()) // the URL whose response we still want
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])

  const run = (url: string) => {
    latest.current = url
    setStatus('loading')
    set({ jobText: '', prefilled: false })
    fetchJobText(url)
      .then((r) => {
        if (latest.current !== url) return // a newer URL replaced this one
        set({ jobText: r.text, prefilled: false })
        setStatus('ok')
      })
      .catch(() => latest.current === url && setStatus('error'))
  }
  const onUrl = (value: string, immediate = false) => {
    const url = value.trim()
    set({ jobUrl: value, noJob: false })
    window.clearTimeout(timer.current)
    if (url === latest.current) return // already fetched or fetching (paste fires paste, then change)
    latest.current = url
    if (!looksLikeUrl(url)) return setStatus('idle')
    if (immediate) return run(url)
    timer.current = window.setTimeout(() => run(url), DELAY_MS)
  }

  const showText = pasteOpen || status === 'error'
  const url = w.jobUrl.trim()
  return (
    <Box maxW="560px" mx="auto" minH="50vh" display="flex" flexDirection="column" justifyContent="center" alignItems="center" textAlign="center" gap="4">
      <RobotMascot mood={status === 'loading' ? 'thinking' : status === 'ok' ? 'celebrate' : 'happy'} />
      <Heading as="h1" size="2xl" fontWeight="semibold" color="app.text">
        Where is the job posting?
      </Heading>
      <Text color="app.muted">Paste the link and we will read it for you.</Text>
      <Input
        type="url"
        size="2xl"
        aria-label="Job posting link"
        placeholder="https://example.com/jobs/123"
        value={w.jobUrl}
        onChange={(e) => onUrl(e.target.value)}
        onPaste={(e) => {
          const pasted = e.clipboardData.getData('text').trim()
          if (looksLikeUrl(pasted)) onUrl(pasted, true)
        }}
        bg="app.surface"
        borderColor="app.borderStrong"
        color="app.text"
        autoFocus
      />
      <Box minH="6" role="status" aria-live="polite" fontSize="sm">
        {status === 'loading' && <Text color="app.muted">Fetching…</Text>}
        {status === 'ok' && <Text color="app.text">Got it: {looksLikeUrl(url) ? siteName(url) : 'job text added'}</Text>}
        {status === 'error' && <Text color="app.missText">Could not read this page. Paste the text instead.</Text>}
      </Box>
      {!showText && (
        <Link as="button" fontSize="sm" color="app.link" onClick={() => setPasteOpen(true)}>
          Paste the job text instead
        </Link>
      )}
      {!w.jobText.trim() && !w.noJob && (
        <Link as="button" fontSize="sm" color="app.muted" onClick={() => set({ noJob: true, step: 2 })}>
          Continue without a job posting
        </Link>
      )}
      {showText && (
        <Textarea
          rows={10}
          aria-label="Job posting text"
          placeholder="Paste the full text of the posting"
          value={w.jobText}
          onChange={(e) => {
            set({ jobText: e.target.value, prefilled: false })
            setPasteOpen(true)
            setStatus(e.target.value.trim() ? 'ok' : 'idle')
          }}
          bg="app.surface"
          borderColor="app.borderStrong"
          color="app.text"
          textAlign="left"
        />
      )}
    </Box>
  )
}
