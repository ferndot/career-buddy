import { Box, Button, Dialog, Field, Input, NativeSelect, Portal, Text } from '@chakra-ui/react'
import { useState, type FormEvent } from 'react'
import { LuX } from 'react-icons/lu'
import { errorMessage, useCreateConnection, type Provider } from './llmApi'

type Props = { open: boolean; onClose: () => void; providers: Provider[] }

const fieldProps = { bg: 'app.surface', color: 'app.text', borderColor: 'app.borderStrong' } as const

export function AddConnectionDialog({ open, onClose, providers }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={(e) => !e.open && onClose()} placement="center">
      <Portal>
        <Dialog.Backdrop bg="app.scrim" />
        <Dialog.Positioner>
          <Dialog.Content bg="app.surface" color="app.text" borderWidth="1px" borderColor="app.border" mx="4">
            {/* Remounted per open so the form always starts blank. */}
            <AddForm providers={providers} onClose={onClose} />
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}

function AddForm({ providers, onClose }: Omit<Props, 'open'>) {
  const create = useCreateConnection()
  const [presetId, setPresetId] = useState(providers[0]?.id ?? '')
  const [label, setLabel] = useState('')
  const [url, setUrl] = useState('')
  const [model, setModel] = useState('')
  const [key, setKey] = useState('')
  const provider = providers.find((p) => p.id === presetId)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!provider) return
    create.mutate(
      {
        preset: provider.id,
        label: label.trim() || undefined,
        base_url: provider.url_editable ? url.trim() || provider.base_url : undefined,
        model: model.trim(),
        api_key: key || undefined,
      },
      { onSuccess: onClose },
    )
  }

  return (
    <form onSubmit={submit}>
      <Dialog.Header>
        <Dialog.Title color="app.text">Add a connection</Dialog.Title>
      </Dialog.Header>
      <Dialog.CloseTrigger asChild>
        <Button variant="ghost" size="sm" aria-label="Close" color="app.muted"><LuX /></Button>
      </Dialog.CloseTrigger>
      <Dialog.Body display="flex" flexDirection="column" gap="4">
        <Field.Root>
          <Field.Label color="app.text2">Provider</Field.Label>
          <NativeSelect.Root>
            <NativeSelect.Field {...fieldProps} value={presetId}
              onChange={(e) => { setPresetId(e.target.value); setUrl('') }}>
              {providers.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </NativeSelect.Field>
            <NativeSelect.Indicator />
          </NativeSelect.Root>
          {provider && <Field.HelperText color="app.muted">{provider.hint}</Field.HelperText>}
        </Field.Root>
        <Field.Root>
          <Field.Label color="app.text2">Name (optional)</Field.Label>
          <Input {...fieldProps} value={label} onChange={(e) => setLabel(e.target.value)} />
        </Field.Root>
        <Field.Root>
          <Field.Label color="app.text2">Address</Field.Label>
          <Input {...fieldProps} readOnly={!provider?.url_editable}
            value={provider?.url_editable ? url : (provider?.base_url ?? '')}
            placeholder={provider?.base_url || 'https://your-server/v1'}
            onChange={(e) => setUrl(e.target.value)} />
        </Field.Root>
        <Field.Root required>
          <Field.Label color="app.text2">Model</Field.Label>
          <Input {...fieldProps} value={model} onChange={(e) => setModel(e.target.value)} placeholder="e.g. claude-sonnet-5-5" />
        </Field.Root>
        <Field.Root required={provider?.needs_key}>
          <Field.Label color="app.text2">API key</Field.Label>
          <Input {...fieldProps} type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)}
            placeholder={provider?.needs_key ? 'Required' : 'Only if the server asks for one'} />
        </Field.Root>
        {create.isError && (
          <Box bg="app.missBg" color="app.missText" borderRadius="md" px="3" py="2" role="alert">
            <Text fontSize="sm">{errorMessage(create.error)}</Text>
          </Box>
        )}
      </Dialog.Body>
      <Dialog.Footer>
        <Button variant="ghost" color="app.link" onClick={onClose}>Cancel</Button>
        <Button type="submit" bg="app.primary" color="app.onPrimary" loading={create.isPending} disabled={!provider}>
          Save connection
        </Button>
      </Dialog.Footer>
    </form>
  )
}
