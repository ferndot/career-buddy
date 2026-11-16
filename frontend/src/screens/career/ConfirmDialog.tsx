import { Button, Dialog, Portal, Text } from '@chakra-ui/react'
import type { ReactNode } from 'react'

type Props = {
  title: string
  open: boolean
  busy?: boolean
  error?: boolean
  children: ReactNode
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
}

/** A yes/no popup for an action that cannot be undone. */
export function ConfirmDialog({ title, open, busy, error, children, confirmLabel, onConfirm, onCancel }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={(d) => !d.open && onCancel()} placement="center" lazyMount unmountOnExit>
      <Portal>
        <Dialog.Backdrop bg="app.scrim" />
        <Dialog.Positioner>
          <Dialog.Content bg="app.surface" color="app.text" borderRadius="lg" maxW="420px">
            <Dialog.Header>
              <Dialog.Title>{title}</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Text color="app.text2" fontSize="sm">{children}</Text>
              {error && <Text color="app.missText" fontSize="sm" mt="2">Could not delete. Try again.</Text>}
            </Dialog.Body>
            <Dialog.Footer>
              <Button variant="ghost" color="app.link" onClick={onCancel}>Keep</Button>
              <Button colorPalette="red" loading={busy} onClick={onConfirm}>{confirmLabel}</Button>
            </Dialog.Footer>
            <Dialog.CloseTrigger asChild>
              <Button variant="ghost" size="sm" aria-label="Close" onClick={onCancel}>×</Button>
            </Dialog.CloseTrigger>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}
