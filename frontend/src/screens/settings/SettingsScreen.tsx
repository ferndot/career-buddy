import { Button, Spinner, Tabs, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { LuPlus } from 'react-icons/lu'
import { EmptyState, PageHeader } from '../../components'
import { AddConnectionDialog } from './AddConnectionDialog'
import { AppearanceSettings } from './AppearanceSettings'
import { ConnectionCard } from './ConnectionCard'
import { useConnections, useProviders, type Connection } from './llmApi'

export function SettingsScreen() {
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<Connection | undefined>()
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
        subtitle="Connect a language model to reword resumes. Works offline without one."
      />
      <Tabs.Root defaultValue="connections" variant="line">
        <Tabs.List mb="5">
          <Tabs.Trigger value="connections">LLM connections</Tabs.Trigger>
          <Tabs.Trigger value="appearance">Appearance</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="connections">
          <Text as="h2" fontWeight="semibold" color="app.text" mb="3">LLM connections</Text>
          {connections.isPending && <Spinner color="app.primary" />}
          {connections.isError && <Text color="app.missText" role="alert">Could not load your connections.</Text>}
          {connections.data && items.length === 0 && (
            <EmptyState title="No connections yet" description="Add one to let an AI model reword your resume.">
              {addButton}
            </EmptyState>
          )}
          {items.map((c) => (
            <ConnectionCard key={c.id} conn={c} active={c.id === connections.data?.active} providerLabel={labels[c.preset] ?? c.preset}
              onEdit={setEditing} />
          ))}
          {items.length > 0 && addButton}
        </Tabs.Content>
        <Tabs.Content value="appearance">
          <AppearanceSettings />
        </Tabs.Content>
      </Tabs.Root>
      {providers.data && (
        <AddConnectionDialog open={adding || !!editing} conn={editing} providers={providers.data}
          onClose={() => { setAdding(false); setEditing(undefined) }} />
      )}
    </>
  )
}
