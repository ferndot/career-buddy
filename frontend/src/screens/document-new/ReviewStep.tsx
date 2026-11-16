import { Box, Button, Text } from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { LuDownload } from 'react-icons/lu'
import { downloadDocument, getPreview, type Template } from '../documents/api'
import { AtsTag } from '../documents/DocumentsTable'
import { buildBody, pickFormat, type Wizard } from './state'

type Props = { w: Wizard; template: Template; set: (patch: Partial<Wizard>) => void }

export function ReviewStep({ w, template, set }: Props) {
  const [error, setError] = useState('')
  const body = buildBody(w)
  const preview = useQuery({
    queryKey: ['document-preview', body, w.format],
    queryFn: () => getPreview(body, pickFormat(w, template)),
  })
  const formats = (['docx', 'pdf'] as const).filter((f) => template.formats.includes(f))
  const get = (fmt: string) =>
    downloadDocument(body, fmt).then(
      () => setError(''),
      (e: Error) => setError(e.message),
    )
  const p = preview.data
  return (
    <Box display="flex" gap="6" flexWrap="wrap" alignItems="flex-start">
      <Box flex="1.4 1 420px" minW="0" bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5">
        <Text fontWeight="semibold" mb="3">Preview</Text>
        {preview.isPending && <Text color="app.muted">Building your preview...</Text>}
        {preview.isError && <Text role="alert" color="app.missText">Could not build the preview.</Text>}
        {p && (
          <Box bg="app.surface2" borderWidth="1px" borderColor="app.border" borderRadius="md" p="4" fontSize="13px" color="app.text2" maxH="480px" overflowY="auto">
            {p.lines.map((line, i) => (
              <Text key={i} fontWeight={i === 0 ? 'bold' : 'normal'} minH="1.2em">{line}</Text>
            ))}
          </Box>
        )}
      </Box>
      <Box as="aside" flex="1 1 260px" minW="0" bg="app.surface2" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5" display="flex" flexDirection="column" gap="3">
        <Text fontWeight="semibold" fontSize="sm">ATS check</Text>
        {p && (
          <>
            <Box><AtsTag issues={p.ats.issues.length} /></Box>
            {p.ats.issues.map((i) => (
              <Text key={i.code} fontSize="13px" color="app.warnText" bg="app.warnPanel" borderWidth="1px" borderColor="app.warnBorder" borderRadius="md" px="3" py="2">
                {i.message}
              </Text>
            ))}
            {p.tailoring.missing.length > 0 && (
              <Text fontSize="13px" color="app.text3">Not in your profile: {p.tailoring.missing.slice(0, 6).join(', ')}.</Text>
            )}
          </>
        )}
        <Text fontWeight="semibold" fontSize="sm" mt="2">Format to save</Text>
        <Box display="flex" gap="2" flexWrap="wrap" role="group" aria-label="Format to save">
          {template.formats.map((f) => (
            <Button key={f} size="sm" borderRadius="full" variant={pickFormat(w, template) === f ? 'solid' : 'outline'} bg={pickFormat(w, template) === f ? 'app.activeBg' : 'app.surface'} color={pickFormat(w, template) === f ? 'app.activeText' : 'app.text'} borderColor="app.borderStrong" aria-pressed={pickFormat(w, template) === f} onClick={() => set({ format: f })}>
              {f.toUpperCase()}
            </Button>
          ))}
        </Box>
        <Text fontSize="13px" color="app.text3">Press Done to save it to your documents.</Text>
        <Text fontWeight="semibold" fontSize="sm" mt="2">Download now</Text>
        <Box display="flex" gap="2" flexWrap="wrap">
          {formats.map((f) => (
            <Button key={f} bg="app.primary" color="app.onPrimary" disabled={!p} onClick={() => void get(f)}>
              <LuDownload /> {f.toUpperCase()}
            </Button>
          ))}
        </Box>
        {error && <Text role="alert" fontSize="13px" color="app.missText" bg="app.missBg" borderRadius="md" px="3" py="2">{error}</Text>}
      </Box>
    </Box>
  )
}
