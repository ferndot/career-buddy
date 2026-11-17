import { Box, Text } from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'
import { LoadingState } from '../../components'
import { AtsTag } from '../documents/DocumentsTable'
import { previewQuery, type Template } from '../documents/api'
import { shown } from './layout'
import { PreviewEditor } from './PreviewEditor'
import { buildBody, kindLabel, type DocDraft, type DocKind, type Wizard } from './state'

type Props = { w: Wizard; kind: DocKind; template: Template | undefined; ready: boolean; setDoc: (patch: Partial<DocDraft>) => void }

/** What the document is called: the kind with the name for a resume, with the company (else the role) for a letter. */
export const documentTitle = (kind: DocKind, name: string, inputs: Record<string, string>) =>
  [kindLabel(kind), (kind === 'letter' ? inputs.company || inputs.role : '') || name].filter(Boolean).join(' - ')

/** The last step's document: the written text on a white sheet in the template's layout, editable, with the ATS check. */
export function DocPreview({ w, kind, template, ready, setDoc }: Props) {
  const doc = w.docs[kind]
  const body = buildBody(w, kind)
  const preview = useQuery({ ...previewQuery(body), enabled: ready }) // the facts' text: written and edited text is laid over it
  const p = preview.data
  const view = p && shown(p.document, doc, kind)
  const title = documentTitle(kind, p?.document.name.text ?? '', body.inputs)
  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5" display="flex" flexDirection="column" gap="4" minW="0">
      <Box>
        <Text as="h2" fontWeight="semibold" mb="1">{title}</Text>
        <Text fontSize="xs" color="app.muted">Edit the summary, a bullet or a letter paragraph to use your own wording. Unedited text is the written text, or your career facts.</Text>
      </Box>
      {!ready && <Text color="app.muted">Fill in the required fields to see the preview.</Text>}
      {ready && preview.isPending && <LoadingState text="Building your preview..." />}
      {preview.isError && <Text role="alert" color="app.missText">Could not build the preview.</Text>}
      {view && template && <PreviewEditor doc={view.doc} layout={template.layout} title={title} defaults={view.defaults} generated={doc.generated} flags={doc.flags} overrides={doc.overrides} onChange={(overrides) => setDoc({ overrides })} />}
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
