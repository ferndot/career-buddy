import { Box, Button, Table, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { downloadSaved, type SavedDocument } from './api'

export const KIND_LABEL = { resume: 'Resume', letter: 'Cover letter' } as const
export type Kind = keyof typeof KIND_LABEL

export function AtsTag({ issues }: { issues: number }) {
  const ok = issues === 0
  return (
    <Text
      as="span"
      fontSize="xs"
      fontWeight="medium"
      px="2"
      py="0.5"
      borderRadius="full"
      bg={ok ? 'app.okBg' : 'app.warnBg'}
      color={ok ? 'app.okText' : 'app.warnText'}
    >
      {ok ? 'OK' : `${issues} warning${issues > 1 ? 's' : ''}`}
    </Text>
  )
}

const cell = { borderColor: 'app.border' } as const

export type Row = { doc: SavedDocument; kind: Kind | null; templateLabel: string }
type Props = { rows: Row[]; onDelete: (doc: SavedDocument) => void }

export function DocumentsTable({ rows, onDelete }: Props) {
  const [error, setError] = useState('')
  const get = (doc: SavedDocument) =>
    downloadSaved(doc).then(
      () => setError(''),
      (e: Error) => setError(`${doc.label}: ${e.message}`),
    )
  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" overflowX="auto">
      <Table.Root size="md" variant="line" color="app.text">
        <Table.Header>
          <Table.Row bg="transparent">
            {['Name', 'Type', 'Template', 'Format', 'Created', 'ATS', 'Download'].map((h) => (
              <Table.ColumnHeader key={h} color="app.muted" textTransform="uppercase" fontSize="xs" letterSpacing="wider" {...cell}>
                {h}
              </Table.ColumnHeader>
            ))}
            <Table.ColumnHeader {...cell}>
              <span style={{ position: 'absolute', left: -9999 }}>Actions</span>
            </Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {rows.map(({ doc: d, kind, templateLabel }) => (
            <Table.Row key={d.id} bg="transparent">
              <Table.Cell fontWeight="semibold" {...cell}>{d.label}</Table.Cell>
              <Table.Cell {...cell}>{kind ? KIND_LABEL[kind] : '—'}</Table.Cell>
              <Table.Cell {...cell}>{templateLabel}</Table.Cell>
              <Table.Cell {...cell}>{d.format.toUpperCase()}</Table.Cell>
              <Table.Cell whiteSpace="nowrap" {...cell}>
                {new Date(d.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
              </Table.Cell>
              <Table.Cell {...cell}><AtsTag issues={d.ats_issues.length} /></Table.Cell>
              <Table.Cell {...cell}>
                <Button
                  size="sm"
                  variant="outline"
                  borderColor="app.borderStrong"
                  color="app.text"
                  aria-label={`Download ${d.label}`}
                  onClick={() => void get(d)}
                >
                  Download
                </Button>
              </Table.Cell>
              <Table.Cell {...cell}>
                <Button size="sm" variant="ghost" color="app.link" aria-label={`Delete ${d.label}`} onClick={() => onDelete(d)}>
                  Delete
                </Button>
              </Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
      {error && (
        <Text role="alert" color="app.missText" bg="app.missBg" fontSize="sm" px="4" py="2">
          {error}
        </Text>
      )}
    </Box>
  )
}
