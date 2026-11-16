import { Box, Button, Text, Textarea } from '@chakra-ui/react'
import type { ReactNode } from 'react'
import type { Flag } from '../documents/api'
import type { SlotDoc, SlotLine } from './layout'
import { withOverride } from './state'

type Props = {
  doc: SlotDoc // the layout with slot ids
  defaults: Record<string, string> // each slot's text without the user's edits: generated, else the facts'
  generated: Record<string, string> // the slots whose default is the writer's text
  flags: Record<string, Flag> // slots the writer could not do properly
  overrides: Record<string, string>
  onChange: (overrides: Record<string, string>) => void
}

const editable = (slot: string) => slot === 'summary' || slot.startsWith('bullet:') || slot.startsWith('para:')

/**
 * The document with editable text. An edit is an override for that slot id; Reset to generated removes it and the slot
 * follows its default again. Editable: the summary, bullets and a letter's paragraphs. Headings, contact line, skills,
 * greeting and sign-off stay read-only.
 */
export function PreviewEditor({ doc, defaults, generated, flags, overrides, onChange }: Props) {
  const slot = (l: SlotLine): ReactNode =>
    editable(l.slot) ? (
      <Slot fallback={defaults[l.slot] ?? l.text} value={overrides[l.slot]} label={(defaults[l.slot] ?? l.text) || l.slot} generated={l.slot in generated} flag={flags[l.slot]} onChange={(text) => onChange(withOverride(overrides, l.slot, text, defaults[l.slot] ?? l.text))} />
    ) : (
      <Text minH="1.2em">{l.text}</Text>
    )
  return (
    <Box bg="app.surface2" borderWidth="1px" borderColor="app.border" borderRadius="md" p="4" fontSize="13px" color="app.text2" maxH="560px" overflowY="auto" display="flex" flexDirection="column" gap="1">
      <Text fontWeight="bold">{doc.name.text}</Text>
      {doc.intro.map((l) => <Text key={l.slot}>{l.text}</Text>)}
      {doc.sections.map((s, i) => (
        <Box key={i} display="flex" flexDirection="column" gap="1" mt="2">
          {s.title && <Text fontWeight="bold" color="app.text">{s.title}</Text>}
          {s.entries.map((e, j) => (
            <Box key={j} display="flex" flexDirection="column" gap="1">
              {e.heading && <Text fontWeight="semibold">{e.heading.text}</Text>}
              {e.paragraph && slot(e.paragraph)}
              {e.bullets.map((b) => <Box key={b.slot}>{slot(b)}</Box>)}
            </Box>
          ))}
        </Box>
      ))}
    </Box>
  )
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
    <Text role="status" fontSize="xs" color="app.warnText">
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
        color="app.text"
        bg="app.surface"
        borderColor={edited ? 'app.dash' : 'app.border'}
      />
      {edited && (
        <Box display="flex" alignItems="center" gap="2" fontSize="xs" color="app.muted">
          Edited
          <Button size="2xs" variant="ghost" color="app.link" aria-label={`Reset to generated: ${label}`} onClick={() => onChange(fallback)}>
            Reset to generated
          </Button>
        </Box>
      )}
      {!edited && flag && <FlagNote flag={flag} />}
      {!edited && generated && !flag && <Text fontSize="xs" color="app.muted">Generated</Text>}
    </Box>
  )
}
