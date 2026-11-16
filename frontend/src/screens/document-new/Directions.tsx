import { Box, Button, Field, NativeSelect, Text, Textarea } from '@chakra-ui/react'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { LoadingState } from '../../components'
import { generateText, MAX_INSTRUCTIONS, type ResumePages } from '../documents/api'
import { errorMessage, useConnections } from '../settings/llmApi'
import { buildBody, type DocDraft, type DocKind, type Wizard } from './state'

type Props = { w: Wizard; kind: DocKind; ready: boolean; setDoc: (patch: Partial<DocDraft>) => void }

/** Directions for the writer, and the button that asks for a draft. The draft becomes the default text of the preview. */
export function Directions({ w, kind, ready, setDoc }: Props) {
  const doc = w.docs[kind]
  const over = doc.instructions.length > MAX_INSTRUCTIONS
  const connections = useConnections()
  const noModel = !!connections.data && !connections.data.active // not while loading: the answer is not known yet
  const gen = useMutation({
    mutationFn: () => generateText({ ...buildBody(w, kind), instructions: doc.instructions, pinned: Object.keys(doc.overrides), resume_pages: doc.resumePages }),
    // a new draft replaces the generated text, except under the user's own wording, which it never touched. A failed call changes nothing.
    onSuccess: (draft) => setDoc({ generated: { ...Object.fromEntries(Object.entries(doc.generated).filter(([slot]) => slot in doc.overrides)), ...draft.slots }, flags: draft.flags }),
  })
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
      <Box>
        <Button bg="app.primary" color="app.onPrimary" disabled={!ready || over || gen.isPending || !connections.data?.active} onClick={() => gen.mutate()}>
          Generate text
        </Button>
      </Box>
      {noModel && (
        <Text role="status" fontSize="13px" color="app.warnText">
          Connect a model in <Link to="/settings">Settings</Link> to generate text
        </Text>
      )}
      {gen.isPending && <LoadingState text="Writing your text..." />}
      {gen.isError && <Text role="alert" fontSize="13px" color="app.missText">{errorMessage(gen.error)}</Text>}
    </Box>
  )
}
