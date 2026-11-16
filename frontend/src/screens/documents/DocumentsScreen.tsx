import { Box, Button, Input, NativeSelect, Text } from '@chakra-ui/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { LuPlus } from 'react-icons/lu'
import { useNavigate } from 'react-router-dom'
import { EmptyState, PageHeader, toaster } from '../../components'
import { DeleteDialog } from './DeleteDialog'
import { deleteSavedDocument, getSavedDocuments, getTemplates, SAVED_KEY, type SavedDocument } from './api'
import { DocumentsTable, type Row } from './DocumentsTable'

export function DocumentsScreen() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const saved = useQuery({ queryKey: SAVED_KEY, queryFn: getSavedDocuments })
  const templates = useQuery({ queryKey: ['templates'], queryFn: getTemplates })
  const docs = saved.data ?? []
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState('')
  const [pending, setPending] = useState<SavedDocument | null>(null)

  const q = query.trim().toLowerCase()
  const rows: Row[] = docs.map((doc) => {
    const t = templates.data?.find((x) => x.id === doc.template)
    return { doc, kind: t?.kind ?? 'other', templateLabel: t?.label ?? doc.template }
  })
  const shown = rows.filter(
    (r) =>
      (!kind || r.kind === kind) &&
      (!q || [r.doc.label, r.doc.filename, r.templateLabel].some((s) => s.toLowerCase().includes(q))),
  )
  const del = useMutation({
    mutationFn: (doc: SavedDocument) => deleteSavedDocument(doc.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: SAVED_KEY }),
    onError: () => toaster.create({ type: 'error', title: 'Could not delete that document' }),
    onSettled: () => setPending(null),
  })
  const generate = () => navigate('/documents/new')
  const generateButton = (
    <Button bg="app.primary" color="app.onPrimary" onClick={generate}>
      <LuPlus /> Generate
    </Button>
  )

  return (
    <>
      <PageHeader
        title="Documents"
        subtitle="Documents you have generated. Download any of them, or make a new one."
        actions={generateButton}
      />
      {saved.isPending ? (
        <Text color="app.muted">Loading your documents...</Text>
      ) : saved.isError ? (
        <Text role="alert" color="app.missText">Could not load your documents.</Text>
      ) : docs.length === 0 ? (
        <EmptyState title="No documents yet" description="Create a resume or cover letter from a job posting.">
          {generateButton}
        </EmptyState>
      ) : (
        <>
          <Box display="flex" gap="3" flexWrap="wrap" mb="4">
            <Input
              type="search"
              placeholder="Search documents"
              aria-label="Search documents"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              flex="1 1 240px"
              maxW="360px"
              bg="app.surface"
              borderColor="app.borderStrong"
              color="app.text"
            />
            <NativeSelect.Root flex="0 1 180px" w="auto">
              <NativeSelect.Field
                aria-label="Document type"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
                bg="app.surface"
                borderColor="app.borderStrong"
                color="app.text"
              >
                <option value="">All types</option>
                <option value="resume">Resume</option>
                <option value="letter">Cover letter</option>
                <option value="other">Other</option>
              </NativeSelect.Field>
              <NativeSelect.Indicator />
            </NativeSelect.Root>
          </Box>
          {shown.length ? (
            <DocumentsTable rows={shown} onDelete={setPending} />
          ) : (
            <EmptyState title="No matches" description="Try a different search or type." />
          )}
        </>
      )}
      <DeleteDialog doc={pending} onCancel={() => setPending(null)} onConfirm={(d) => del.mutate(d)} />
    </>
  )
}
