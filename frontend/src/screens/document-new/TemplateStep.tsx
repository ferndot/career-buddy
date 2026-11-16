import { Box, Field, Input, Text } from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'
import { AtsTag } from '../documents/DocumentsTable'
import { getPreview, type Template } from '../documents/api'
import { PreviewEditor } from './PreviewEditor'
import { buildBody, missingInputs, type DocDraft, type DocKind, type Wizard } from './state'

type Props = { w: Wizard; kind: DocKind; templates: Template[]; setDoc: (patch: Partial<DocDraft>) => void }

const field = { bg: 'app.surface', borderColor: 'app.borderStrong', color: 'app.text' } as const

/** Template for one document, its inputs, and the generated preview with editable text. */
export function TemplateStep({ w, kind, templates, setDoc }: Props) {
  const doc = w.docs[kind]
  const choices = templates.filter((t) => t.kind === kind)
  const chosen = templates.find((t) => t.id === doc.templateId)
  const fields = chosen ? [...chosen.required, ...chosen.optional] : []
  const ready = !missingInputs(doc, chosen)
  const body = buildBody(w, kind, false) // text overrides stay out: the preview shows generated text beside them
  const preview = useQuery({ queryKey: ['details-preview', body], queryFn: () => getPreview(body), enabled: ready })
  const p = preview.data
  return (
    <Box display="flex" gap="6" flexWrap="wrap" alignItems="flex-start">
      <Box flex="1 1 280px" minW="0" bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5" display="flex" flexDirection="column" gap="5">
        <Box>
          <Text fontWeight="semibold" fontSize="sm" mb="2">Template</Text>
          <Box display="grid" gridTemplateColumns="repeat(auto-fill, minmax(160px, 1fr))" gap="3" role="radiogroup" aria-label="Template">
            {choices.map((t) => {
              const on = t.id === doc.templateId
              return (
                <Box key={t.id} as="button" role="radio" aria-checked={on} textAlign="left" p="3" borderRadius="md" borderWidth="2px" borderColor={on ? 'app.primary' : 'app.border'} bg={on ? 'app.activeBg' : 'app.surface2'} color={on ? 'app.activeText' : 'app.text'} cursor="pointer" onClick={() => setDoc({ templateId: t.id, inputs: {} })}>
                  <Text fontWeight="semibold" fontSize="sm">{t.label}</Text>
                </Box>
              )
            })}
          </Box>
        </Box>
        {fields.map((f) => (
          <Field.Root key={f} required={chosen?.required.includes(f)}>
            <Field.Label color="app.text2" textTransform="capitalize">{f.replace('_', ' ')}<Field.RequiredIndicator /></Field.Label>
            <Input {...field} value={doc.inputs[f] ?? ''} onChange={(e) => setDoc({ inputs: { ...doc.inputs, [f]: e.target.value } })} />
          </Field.Root>
        ))}
        {p && (
          <Box display="flex" flexDirection="column" gap="2">
            <Text fontWeight="semibold" fontSize="sm">ATS check</Text>
            <Box><AtsTag issues={p.ats.issues.length} /></Box>
            {p.ats.issues.map((i) => (
              <Text key={i.code} fontSize="13px" color="app.warnText" bg="app.warnPanel" borderWidth="1px" borderColor="app.warnBorder" borderRadius="md" px="3" py="2">{i.message}</Text>
            ))}
          </Box>
        )}
      </Box>
      <Box flex="1.4 1 320px" minW="0" bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5">
        <Text fontWeight="semibold" mb="1">Preview</Text>
        <Text fontSize="xs" color="app.muted" mb="3">Edit any bullet or the summary to use your own wording. Unedited text follows your career facts.</Text>
        {!ready && <Text color="app.muted">Fill in the required fields to see the preview.</Text>}
        {ready && preview.isPending && <Text color="app.muted">Building your preview...</Text>}
        {preview.isError && <Text role="alert" color="app.missText">Could not build the preview.</Text>}
        {p && <PreviewEditor doc={p.document} overrides={doc.overrides} onChange={(overrides) => setDoc({ overrides })} />}
      </Box>
    </Box>
  )
}
