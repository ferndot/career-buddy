import { Box, Button, CloseButton, Dialog, Field, Input, Portal, Text, Textarea } from '@chakra-ui/react'
import { useRef, useState } from 'react'
import { LuUpload } from 'react-icons/lu'
import { useImportSource } from './sourcesApi'

type Props = { open: boolean; onClose: () => void }

export function AddSourceDialog({ open, onClose }: Props) {
  const [name, setName] = useState('')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [drag, setDrag] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const add = useImportSource()

  const reset = () => {
    setName('')
    setText('')
    setFile(null)
    add.reset()
    onClose()
  }
  // A file needs nothing else; typed text needs a name and details.
  const canImport = file !== null || (name.trim() !== '' && text.trim() !== '')
  const submit = () => {
    const src = file
      ? ({ kind: 'file', file } as const)
      : ({ kind: 'text', name: name.trim(), text } as const)
    add.mutate(src, { onSuccess: reset })
  }
  const pick = (f?: File) => f && setFile(f)
  const browse = () => fileInput.current?.click()

  return (
    <Dialog.Root open={open} onOpenChange={(e) => !e.open && reset()} placement="center">
      <Portal>
        <Dialog.Backdrop bg="app.scrim" />
        <Dialog.Positioner>
          <Dialog.Content bg="app.surface" color="app.text" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="6">
            <Dialog.Header p="0" mb="4">
              <Dialog.Title fontSize="md">Add a source</Dialog.Title>
              <Dialog.CloseTrigger asChild>
                <CloseButton aria-label="Close" size="sm" />
              </Dialog.CloseTrigger>
            </Dialog.Header>
            <Dialog.Body p="0">
              <Box
                role="button"
                tabIndex={0}
                aria-label="Drop files here or browse"
                textAlign="center"
                p="7"
                borderWidth="2px"
                borderStyle="dashed"
                borderColor="app.dash"
                borderRadius="lg"
                cursor="pointer"
                bg={drag ? 'app.hover' : 'app.surface'}
                onClick={browse}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && browse()}
                onDragOver={(e) => {
                  e.preventDefault()
                  setDrag(true)
                }}
                onDragLeave={() => setDrag(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setDrag(false)
                  pick(e.dataTransfer.files[0])
                }}
              >
                <Box color="app.primary" fontSize="xl" display="flex" justifyContent="center">
                  <LuUpload />
                </Box>
                <Text fontWeight="semibold" fontSize="sm">
                  {file ? (
                    file.name
                  ) : (
                    <>
                      Drop files here or{' '}
                      <Text as="span" color="app.link" textDecoration="underline">
                        browse
                      </Text>
                    </>
                  )}
                </Text>
                <Text fontSize="sm" color="app.muted" mt="1.5">
                  PDF, DOCX, TXT, MD
                </Text>
                <input
                  ref={fileInput}
                  type="file"
                  hidden
                  data-testid="source-file"
                  accept=".pdf,.docx,.txt,.md"
                  onChange={(e) => pick(e.target.files?.[0])}
                />
              </Box>
              <Text textAlign="center" fontSize="xs" color="app.muted" textTransform="uppercase" letterSpacing="wider" my="5">
                or enter text
              </Text>
              <Box borderWidth="1px" borderColor="app.border" borderRadius="lg" p="4">
                <Field.Root required mb="3">
                  <Field.Label fontSize="sm" color="app.text2">
                    Name
                  </Field.Label>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="For example, Resume 2026"
                    borderColor="app.borderStrong"
                  />
                </Field.Root>
                <Field.Root>
                  <Field.Label fontSize="sm" color="app.text2">
                    Details
                  </Field.Label>
                  <Textarea
                    rows={6}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder={'Jane Doe\n\nExperience\nSenior Engineer at Acme, 2019 - 2023'}
                    borderColor="app.borderStrong"
                  />
                </Field.Root>
              </Box>
              {add.isError && (
                <Text role="alert" color="app.missText" fontSize="sm" mt="3">
                  Import failed. Check the file type and try again.
                </Text>
              )}
            </Dialog.Body>
            <Dialog.Footer p="0" mt="4" gap="2">
              <Button variant="ghost" color="app.link" onClick={reset}>
                Cancel
              </Button>
              <Button bg="app.primary" color="app.onPrimary" disabled={!canImport} loading={add.isPending} onClick={submit}>
                Import
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}
