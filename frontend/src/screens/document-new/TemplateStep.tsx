import { Box, Button, Field, Input, Text } from '@chakra-ui/react'
import type { Template } from '../documents/api'
import type { Wizard } from './state'

const KINDS = [
  { id: 'resume', label: 'Resume' },
  { id: 'letter', label: 'Cover letter and notes' },
  { id: 'other', label: 'Other' },
] as const

type Props = { w: Wizard; templates: Template[]; set: (patch: Partial<Wizard>) => void }

export function TemplateStep({ w, templates, set }: Props) {
  const choices = templates.filter((t) => t.kind === w.kind)
  const chosen = templates.find((t) => t.id === w.templateId)
  const fields = chosen ? [...chosen.required, ...chosen.optional] : []
  const pick = (kind: Wizard['kind']) => set({ kind, templateId: templates.find((t) => t.kind === kind)?.id ?? '', inputs: {}, prefilled: false })
  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5" display="flex" flexDirection="column" gap="5">
      <Box>
        <Text fontWeight="semibold" fontSize="sm" mb="2">Type</Text>
        <Box display="flex" gap="2" flexWrap="wrap" role="group" aria-label="Document type">
          {KINDS.map((k) => (
            <Button key={k.id} size="sm" borderRadius="full" variant={w.kind === k.id ? 'solid' : 'outline'} bg={w.kind === k.id ? 'app.activeBg' : 'app.surface'} color={w.kind === k.id ? 'app.activeText' : 'app.text'} borderColor="app.borderStrong" aria-pressed={w.kind === k.id} onClick={() => pick(k.id)}>
              {k.label}
            </Button>
          ))}
        </Box>
      </Box>
      <Box>
        <Text fontWeight="semibold" fontSize="sm" mb="2">Template</Text>
        <Box display="grid" gridTemplateColumns="repeat(auto-fill, minmax(200px, 1fr))" gap="3" role="radiogroup" aria-label="Template">
          {choices.map((t) => {
            const on = t.id === w.templateId
            return (
              <Box key={t.id} as="button" role="radio" aria-checked={on} textAlign="left" p="3" borderRadius="md" borderWidth="2px" borderColor={on ? 'app.primary' : 'app.border'} bg={on ? 'app.activeBg' : 'app.surface2'} color={on ? 'app.activeText' : 'app.text'} cursor="pointer" onClick={() => set({ templateId: t.id, inputs: {}, prefilled: false })}>
                <Text fontWeight="semibold" fontSize="sm">{t.label}</Text>
                <Text fontSize="xs" color="app.muted">{t.formats.slice(0, 5).join(', ').toUpperCase()}</Text>
              </Box>
            )
          })}
        </Box>
      </Box>
      {fields.length > 0 && (
        <Box display="grid" gridTemplateColumns="repeat(auto-fit, minmax(220px, 1fr))" gap="4">
          {fields.map((f) => (
            <Field.Root key={f} required={chosen?.required.includes(f)}>
              <Field.Label color="app.text2" textTransform="capitalize">{f.replace('_', ' ')}<Field.RequiredIndicator /></Field.Label>
              <Input value={w.inputs[f] ?? ''} onChange={(e) => set({ inputs: { ...w.inputs, [f]: e.target.value } })} bg="app.surface" borderColor="app.borderStrong" color="app.text" />
            </Field.Root>
          ))}
        </Box>
      )}
    </Box>
  )
}
