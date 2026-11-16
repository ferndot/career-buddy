import { Box, Input, Text } from '@chakra-ui/react'
import { useState } from 'react'

type Props = { models: string[] | null; value: string; onChange: (model: string) => void; fieldProps: object }

/** A searchable list of the models the server reports. With no list (null) it is a plain text field, and says so. */
export function ModelPicker({ models, value, onChange, fieldProps }: Props) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  if (!models) {
    return (
      <>
        <Input {...fieldProps} value={value} onChange={(e) => onChange(e.target.value)} placeholder="e.g. claude-sonnet-5-5" />
        <Text fontSize="sm" color="app.muted">Could not load the model list, so type the model name.</Text>
      </>
    )
  }
  const shown = models.filter((m) => m.toLowerCase().includes(query.trim().toLowerCase()))
  const pick = (m: string) => { onChange(m); setQuery(''); setOpen(false) }
  return (
    <Box position="relative" w="full">
      <Input {...fieldProps} role="combobox" aria-expanded={open} aria-controls="model-options" aria-label="Model"
        placeholder="Search models" value={open ? query : value} autoComplete="off"
        onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => { setOpen(false); setQuery('') }, 150)}
        onChange={(e) => setQuery(e.target.value)} />
      {open && (
        <Box id="model-options" role="listbox" position="absolute" zIndex="dropdown" w="full" maxH="48" overflowY="auto" mt="1"
          bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="md">
          {shown.length === 0 && <Text px="3" py="2" fontSize="sm" color="app.muted">No model matches.</Text>}
          {shown.map((m) => (
            <Box key={m} role="option" aria-selected={m === value} px="3" py="2" fontSize="sm" cursor="pointer" color="app.text"
              fontWeight={m === value ? 'semibold' : 'normal'} _hover={{ bg: 'app.border' }}
              onMouseDown={(e) => { e.preventDefault(); pick(m) }}>
              {m}
            </Box>
          ))}
        </Box>
      )}
    </Box>
  )
}
