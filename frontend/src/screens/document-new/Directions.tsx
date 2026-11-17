import { Box, Field, NativeSelect, Text, Textarea } from '@chakra-ui/react'
import { Link } from 'react-router-dom'
import { MAX_INSTRUCTIONS, type ResumePages } from '../documents/api'
import { useConnections } from '../settings/llmApi'
import type { DocDraft, DocKind } from './state'

type Props = { kind: DocKind; doc: DocDraft; setDoc: (patch: Partial<DocDraft>) => void }

/** The writer's directions and the resume length. The text itself is written on the interstitial after this step. */
export function Directions({ kind, doc, setDoc }: Props) {
  const over = doc.instructions.length > MAX_INSTRUCTIONS
  const connections = useConnections()
  const noModel = !!connections.data && !connections.data.active // not while loading: the answer is not known yet
  return (
    <Box display="flex" flexDirection="column" gap="3">
      <Field.Root invalid={over}>
        <Field.Label color="app.text2">Directions for this document</Field.Label>
        <Textarea bg="app.surface" borderColor="app.borderStrong" color="app.text" rows={3} value={doc.instructions} onChange={(e) => setDoc({ instructions: e.target.value })} />
        <Field.HelperText>Tell the writer what to emphasise or how to phrase it. Optional.</Field.HelperText>
        <Text fontSize="xs" color={over ? 'app.missText' : 'app.muted'} role={over ? 'alert' : undefined}>
          {doc.instructions.length} / {MAX_INSTRUCTIONS}{over ? ' - too long' : ''}
        </Text>
      </Field.Root>
      {kind === 'resume' && (
        <Field.Root>
          <Field.Label color="app.text2">Resume length</Field.Label>
          <NativeSelect.Root size="sm" maxW="40">
            <NativeSelect.Field value={doc.resumePages} bg="app.surface" borderColor="app.borderStrong" onChange={(e) => setDoc({ resumePages: Number(e.target.value) as ResumePages })}>
              <option value={1}>1 page</option>
              <option value={2}>2 pages</option>
              <option value={3}>3 pages</option>
            </NativeSelect.Field>
            <NativeSelect.Indicator />
          </NativeSelect.Root>
          <Field.HelperText>How much the writer may put in: bullets per position and skills.</Field.HelperText>
        </Field.Root>
      )}
      {noModel && (
        <Text role="status" fontSize="13px" color="app.warnText">
          Connect a model in <Link to="/settings">Settings</Link> to write the text
        </Text>
      )}
    </Box>
  )
}
