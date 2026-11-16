import { Button, Spinner, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { LuPlus } from 'react-icons/lu'
import { EmptyState, PageHeader } from '../../components'
import { AddConnectionDialog } from './AddConnectionDialog'
import { ConnectionCard } from './ConnectionCard'
import { useConnections, useProviders } from './llmApi'

export function SettingsScreen() {
  const [adding, setAdding] = useState(false)
  const connections = useConnections()
  const providers = useProviders()
  const labels = Object.fromEntries((providers.data ?? []).map((p) => [p.id, p.label]))
  const items = connections.data?.connections ?? []

  const addButton = (
    <Button bg="app.primary" color="app.onPrimary" onClick={() => setAdding(true)} disabled={!providers.data}>
      <LuPlus /> Add a connection
    </Button>
  )

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Connect a language model for better rewording. Without one, a built-in reader works offline."
      />
      <Text as="h2" fontWeight="semibold" color="app.text" mb="3">LLM connections</Text>
      {connections.isPending && <Spinner color="app.primary" />}
      {connections.isError && <Text color="app.missText" role="alert">Could not load your connections.</Text>}
      {connections.data && items.length === 0 && (
        <EmptyState title="No connections yet" description="Add one to let an AI model reword your resume.">
          {addButton}
        </EmptyState>
      )}
      {items.map((c) => (
        <ConnectionCard key={c.id} conn={c} active={c.id === connections.data?.active} providerLabel={labels[c.preset] ?? c.preset} />
      ))}
      {items.length > 0 && addButton}
      {providers.data && (
        <AddConnectionDialog open={adding} onClose={() => setAdding(false)} providers={providers.data} />
      )}
    </>
  )
}
