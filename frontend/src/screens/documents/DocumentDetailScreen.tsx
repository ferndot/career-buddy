import { Box, Link, Text } from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link as RouterLink, useParams } from 'react-router-dom'
import { LoadingState, PageHeader } from '../../components'
import { scopeCss, sheetCss } from '../document-new/sheet'
import { getSavedContent, getSavedDocuments, getTemplates, SAVED_KEY } from './api'
import { DownloadMenu } from './DownloadMenu'
import { KIND_LABEL } from './DocumentsTable'
import { filledLayout, listingLink } from './savedPreview'

/** One saved document: what it is named for, the listing it was written for, and the document as it reads now (read-only). */
export function DocumentDetailScreen() {
  const { id = '' } = useParams()
  const saved = useQuery({ queryKey: SAVED_KEY, queryFn: getSavedDocuments })
  const templates = useQuery({ queryKey: ['templates'], queryFn: getTemplates })
  const content = useQuery({ queryKey: ['saved-content', id], queryFn: () => getSavedContent(id) })
  const [error, setError] = useState('')
  const doc = saved.data?.find((d) => d.id === id)
  const template = templates.data?.find((t) => t.id === doc?.template)
  const link = listingLink(content.data?.source?.job_url)
  const back = <Link asChild color="app.link" fontSize="sm"><RouterLink to="/documents">All documents</RouterLink></Link>

  if (saved.isPending || content.isPending) return <LoadingState text="Loading the document..." />
  if (!doc || content.isError) return <Box display="flex" flexDirection="column" gap="3"><Text role="alert" color="app.missText">Could not find that document.</Text>{back}</Box>
  return (
    <>
      <PageHeader title={doc.label} subtitle={[template ? KIND_LABEL[template.kind] : '', template?.label ?? doc.template].filter(Boolean).join(' · ')} actions={<DownloadMenu doc={doc} onResult={setError} />} />
      <Box display="flex" flexDirection="column" gap="4">
        {back}
        <Text>
          Job listing:{' '}
          {link ? <Link href={link} target="_blank" rel="noopener noreferrer" color="app.link">{link}</Link> : <Text as="span" color="app.muted">No link saved</Text>}
        </Text>
        {error && <Text role="alert" color="app.missText" bg="app.missBg" fontSize="sm" px="4" py="2">{error}</Text>}
        <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5">
          <Box borderWidth="1px" borderColor="#d5d9e0" borderRadius="md" boxShadow="sm" overflow="hidden">
            <style>{template ? sheetCss(template.layout) : scopeCss(content.data.css, '.sheet')}</style>
            <div className="sheet" role="document" aria-label={`Preview of ${doc.label}`} dangerouslySetInnerHTML={{ __html: filledLayout(content.data.html, content.data.slots) }} />
          </Box>
        </Box>
      </Box>
    </>
  )
}
