import { Box, Button, Text, Textarea } from '@chakra-ui/react'
import type { ReactNode } from 'react'
import type { Flag, TemplateLayout } from '../documents/api'
import type { SlotDoc, SlotLine } from './layout'
import { Page } from './Page'
import { withOverride } from './state'

type Props = {
  doc: SlotDoc // the layout with slot ids
  layout: TemplateLayout // the template's page arrangement
  title: string // names the sheet: what the document is
  defaults: Record<string, string> // each slot's text without the user's edits: the writer's
  generated: Record<string, string> // the slots that have the writer's text
  flags: Record<string, Flag> // slots the writer could not do properly
  overrides: Record<string, string>
  onChange: (overrides: Record<string, string>) => void
}

const editable = (slot: string) => slot === 'summary' || slot.startsWith('skills') || ['bullet:', 'edu:', 'para:'].some((p) => slot.startsWith(p))

/**
 * The document as a white sheet in the template's layout, with editable text. An edit is an override for that slot id; Reset
 * to generated removes it and the slot follows its default again. Editable: every text the writer wrote (summary, bullets, skills and
 * education lines, a letter's paragraphs). Position headings and the contact line are the facts' own and stay read-only.
 */
export function PreviewEditor({ doc, layout, title, defaults, generated, flags, overrides, onChange }: Props) {
  const slot = (l: SlotLine): ReactNode =>
    editable(l.slot) ? (
      <Slot fallback={defaults[l.slot] ?? l.text} value={overrides[l.slot]} label={(defaults[l.slot] ?? l.text) || l.slot} generated={!!generated[l.slot]} flag={flags[l.slot]} onChange={(text) => onChange(withOverride(overrides, l.slot, text, defaults[l.slot] ?? l.text))} />
    ) : (
      <Text minH="1.2em">{l.text}</Text>
    )
  const head = (
    <>
      <Text fontWeight="bold" fontSize="18px">{doc.name.text}</Text>
      {doc.intro.map((l) => <Text key={l.slot}>{l.text}</Text>)}
    </>
  )
  const parts = doc.sections.map((s) => ({
    title: s.title,
    node: s.entries.map((e, j) => (
      <Box key={j} display="flex" flexDirection="column" gap="1">
        {e.heading && <Text fontWeight="semibold">{e.heading.text}</Text>}
        {e.paragraph && slot(e.paragraph)}
        {e.bullets.map((b) => <Box key={b.slot}>{slot(b)}</Box>)}
      </Box>
    )),
  }))
  return <Page label={title} layout={layout} head={head} parts={parts} />
}

type SlotProps = {
  fallback: string
  label: string // what names the slot for a screen reader: its text, or its id when it is empty
  value: string | undefined
  generated: boolean
  flag: Flag | undefined
  onChange: (text: string) => void
}

/** Why a flagged slot looks as it does. Once the user writes the slot themselves there is nothing left to flag. */
function FlagNote({ flag }: { flag: Flag }) {
  const why = flag.reasons.join('; ')
  return (
    <Text role="status" fontSize="xs" color="#9a5b00">
      {flag.code === 'not_rewritten' ? `Not rewritten: the writer's wording did not match your facts, so this is your own text. ${why}` : `Left empty: the writer's text did not match your facts. ${why}. Write it yourself or generate again.`}
    </Text>
  )
}

function Slot({ fallback, label, value, generated, flag, onChange }: SlotProps) {
  const edited = value !== undefined
  return (
    <Box>
      <Textarea
        autoresize
        rows={1}
        aria-label={`Edit text: ${label}`}
        value={value ?? fallback}
        onChange={(e) => onChange(e.target.value)}
        fontSize="13px"
        color="#1a1a1a"
        bg="#ffffff"
        borderColor={edited ? 'app.dash' : '#d5d9e0'}
      />
      {edited && (
        <Box display="flex" alignItems="center" gap="2" fontSize="xs" color="#5b6472">
          Edited
          <Button size="2xs" variant="ghost" color="#1d4ed8" aria-label={`Reset to generated: ${label}`} onClick={() => onChange(fallback)}>
            Reset to generated
          </Button>
        </Box>
      )}
      {!edited && flag && <FlagNote flag={flag} />}
      {!edited && generated && !flag && <Text fontSize="xs" color="#5b6472">Generated</Text>}
    </Box>
  )
}
