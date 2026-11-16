import { Badge, Box, Button, Text } from '@chakra-ui/react'
import { LuCheck, LuPencil, LuPlugZap, LuTrash2 } from 'react-icons/lu'
import { errorMessage, useDeleteConnection, useSetActive, useTestConnection, type Connection } from './llmApi'

type Props = { conn: Connection; active: boolean; providerLabel: string; onEdit: (conn: Connection) => void }

export function ConnectionCard({ conn, active, providerLabel, onEdit }: Props) {
  const test = useTestConnection()
  const del = useDeleteConnection()
  const setActive = useSetActive()
  const result = test.data
  const failed = test.isError ? errorMessage(test.error) : result && !result.ok ? result.message : null

  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" px="5" py="4" mb="3">
      <Box display="flex" alignItems="center" gap="3" flexWrap="wrap">
        <Box flex="1" minW="200px">
          <Box display="flex" alignItems="center" gap="2" flexWrap="wrap">
            <Text fontWeight="semibold" color="app.text">{conn.label}</Text>
            {active && (
              <Badge bg="app.okBg" color="app.okText" borderRadius="full" px="2">
                <LuCheck /> Active
              </Badge>
            )}
          </Box>
          <Text color="app.muted" fontSize="sm">
            {providerLabel} · {conn.model} · {conn.base_url}
            {conn.key_hint ? ` · key ${conn.key_hint}` : ' · no key'}
          </Text>
        </Box>
        <Button size="sm" variant="outline" borderColor="app.borderStrong" color="app.text" loading={test.isPending}
          onClick={() => test.mutate(conn.id)}>
          <LuPlugZap /> Test
        </Button>
        {!active && (
          <Button size="sm" variant="outline" borderColor="app.borderStrong" color="app.text" loading={setActive.isPending}
            onClick={() => setActive.mutate(conn.id)}>
            Set active
          </Button>
        )}
        {!conn.read_only && (
          <Button size="sm" variant="outline" borderColor="app.borderStrong" color="app.text" onClick={() => onEdit(conn)}
            aria-label={`Edit ${conn.label}`}>
            <LuPencil /> Edit
          </Button>
        )}
        {!conn.read_only && (
          <Button size="sm" variant="ghost" color="app.link" loading={del.isPending} onClick={() => del.mutate(conn.id)}
            aria-label={`Delete ${conn.label}`}>
            <LuTrash2 /> Delete
          </Button>
        )}
      </Box>
      {result?.ok && <Text mt="2" fontSize="sm" color="app.okText" bg="app.okBg" borderRadius="md" px="2" py="1">{result.message}</Text>}
      {failed && <Text mt="2" fontSize="sm" color="app.missText" bg="app.missBg" borderRadius="md" px="2" py="1" role="alert">{failed}</Text>}
    </Box>
  )
}
