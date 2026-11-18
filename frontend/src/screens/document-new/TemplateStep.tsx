import { Box, Field, Input, Text } from '@chakra-ui/react'
import type { Template } from '../documents/api'
import { Wireframe } from './Wireframe'
import { Directions } from './Directions'
import { styleOf, type DocDraft, type DocKind, type Wizard } from './state'

type Props = { w: Wizard; kind: DocKind; templates: Template[]; setDoc: (patch: Partial<DocDraft>) => void }

const field = { bg: 'app.surface', borderColor: 'app.borderStrong', color: 'app.text' } as const

/** Step 4: choose the template (and a letter's style), fill its inputs, give the writer directions, and see the template's layout as a wireframe. */
export function TemplateStep({ w, kind, templates, setDoc }: Props) {
  const doc = w.docs[kind]
  const choices = templates.filter((t) => t.kind === kind)
  const chosen = templates.find((t) => t.id === doc.templateId)
  const fields = chosen ? [...chosen.required, ...chosen.optional] : []
  return (
    <Box display="flex" gap="6" flexWrap="wrap" alignItems="flex-start">
      <Box flex="1 1 280px" minW="0" bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5" display="flex" flexDirection="column" gap="5">
        <Box>
          <Text fontWeight="semibold" fontSize="sm" mb="2">Template</Text>
          <Box display="grid" gridTemplateColumns="repeat(auto-fill, minmax(160px, 1fr))" gap="3" role="radiogroup" aria-label="Template">
            {choices.map((t) => {
              const on = t.id === doc.templateId
              return (
                <Box key={t.id} as="button" role="radio" aria-checked={on} aria-label={t.label} textAlign="left" p="3" borderRadius="md" borderWidth="2px" borderColor={on ? 'app.primary' : 'app.border'} bg={on ? 'app.activeBg' : 'app.surface2'} color={on ? 'app.activeText' : 'app.text'} cursor="pointer" onClick={() => setDoc({ templateId: t.id, styleId: '', inputs: {}, sections: [], flags: {}, genError: undefined })}>
                  <Text fontWeight="semibold" fontSize="sm">{t.label}</Text>
                  {t.ats_safe && <Text as="span" fontSize="xs" color="app.text2">ATS-safe</Text>}
                </Box>
              )
            })}
          </Box>
        </Box>
        {chosen && chosen.styles.length > 0 && (
          <Box>
            <Text fontWeight="semibold" fontSize="sm" mb="2">Writing style</Text>
            <Box display="grid" gridTemplateColumns="repeat(auto-fill, minmax(160px, 1fr))" gap="3" role="radiogroup" aria-label="Writing style">
              {chosen.styles.map((s) => {
                const on = s.id === styleOf(doc, chosen)?.id
                return (
                  <Box key={s.id} as="button" role="radio" aria-checked={on} textAlign="left" p="3" borderRadius="md" borderWidth="2px" borderColor={on ? 'app.primary' : 'app.border'} bg={on ? 'app.activeBg' : 'app.surface2'} color={on ? 'app.activeText' : 'app.text'} cursor="pointer" onClick={() => setDoc({ styleId: s.id, sections: [], flags: {}, genError: undefined })}>
                    <Text fontWeight="semibold" fontSize="sm">{s.label}</Text>
                  </Box>
                )
              })}
            </Box>
          </Box>
        )}
        {fields.map((f) => (
          <Field.Root key={f} required={chosen?.required.includes(f)}>
            <Field.Label color="app.text2" textTransform="capitalize">{f.replace('_', ' ')}<Field.RequiredIndicator /></Field.Label>
            <Input {...field} value={doc.inputs[f] ?? ''} onChange={(e) => setDoc({ inputs: { ...doc.inputs, [f]: e.target.value } })} />
          </Field.Root>
        ))}
        <Directions key={kind} kind={kind} doc={doc} setDoc={setDoc} />
      </Box>
      <Box flex="1.4 1 320px" minW="0">
        {chosen && <Wireframe template={chosen} />}
      </Box>
    </Box>
  )
}
