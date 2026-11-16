import { Box, Button, Text, Textarea } from '@chakra-ui/react'
import type { ReactNode } from 'react'
import type { DocLine, PreviewDoc } from '../documents/api'
import { withOverride } from './state'

type Props = {
  doc: PreviewDoc // generated text: it follows the facts and carries none of the user's overrides
  overrides: Record<string, string>
  onChange: (overrides: Record<string, string>) => void
}

/**
 * The generated document with editable text. An edit is an override for that slot; Reset to generated removes it and the
 * slot follows its fact again. Only what the backend applies is editable: bullets (by fact id, when unique) and the summary.
 * Headings, contact line, skills and letter wording stay read-only.
 */
export function PreviewEditor({ doc, overrides, onChange }: Props) {
  const ids = doc.sections.flatMap((s) => s.entries.flatMap((e) => e.bullets.map((b) => b.source_fact_id)))
  const unique = (id: string | null) => !!id && ids.filter((i) => i === id).length === 1 // shared ids would rewrite every bullet
  const slot = (line: DocLine, key: string | null): ReactNode =>
    key ? <Slot line={line} value={overrides[key]} onChange={(text) => onChange(withOverride(overrides, key, text, line.text))} /> : <Text minH="1.2em">{line.text}</Text>
  return (
    <Box bg="app.surface2" borderWidth="1px" borderColor="app.border" borderRadius="md" p="4" fontSize="13px" color="app.text2" maxH="560px" overflowY="auto" display="flex" flexDirection="column" gap="1">
      <Text fontWeight="bold">{doc.name.text}</Text>
      {doc.intro.map((l, i) => <Text key={i}>{l.text}</Text>)}
      {doc.sections.map((s, i) => (
        <Box key={i} display="flex" flexDirection="column" gap="1" mt="2">
          {s.title && <Text fontWeight="bold" color="app.text">{s.title}</Text>}
          {s.entries.map((e, j) => (
            <Box key={j} display="flex" flexDirection="column" gap="1">
              {e.heading && <Text fontWeight="semibold">{e.heading.text}</Text>}
              {e.paragraph && slot(e.paragraph, s.title === 'Summary' ? 'summary' : null)}
              {e.bullets.map((b, k) => <Box key={k}>{slot(b, unique(b.source_fact_id) ? b.source_fact_id : null)}</Box>)}
            </Box>
          ))}
        </Box>
      ))}
    </Box>
  )
}

function Slot({ line, value, onChange }: { line: DocLine; value: string | undefined; onChange: (text: string) => void }) {
  const edited = value !== undefined
  return (
    <Box>
      <Textarea
        autoresize
        rows={1}
        aria-label={`Edit text: ${line.text}`}
        value={value ?? line.text}
        onChange={(e) => onChange(e.target.value)}
        fontSize="13px"
        color="app.text"
        bg="app.surface"
        borderColor={edited ? 'app.dash' : 'app.border'}
      />
      {edited && (
        <Box display="flex" alignItems="center" gap="2" fontSize="xs" color="app.muted">
          Edited
          <Button size="2xs" variant="ghost" color="app.link" aria-label={`Reset to generated: ${line.text}`} onClick={() => onChange(line.text)}>
            Reset to generated
          </Button>
        </Box>
      )}
    </Box>
  )
}
