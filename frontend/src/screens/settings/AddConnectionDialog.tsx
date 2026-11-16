import { Box, Button, Dialog, Field, Input, NativeSelect, Portal, Text } from '@chakra-ui/react'
import { useEffect, useState, type FormEvent } from 'react'
import { LuX } from 'react-icons/lu'
import { errorMessage, useCreateConnection, useModelList, useUpdateConnection, type Connection, type ModelRequest, type Provider } from './llmApi'
import { ModelPicker } from './ModelPicker'

/** `conn` set means edit mode: the form starts filled in and a blank key keeps the saved one. */
type Props = { open: boolean; onClose: () => void; providers: Provider[]; conn?: Connection }

const fieldProps = { bg: 'app.surface', color: 'app.text', borderColor: 'app.borderStrong' } as const

export function AddConnectionDialog({ open, onClose, providers, conn }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={(e) => !e.open && onClose()} placement="center">
      <Portal>
        <Dialog.Backdrop bg="app.scrim" />
        <Dialog.Positioner>
          <Dialog.Content bg="app.surface" color="app.text" borderWidth="1px" borderColor="app.border" mx="4">
            {/* Remounted per open so the form always starts fresh. */}
            <AddForm key={conn?.id ?? 'new'} providers={providers} onClose={onClose} conn={conn} />
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}

function AddForm({ providers, onClose, conn }: Omit<Props, 'open'>) {
  const create = useCreateConnection()
  const update = useUpdateConnection()
  const save = conn ? update : create
  const [presetId, setPresetId] = useState(conn?.preset ?? providers[0]?.id ?? '')
  const [label, setLabel] = useState(conn?.label ?? '')
  const [url, setUrl] = useState(conn?.base_url ?? '')
  const [model, setModel] = useState(conn?.model ?? '')
  const [key, setKey] = useState('')
  const provider = providers.find((p) => p.id === presetId)
  const urlChanged = !!conn && provider?.url_editable && url.trim() !== conn.base_url

  // Ask the server which models it has: at once for a saved connection, after a pause for a draft being typed.
  const models = useModelList()
  const { mutate: loadModels, reset: resetModels } = models
  const request: ModelRequest | null = conn ? { id: conn.id }
    : provider && (key || !provider.needs_key)
      ? { preset: provider.id, base_url: provider.url_editable ? url.trim() || undefined : undefined, api_key: key || undefined }
      : null
  const requestKey = JSON.stringify(request)
  useEffect(() => {
    if (!request) return resetModels()
    const timer = setTimeout(() => loadModels(request), conn ? 0 : 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey])
  const list = models.data?.ok && models.data.models.length > 0 ? models.data.models : null

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!provider) return
    const fields = {
      label: label.trim() || undefined,
      base_url: provider.url_editable ? url.trim() || provider.base_url : undefined,
      model: model.trim(),
      api_key: key || undefined, // blank means "keep the saved key"
    }
    if (conn) update.mutate({ id: conn.id, ...fields }, { onSuccess: onClose })
    else create.mutate({ preset: provider.id, ...fields }, { onSuccess: onClose })
  }

  return (
    <form onSubmit={submit}>
      <Dialog.Header>
        <Dialog.Title color="app.text">{conn ? 'Edit connection' : 'Add a connection'}</Dialog.Title>
      </Dialog.Header>
      <Dialog.CloseTrigger asChild>
        <Button variant="ghost" size="sm" aria-label="Close" color="app.muted"><LuX /></Button>
      </Dialog.CloseTrigger>
      <Dialog.Body display="flex" flexDirection="column" gap="4">
        <Field.Root>
          <Field.Label color="app.text2">Name (optional)</Field.Label>
          <Input {...fieldProps} value={label} onChange={(e) => setLabel(e.target.value)} />
        </Field.Root>
        <Field.Root>
          <Field.Label color="app.text2">Provider</Field.Label>
          <NativeSelect.Root disabled={!!conn}>
            <NativeSelect.Field {...fieldProps} value={presetId}
              onChange={(e) => { setPresetId(e.target.value); setUrl('') }}>
              {providers.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </NativeSelect.Field>
            <NativeSelect.Indicator />
          </NativeSelect.Root>
          {provider && <Field.HelperText color="app.muted">{provider.hint}</Field.HelperText>}
        </Field.Root>
        <Field.Root>
          <Field.Label color="app.text2">Address</Field.Label>
          <Input {...fieldProps} readOnly={!provider?.url_editable}
            value={provider?.url_editable ? url : (provider?.base_url ?? '')}
            placeholder={provider?.base_url || 'https://your-server/v1'}
            onChange={(e) => setUrl(e.target.value)} />
        </Field.Root>
        <Field.Root required={!conn && provider?.needs_key}>
          <Field.Label color="app.text2">API key</Field.Label>
          <Input {...fieldProps} type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)}
            placeholder={conn ? 'Leave blank to keep the saved key' : provider?.needs_key ? 'Required' : 'Only if the server asks for one'} />
          {urlChanged && <Field.HelperText color="app.muted">Changing the address removes the saved key, so enter the key again if the server needs one.</Field.HelperText>}
        </Field.Root>
        <Field.Root required>
          <Field.Label color="app.text2">Model</Field.Label>
          {models.isPending && <Text fontSize="sm" color="app.muted">Loading models...</Text>}
          {!models.isPending && <ModelPicker models={list} value={model} onChange={setModel} fieldProps={fieldProps} />}
        </Field.Root>
        {save.isError && (
          <Box bg="app.missBg" color="app.missText" borderRadius="md" px="3" py="2" role="alert">
            <Text fontSize="sm">{errorMessage(save.error)}</Text>
          </Box>
        )}
      </Dialog.Body>
      <Dialog.Footer>
        <Button variant="ghost" color="app.link" onClick={onClose}>Cancel</Button>
        <Button type="submit" bg="app.primary" color="app.onPrimary" loading={save.isPending} disabled={!provider || !model.trim()}>
          {conn ? 'Save changes' : 'Save connection'}
        </Button>
      </Dialog.Footer>
    </form>
  )
}
