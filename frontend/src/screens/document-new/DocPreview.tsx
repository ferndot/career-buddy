import { Box, Text } from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'
import { LoadingState } from '../../components'
import { AtsTag } from '../documents/DocumentsTable'
import { previewQuery } from '../documents/api'
import { shown } from './layout'
import { PreviewEditor } from './PreviewEditor'
import { buildBody, type DocDraft, type DocKind, type Wizard } from './state'

type Props = { w: Wizard; kind: DocKind; ready: boolean; setDoc: (patch: Partial<DocDraft>) => void; editable: boolean }

/** The document as it will be. On the template step it is the facts' text (read only); on the last step it is the
 * written text, editable, with the ATS check. */
export function DocPreview({ w, kind, ready, setDoc, editable }: Props) {
  const doc = w.docs[kind]
  const preview = useQuery({ ...previewQuery(buildBody(w, kind)), enabled: ready }) // the facts' text: written and edited text is laid over it
  const p = preview.data
  const view = p && shown(p.document, doc, kind)
  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5" display="flex" flexDirection="column" gap="4" minW="0">
      <Box>
        <Text fontWeight="semibold" mb="1">Preview</Text>
        <Text fontSize="xs" color="app.muted">
          {editable
            ? 'Edit the summary, a bullet or a letter paragraph to use your own wording. Unedited text is the written text, or your career facts.'
            : 'This is your career facts laid out in the template. The text is written on the next step.'}
        </Text>
      </Box>
      {!ready && <Text color="app.muted">Fill in the required fields to see the preview.</Text>}
      {ready && preview.isPending && <LoadingState text="Building your preview..." />}
      {preview.isError && <Text role="alert" color="app.missText">Could not build the preview.</Text>}
      {view && <PreviewEditor doc={view.doc} defaults={view.defaults} generated={doc.generated} flags={doc.flags} overrides={doc.overrides} onChange={(overrides) => setDoc({ overrides })} readOnly={!editable} />}
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
  )
}
